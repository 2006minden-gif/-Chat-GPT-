<?php
declare(strict_types=1);
ini_set('display_errors','0');
require dirname(__DIR__).'/private/app.php';
require dirname(__DIR__).'/private/customer-auth.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
try {
    $r=$_GET['r']??'';
    if(!is_string($r))fail(404,'Не найдено');
    ca_dispatch($r,$_SERVER['REQUEST_METHOD']);
}catch(CustomerFailure $e){fail($e->status,$e->getMessage(),$e->errorCode);}
catch(Throwable $e){server_error($e);}
