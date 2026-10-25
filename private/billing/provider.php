<?php
declare(strict_types=1);
interface BillingProvider {
 public function createPayment(array $attempt):array;
 public function getPaymentStatus(string $id):array;
 public function verifyWebhook(array $event):array;
 public function normalizeProviderEvent(array $object):array;
 public function requestRefund(array $refund,array $attempt):array;
 public function getRefundStatus(string $id):array;
}
function bill_provider_ready():bool{
 $c=config();$m=$c['billing_provider']??[];
 return ($m['enabled']??false)===true&&($m['sandbox_approved']??false)===true&&($m['mode']??'')==='sandbox'&&($m['name']??'')==='yookassa'&&is_string($m['shop_id']??null)&&$m['shop_id']!==''&&is_string($m['secret_key']??null)&&str_starts_with($m['secret_key'],'test_');
}
function bill_provider():BillingProvider{if(!bill_provider_ready())crm_fail(503,'Онлайн-оплата пока недоступна. Свяжитесь с исполнителем для получения реквизитов.');return new YooKassaSandbox();}
function bill_merchant_hash():string{$m=config()['billing_provider']??[];return hash('sha256','yookassa:sandbox:'.($m['shop_id']??''));}
final class YooKassaSandbox implements BillingProvider {
 private function api(string $method,string $path,?array $body=null,?string $key=null):array{
  $m=config()['billing_provider'];$base='https://api.yookassa.ru/v3/';$c=config();
  // Injection is available exclusively on an explicit loopback development installation.
  if(isset($c['billing_test_transport'])){
   $u=parse_url($c['billing_test_transport']);if(($c['billing_test_mode']??false)!==true||!in_array(parse_url($c['app_url'],PHP_URL_HOST),['127.0.0.1','localhost','::1'],true)||($u['scheme']??'')!=='http'||($u['host']??'')!=='127.0.0.1'||isset($u['user'])||isset($u['pass'])||isset($u['query'])||isset($u['fragment']))crm_fail(503,'Тестовый транспорт недоступен.');$base=rtrim($c['billing_test_transport'],'/').'/';
  }
  $headers=['Accept: application/json','Content-Type: application/json','Authorization: Basic '.base64_encode($m['shop_id'].':'.$m['secret_key'])];if($key)$headers[]='Idempotence-Key: '.$key;
  $ctx=stream_context_create(['http'=>['method'=>$method,'header'=>implode("\r\n",$headers),'content'=>$body===null?'':json_encode($body,JSON_THROW_ON_ERROR),'timeout'=>8,'follow_location'=>0,'ignore_errors'=>true],'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'allow_self_signed'=>false]]);
  $fp=@fopen($base.$path,'rb',false,$ctx);if(!$fp)crm_fail(503,'Связь с оплатой прервана. Результат неизвестен; повторите проверку, не создавая новый платёж.');
  try{$meta=stream_get_meta_data($fp);$raw=stream_get_contents($fp,262145);}finally{fclose($fp);}if(!is_string($raw)||strlen($raw)>262144)crm_fail(503,'Не удалось проверить ответ платёжного сервиса.');
  $h=$meta['wrapper_data']??[];$status=0;$json=false;foreach($h as $line){if(preg_match('~^HTTP/\S+ (\d+)~',$line,$x))$status=(int)$x[1];if(preg_match('~^Content-Type:\s*application/json(?:;|$)~i',$line))$json=true;}
  $data=json_decode($raw,true);if($status<200||$status>=300||!$json||!is_array($data)||isset($data['type'])&&$data['type']==='error')crm_fail(503,'Платёжный сервис не подтвердил операцию. Используйте проверку статуса.');return $data;
 }
 private function id(string $id):string{if(!preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$id))crm_fail(422,'Неверный идентификатор платежа.');return $id;}
 public function createPayment(array $a):array{
  return $this->api('POST','payments',['amount'=>['value'=>bill_decimal((int)$a['amount_minor']),'currency'=>$a['currency']],'capture'=>true,'confirmation'=>['type'=>'redirect','return_url'=>rtrim(config()['app_url'],'/').'/billing.php#invoices/'.$a['invoice_id']],'description'=>'НейроДело — оплата счёта','metadata'=>['nd_attempt'=>$a['request_key']]],$a['request_key']);
 }
 public function getPaymentStatus(string $id):array{return $this->api('GET','payments/'.$this->id($id));}
 public function verifyWebhook(array $event):array{
  // YooKassa notifications are hints, NOT signed authority. Fetch under merchant API credentials.
  if(($event['type']??'')!=='notification'||!in_array($event['event']??'',['payment.succeeded','payment.canceled','payment.waiting_for_capture','refund.succeeded'],true)||!is_string($event['object']['id']??null))crm_fail(400,'Некорректное уведомление.');
  return $event['event']==='refund.succeeded'?['kind'=>'refund','object'=>$this->getRefundStatus($event['object']['id'])]:['kind'=>'payment','object'=>$this->getPaymentStatus($event['object']['id'])];
 }
 public function normalizeProviderEvent(array $o):array{
  if(!is_string($o['id']??null)||($o['test']??false)!==true||!in_array($o['status']??'',['pending','waiting_for_capture','succeeded','canceled'],true)||!is_string($o['amount']['currency']??null))crm_fail(409,'Платёжный сервис вернул несогласованные данные тестовой операции.');
  $this->id($o['id']);if($o['status']==='succeeded'&&(($o['paid']??false)!==true||empty($o['captured_at'])))crm_fail(409,'Списание ещё не подтверждено.');
  $status=$o['status']==='waiting_for_capture'?'pending':$o['status'];return ['provider_id'=>$o['id'],'state'=>$status,'amount_minor'=>bill_minor($o['amount']['value']??null),'currency'=>$o['amount']['currency'],'key'=>$o['metadata']['nd_attempt']??null,'redirect_url'=>$o['confirmation']['confirmation_url']??null];
 }
 public function requestRefund(array $r,array $a):array{return $this->api('POST','refunds',['payment_id'=>$a['provider_id'],'amount'=>['value'=>bill_decimal((int)$r['amount_minor']),'currency'=>$a['currency']],'description'=>'Возврат по счёту НейроДело'],$r['request_key']);}
 public function getRefundStatus(string $id):array{return $this->api('GET','refunds/'.$this->id($id));}
}
function bill_redirect(mixed $url):?string{
 if($url===null)return null;if(!is_string($url)||strlen($url)>2048||preg_match('/[\x00-\x20\\\\]/',$url))crm_fail(409,'Переход к оплате не подтверждён.');$u=parse_url($url);
 if(!$u||($u['scheme']??'')!=='https'||!in_array($u['host']??'',['yookassa.ru','yoomoney.ru','checkout.payments.yandex.ru'],true)||isset($u['user'])||isset($u['pass'])||isset($u['port'])||isset($u['fragment']))crm_fail(409,'Адрес оплаты не разрешён.');return $url;
}
