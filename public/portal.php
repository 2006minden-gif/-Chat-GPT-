<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex,nofollow');
if((config()['crm_operations_enabled']??false)!==true){http_response_code(404);exit;}
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>НейроДело — мои проекты</title><link rel="stylesheet" href="operations.css"></head><body><main class="portal"><header><h1>Мои заказы и проекты</h1><a href="/customer.php">Мой кабинет</a></header><p id="portal-message" role="status" aria-live="polite"></p><nav class="tabs" aria-label="Мои документы"><a href="#orders">Заказы</a><a href="#projects">Проекты</a><button id="portal-refresh">Обновить</button></nav><div id="portal-content"></div><footer><button id="portal-prev">Назад</button><span id="portal-page"></span><button id="portal-next">Далее</button></footer></main><script src="portal.js"></script></body></html>
