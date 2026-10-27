<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
require dirname(__DIR__).'/private/notifications/max.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
try {
    if($_SERVER['REQUEST_METHOD']!=='POST')fail(405,'Метод не поддерживается');
    $secret=$_SERVER['HTTP_X_MAX_BOT_API_SECRET']??'';
    if(!is_string($secret)||!preg_match('/^[a-f0-9]{64}$/D',$secret))fail(403,'Недопустимый запрос');
    max_webhook(input(),$secret);json_response(['ok'=>true]);
}catch(Throwable $e){server_error($e);}
