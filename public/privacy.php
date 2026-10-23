<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');
try {
    $policy=privacy_settings();
    $available=$policy['enabled'];
    if(!$available)http_response_code(503);
    $text=$available ? file_get_contents(dirname(__DIR__).'/private/privacy-policy.txt') : 'Политика обработки персональных данных ещё не опубликована. Приём заявок через форму отключён.';
} catch(Throwable $e){server_error($e);}
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Обработка персональных данных — НейроДело</title><link rel="stylesheet" href="styles.css"></head><body><main class="wrap section"><a href="/">← На главную</a><h1>Обработка персональных данных</h1><p>Версия: <?=htmlspecialchars($policy['version'] ?: 'не утверждена', ENT_QUOTES, 'UTF-8')?></p><div class="policy-text"><?=htmlspecialchars($text,ENT_QUOTES,'UTF-8')?></div></main></body></html>
