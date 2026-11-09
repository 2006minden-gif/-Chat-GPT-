<?php
declare(strict_types=1);
ini_set('display_errors','0');
require_once __DIR__.'/core.php';require_once __DIR__.'/provider.php';require_once __DIR__.'/notifications.php';require_once __DIR__.'/invoices.php';require_once __DIR__.'/payments.php';require_once __DIR__.'/read.php';
function bill_dispatch(bool $customer,string $route,string $method):never{
 try{
  $a=bill_actor($customer,$method!=='GET');rate('billing:'.$a['type'].':'.$a['id'],180);
  if($method==='GET'){
   if($route==='invoices')json_response(bill_list($a));
   if(preg_match('~^invoices/([1-9][0-9]*)$~D',$route,$m))json_response(['ok'=>true,'record'=>bill_public($a,bill_invoice($a,(int)$m[1]))]);
   if($route==='report')json_response(bill_report($a));
   if($route==='export')bill_csv($a);
   if($route==='notifications')json_response(bill_notifications($a));
   if($route==='preferences')json_response(['ok'=>true,'optional_email'=>$a['type']==='customer'&&(bool)crm_query('SELECT optional_email FROM nd_notification_preferences WHERE account_id=?',[$a['id']])->fetchColumn()]);
   if($route==='settings')json_response(['ok'=>true,'provider_ready'=>bill_provider_ready(),'mode'=>'sandbox','live_enabled'=>false,'merchant_approved'=>(config()['billing_merchant']['approved']??false)===true,'email_enabled'=>(config()['billing_email_enabled']??false)===true,'scheduler_verified'=>false,'currency'=>'RUB','partial_payments_enabled'=>false]);
   if($route==='payments'||$route==='refunds'){cc_owner($a);$table=$route==='payments'?'nd_payment_attempts':'nd_refunds';$cols=$route==='payments'?'id,invoice_id,amount_minor,currency,state,last_error,created_at':'id,attempt_id,amount_minor,reason,state,last_error,created_at';json_response(['ok'=>true,'items'=>crm_query('SELECT '.$cols.' FROM '.$table.' ORDER BY id DESC LIMIT 25 OFFSET '.((cc_page()-1)*25))->fetchAll(),'page'=>cc_page(),'page_size'=>25]);}
  }elseif($method==='POST'){
   $d=input();
   if($route==='invoices')json_response(bill_save($a,0,$d));
   if(preg_match('~^invoices/([1-9][0-9]*)/(save|issue|cancel|send|adjust|pay)$~D',$route,$m))json_response(match($m[2]){'save'=>bill_save($a,(int)$m[1],$d),'pay'=>bill_pay($a,(int)$m[1],$d),default=>bill_action($a,(int)$m[1],$m[2],$d)});
   if(preg_match('~^payments/([1-9][0-9]*)/(reconcile|refund)$~D',$route,$m))json_response($m[2]==='refund'?bill_refund($a,(int)$m[1],$d):bill_sync_payment($a,(int)$m[1]));
   if(preg_match('~^refunds/([1-9][0-9]*)/reconcile$~D',$route,$m))json_response(bill_sync_refund($a,(int)$m[1]));
   if(preg_match('~^notifications/([1-9][0-9]*)/read$~D',$route,$m)){crm_query('UPDATE nd_notification_outbox SET read_at=COALESCE(read_at,UTC_TIMESTAMP()) WHERE id=? AND recipient_type=? AND recipient_id=?',[(int)$m[1],$a['type'],$a['id']]);json_response(['ok'=>true]);}
   if($route==='preferences'&&$a['type']==='customer'){if(!is_bool($d['optional_email']??null))crm_fail(422,'Выберите настройку уведомлений.');crm_query('INSERT INTO nd_notification_preferences(account_id,optional_email) VALUES (?,?) ON DUPLICATE KEY UPDATE optional_email=VALUES(optional_email)',[$a['id'],$d['optional_email']?1:0]);json_response(['ok'=>true]);}
  }
  crm_fail(404,'Раздел не найден.');
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'billing_error');}catch(CustomerFailure $e){fail($e->status,$e->getMessage(),$e->errorCode);}
}
