<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
require dirname(__DIR__).'/app.php';require __DIR__.'/max.php';
$result=['ok'=>true];
try{$result=array_replace($result,max_pump(10));}catch(Throwable $e){$result['deferred']=true;$result['error_code']='max_retry_deferred';}
try{require_once dirname(__DIR__).'/lifecycle/routes.php';require_once dirname(__DIR__).'/lifecycle/access.php';$result['access_jobs_processed']=la_pump(10);}catch(Throwable $e){$result['ok']=false;$result['error_code']='access_retry_deferred';}
try{require_once dirname(__DIR__).'/support/core.php';$result['support_jobs_processed']=sa_pump();}catch(Throwable $e){$result['ok']=false;$result['error_code']='support_retry_deferred';}
try{if((config()['billing_email_enabled']??false)===true){require_once dirname(__DIR__).'/billing/core.php';require_once dirname(__DIR__).'/billing/notifications.php';$accepted=0;for($i=0;$i<10;$i++){if(!bill_deliver_one())break;$accepted++;}$result['email_jobs_processed']=$accepted;$result['email_evidence']='smtp_acceptance_only';}}catch(Throwable $e){$result['ok']=false;$result['error_code']='email_retry_deferred';}
echo json_encode($result);if(!$result['ok'])exit(1);
