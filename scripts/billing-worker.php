<?php
/** Explicit CLI scheduler prerequisite. No public trigger, no migrations or live charges. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/billing/routes.php';
$locked=false;
try{
 if(count($argv)!==1)throw new RuntimeException('invalid_arguments');bill_gate();
 $lock='nd_billing_worker_'.substr(hash('sha256',config()['db_name']),0,32);if((int)crm_query('SELECT GET_LOCK(?,0)',[$lock])->fetchColumn()!==1)throw new RuntimeException('worker_busy');$locked=true;
 $events=bill_bridge_events();$sent=0;for($i=0;$i<50&&bill_deliver_one();$i++)$sent++;
 // No external status polling without a separately approved provider and bounded queue.
 $checked=0;if(bill_provider_ready()){
  foreach(crm_query("SELECT id FROM nd_payment_attempts WHERE state IN ('creating','pending') AND next_check<=UTC_TIMESTAMP() ORDER BY next_check,id LIMIT 25")->fetchAll() as $r){crm_query('UPDATE nd_payment_attempts SET next_check=DATE_ADD(UTC_TIMESTAMP(),INTERVAL 5 MINUTE) WHERE id=?',[$r['id']]);try{bill_sync_payment(['type'=>'owner','id'=>1],(int)$r['id']);$checked++;}catch(CrmFailure $e){}}
  foreach(crm_query("SELECT id FROM nd_refunds WHERE state IN ('creating','pending') AND next_check<=UTC_TIMESTAMP() ORDER BY next_check,id LIMIT 25")->fetchAll() as $r){crm_query('UPDATE nd_refunds SET next_check=DATE_ADD(UTC_TIMESTAMP(),INTERVAL 5 MINUTE) WHERE id=?',[$r['id']]);try{bill_sync_refund(['type'=>'owner','id'=>1],(int)$r['id']);$checked++;}catch(CrmFailure $e){}}
 }
 echo json_encode(['ok'=>true,'events_checked'=>$events,'deliveries_attempted'=>$sent,'reconciliations'=>$checked,'scheduler_configured'=>false]).PHP_EOL;
}catch(Throwable $e){fwrite(STDERR,"{\"error\":\"worker_unavailable\"}\n");exit(1);}finally{if($locked)crm_query('SELECT RELEASE_LOCK(?)',[$lock]);}
