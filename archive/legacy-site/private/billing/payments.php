<?php
declare(strict_types=1);
function bill_attempt(array $a,int $id):array{$r=crm_query('SELECT * FROM nd_payment_attempts WHERE id=?',[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');bill_invoice($a,(int)$r['invoice_id']);return $r;}
function bill_apply_payment(array $attempt,array $object):array{
 $n=bill_provider()->normalizeProviderEvent($object);
 return crm_atomic(function()use($attempt,$n){$owner=['type'=>'owner','id'=>1];$i=bill_invoice($owner,(int)$attempt['invoice_id'],true);$a=crm_query('SELECT * FROM nd_payment_attempts WHERE id=? FOR UPDATE',[$attempt['id']])->fetch();
  if($a['merchant_hash']!==bill_merchant_hash()||$n['key']!==$a['request_key']||$n['amount_minor']!==(int)$a['amount_minor']||$n['currency']!==$a['currency']||($a['provider_id']!==null&&$a['provider_id']!==$n['provider_id']))crm_fail(409,'Платёж не соответствует счёту или магазину.');
  if(in_array($a['state'],['succeeded','canceled'],true)&&$a['state']!==$n['state'])crm_fail(409,'Устаревшее состояние платежа отклонено.');
  $url=bill_redirect($n['redirect_url']);$fresh=$a['state']!==$n['state'];
  if($n['state']==='succeeded'&&$a['state']!=='succeeded'){
   if($i['state']!=='issued'||$n['amount_minor']>bill_balance($i)['outstanding_minor'])crm_fail(409,'Подтверждение требует ручной сверки суммы.');
   crm_query('INSERT INTO nd_payment_transactions(attempt_id,provider_id,amount_minor,currency,settled_at) VALUES (?,?,?,?,UTC_TIMESTAMP())',[$a['id'],$n['provider_id'],$n['amount_minor'],$n['currency']]);
  }
  crm_query('UPDATE nd_payment_attempts SET provider_id=?,state=?,redirect_url=COALESCE(?,redirect_url),verified_at=UTC_TIMESTAMP(),last_error=NULL WHERE id=?',[$n['provider_id'],$n['state'],$url,$a['id']]);
  $event=hash('sha256','payment:'.$n['provider_id'].':'.$n['state']);crm_query('INSERT INTO nd_payment_events(event_key,attempt_id,state) VALUES (?,?,?) ON DUPLICATE KEY UPDATE event_key=VALUES(event_key)',[$event,$a['id'],$n['state']]);
  if($fresh){crm_query('UPDATE nd_invoices SET version=version+1 WHERE id=?',[$i['id']]);bill_audit($owner,$i,'payment_'.$n['state']);bill_emit('payment:'.$a['id'].':'.$n['state'],match($n['state']){'succeeded'=>'payment_confirmed','canceled'=>'payment_failed',default=>'payment_pending'},'invoices',(int)$i['id'],(int)$i['customer_id']);}
  return ['ok'=>true,'id'=>(int)$a['id'],'state'=>$n['state'],'redirect_url'=>$url??$a['redirect_url']];
 });
}
function bill_sync_payment(array $a,int $id):array{
 $attempt=bill_attempt($a,$id);$provider=bill_provider();if($attempt['merchant_hash']!==bill_merchant_hash())crm_fail(409,'Нельзя сверять платёж другого магазина.');
 try{if($attempt['provider_id']===null){$o=$provider->createPayment($attempt);$n=$provider->normalizeProviderEvent($o);$o=$provider->getPaymentStatus($n['provider_id']);}else $o=$provider->getPaymentStatus($attempt['provider_id']);return bill_apply_payment($attempt,$o);}
 catch(CrmFailure $e){crm_query("UPDATE nd_payment_attempts SET last_error='verification_unavailable' WHERE id=?",[$id]);throw $e;}
}
function bill_pay(array $a,int $id,array $d):array{
 bill_provider();if($a['type']!=='customer')crm_fail(403,'Оплата доступна в кабинете клиента.');bill_key($d);
 $reserved=bill_mutation($a,'pay:'.$id,$d,function()use($a,$id,$d){$i=bill_invoice($a,$id,true);if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите переход к тестовой оплате.');$b=bill_balance($i);
  if($i['state']!=='issued'||$b['outstanding_minor']<1||$b['refunded_minor']>0)crm_fail(409,'Счёт недоступен для оплаты. После возврата требуется отдельное решение владельца.');
  $pending=crm_query("SELECT id FROM nd_payment_attempts WHERE invoice_id=? AND state IN ('creating','pending') FOR UPDATE",[$id])->fetchColumn();if($pending)return ['ok'=>true,'id'=>(int)$pending];
  crm_query("INSERT INTO nd_payment_attempts(invoice_id,request_key,provider,merchant_hash,amount_minor,currency) VALUES (?,?,'yookassa_sandbox',?,?,?)",[$id,bill_key($d),bill_merchant_hash(),$b['outstanding_minor'],$i['currency']]);$pid=(int)db()->lastInsertId();bill_audit($a,$i,'payment_started');bill_emit('attempt:'.$pid,'payment_pending','invoices',$id,(int)$i['customer_id']);return ['ok'=>true,'id'=>$pid];
 });return bill_sync_payment($a,$reserved['id']);
}
function bill_refund(array $a,int $pid,array $d):array{
 cc_owner($a);bill_provider();bill_key($d);
 $reserved=bill_mutation($a,'refund:'.$pid,$d,function()use($a,$pid,$d){$attempt=bill_attempt($a,$pid);$i=bill_invoice($a,(int)$attempt['invoice_id'],true);$attempt=crm_query('SELECT * FROM nd_payment_attempts WHERE id=? FOR UPDATE',[$pid])->fetch();$amount=bill_minor($d['amount']??null);$reason=bill_text($d,'reason');
  if(($d['confirm']??false)!==true||$attempt['state']!=='succeeded'||$amount<1)crm_fail(422,'Подтвердите возврат подтверждённого платежа.');
  $reserved=(int)crm_query("SELECT COALESCE(SUM(amount_minor),0) FROM nd_refunds WHERE attempt_id=? AND state<>'canceled' FOR UPDATE",[$pid])->fetchColumn();
  if($reserved+$amount>(int)$attempt['amount_minor'])crm_fail(409,'Сумма возврата превышает доступный остаток.');
  crm_query('INSERT INTO nd_refunds(attempt_id,request_key,amount_minor,reason) VALUES (?,?,?,?)',[$pid,bill_key($d),$amount,$reason]);$id=(int)db()->lastInsertId();bill_audit($a,$i,'refund_requested');return ['ok'=>true,'id'=>$id];
 });return bill_sync_refund($a,$reserved['id']);
}
function bill_sync_refund(array $a,int $id):array{
 cc_owner($a);$r=crm_query('SELECT * FROM nd_refunds WHERE id=?',[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');$p=bill_attempt($a,(int)$r['attempt_id']);if($p['merchant_hash']!==bill_merchant_hash())crm_fail(409,'Магазин не совпадает.');$provider=bill_provider();
 try{$object=$r['provider_id']?$provider->getRefundStatus($r['provider_id']):$provider->requestRefund($r,$p);if(!is_string($object['id']??null)||!preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$object['id']))crm_fail(409,'Возврат не подтверждён.');$object=$provider->getRefundStatus($object['id']);return bill_apply_refund($r,$p,$object);}
 catch(CrmFailure $e){crm_query("UPDATE nd_refunds SET last_error='verification_unavailable' WHERE id=?",[$id]);throw $e;}
}
function bill_apply_refund(array $r,array $p,array $o):array{
 // Refund objects have no test/paid fields. Merchant-authorized GET + exact known payment binding.
 if(!is_string($o['id']??null)||!preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$o['id'])||($o['payment_id']??null)!==$p['provider_id']||bill_minor($o['amount']['value']??null)!==(int)$r['amount_minor']||($o['amount']['currency']??null)!==$p['currency']||!in_array($o['status']??'', ['pending','succeeded','canceled'],true))crm_fail(409,'Возврат не соответствует платежу.');
 return crm_atomic(function()use($r,$p,$o){$a=['type'=>'owner','id'=>1];$i=bill_invoice($a,(int)$p['invoice_id'],true);$current=crm_query('SELECT * FROM nd_refunds WHERE id=? FOR UPDATE',[$r['id']])->fetch();if(($current['provider_id']!==null&&$current['provider_id']!==$o['id'])||in_array($current['state'],['succeeded','canceled'],true)&&$current['state']!==$o['status'])crm_fail(409,'Устаревшее состояние возврата.');
  crm_query('UPDATE nd_refunds SET state=?,provider_id=?,verified_at=UTC_TIMESTAMP(),last_error=NULL WHERE id=?',[$o['status'],$o['id'],$r['id']]);
  if($current['state']!==$o['status']){crm_query('UPDATE nd_invoices SET version=version+1 WHERE id=?',[$i['id']]);bill_audit($a,$i,'refund_'.$o['status']);if($o['status']==='succeeded')bill_emit('refund:'.$r['id'].':done','refund_completed','invoices',(int)$i['id'],(int)$i['customer_id']);}
  return ['ok'=>true,'id'=>(int)$r['id'],'state'=>$o['status']];
 });
}
