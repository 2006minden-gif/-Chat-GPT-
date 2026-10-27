<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
require dirname(__DIR__).'/private/owner-bootstrap.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
try {
    if ($_SERVER['REQUEST_METHOD']==='POST') {same_origin();owner_bootstrap_create(input());}
    if ($_SERVER['REQUEST_METHOD']!=='GET')fail(405,'Метод не поддерживается');
} catch(Throwable $e){server_error($e);}
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Первый вход владельца — НейроДело</title><link rel="icon" href="/favicon.svg" type="image/svg+xml"><link rel="stylesheet" href="/styles.css"><link rel="stylesheet" href="/crm.css"><script src="/owner-setup.js" defer></script></head><body><main class="wrap"><section class="login-panel"><a href="/">НейроДело</a><h1>Первый вход владельца</h1><p>Задайте пароль для личного кабинета. Персональная ссылка работает один раз и ограничена по времени.</p><p id="setup-message" role="status">Проверяем ссылку…</p><form id="owner-setup-form" hidden><label for="owner-password">Новый пароль (от 12 символов, до 72 байт)</label><input id="owner-password" name="password" type="password" required minlength="12" maxlength="72" autocomplete="new-password"><label for="owner-repeat">Повторите пароль</label><input id="owner-repeat" name="repeat" type="password" required minlength="12" maxlength="72" autocomplete="new-password"><button class="button primary" type="submit">Создать кабинет</button></form><p><a href="/studio.php">Войти в существующий кабинет →</a></p></section></main></body></html>
