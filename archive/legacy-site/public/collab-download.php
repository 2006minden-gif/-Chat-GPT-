<?php
declare(strict_types=1);
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/collab/core.php';require dirname(__DIR__).'/private/collab/files.php';
security_headers();header('Cache-Control: private, no-store');header('X-Robots-Tag: noindex,nofollow');
try{$a=cc_actor(($_GET['mode']??'customer')!=='owner');$id=filter_var($_GET['id']??'',FILTER_VALIDATE_INT);if(!$id||$id<1)crm_fail(404,'Запись не найдена.');cc_download($a,$id);}
catch(CrmFailure $e){fail($e->status,$e->getMessage(),'collaboration_error');}catch(CustomerFailure $e){fail($e->status,$e->getMessage(),$e->errorCode);}catch(Throwable $e){server_error($e);}
