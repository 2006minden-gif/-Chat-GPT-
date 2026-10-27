<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
require dirname(__DIR__).'/app.php';require __DIR__.'/max.php';
try{$result=max_pump(10);if((config()['billing_email_enabled']??false)===true){require_once dirname(__DIR__).'/billing/core.php';require_once dirname(__DIR__).'/billing/notifications.php';$accepted=0;for($i=0;$i<10;$i++){if(!bill_deliver_one())break;$accepted++;}$result['email_jobs_processed']=$accepted;$result['email_evidence']='smtp_acceptance_only';}echo json_encode($result);}
catch(Throwable $e){echo '{"ok":false,"error":"notification_worker_failed"}';exit(1);}
