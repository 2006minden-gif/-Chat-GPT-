<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
try {
    $key=config()['setup_key'] ?? '';
    if(!is_string($key) || strlen($key)<32) fail(503,'Первичная настройка отключена. Задайте setup_key в приватном config.php.');
    if(db()->query('SELECT id FROM nd_admin WHERE id=1')->fetch())fail(403,'CRM уже настроена. Удалите setup.php и очистите setup_key.');
    $message='';
    if($_SERVER['REQUEST_METHOD']==='POST') {
        same_origin();rate('setup',10);
        $given=$_POST['setup_key'] ?? ''; $password=$_POST['password'] ?? ''; $repeat=$_POST['repeat'] ?? '';
        if(!is_string($given) || !hash_equals($key,$given)) {http_response_code(403);$message='Неверный ключ установки';}
        elseif(!is_string($password) || !is_string($repeat) || strlen($password)<12 || strlen($password)>72 || $password!==$repeat){http_response_code(422);$message='Пароли должны совпадать; длина от 12 до 72 байт.';}
        else {
            // Unique id prevents concurrent setup requests from replacing the password.
            db()->prepare('INSERT INTO nd_admin (id,password_hash) VALUES (1,?)')->execute([password_hash($password,PASSWORD_DEFAULT)]);
            header('Location: /studio.php',true,303);exit;
        }
    }
} catch(Throwable $e){server_error($e);}
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Первичная настройка — НейроДело</title><link rel="stylesheet" href="styles.css"><link rel="stylesheet" href="crm.css"></head><body><main class="wrap"><section class="login-panel"><h1>Настройка CRM</h1><p>После установки удалите setup.php и очистите setup_key. Настоящий пароль задавайте только на HTTPS.</p><p role="status"><?=htmlspecialchars($message,ENT_QUOTES,'UTF-8')?></p><form method="post"><label for="key">Ключ установки из config.php</label><input id="key" name="setup_key" type="password" required autocomplete="off"><label for="password">Пароль CRM (12–72 байта)</label><input id="password" name="password" type="password" required minlength="12" maxlength="72" autocomplete="new-password"><label for="repeat">Повторите пароль</label><input id="repeat" name="repeat" type="password" required minlength="12" maxlength="72" autocomplete="new-password"><button class="button primary">Создать кабинет</button></form></section></main></body></html>
