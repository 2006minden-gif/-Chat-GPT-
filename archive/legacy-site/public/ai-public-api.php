<?php
declare(strict_types=1);
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/ai/routes.php';security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex,nofollow');
try{$route=$_GET['r']??'';if(!is_string($route))crm_fail(404,'Раздел не найден.');ai_public_dispatch($route,$_SERVER['REQUEST_METHOD']);}catch(CrmFailure $e){fail($e->status,$e->getMessage(),'ai_error');}catch(Throwable $e){server_error($e);}
