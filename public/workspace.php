<?php
declare(strict_types=1);
ini_set('display_errors','0');
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex,nofollow');
try{if((config()['crm_operations_enabled']??false)!==true){http_response_code(404);exit;}}catch(Throwable $e){server_error($e);}
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>НейроДело — управление</title><link rel="stylesheet" href="operations.css"></head><body>
<button id="menu" class="mobile-menu" aria-controls="sidebar" aria-expanded="false">Меню</button>
<aside id="sidebar"><a class="brand" href="/">НейроДело<span>•</span></a><nav id="navigation" aria-label="Разделы CRM"></nav><a href="/studio.php">Прежний список заявок</a></aside>
<main><header><h1 id="title">Обзор</h1><form id="global-search"><label for="global-query">Поиск по CRM</label><input id="global-query" maxlength="100" placeholder="Имя или название"><button>Найти</button></form><a href="#notifications" aria-label="Уведомления">Уведомления</a><span>Владелец</span><button id="logout">Выйти</button></header>
<p id="message" role="status" aria-live="polite"></p><section id="login" hidden><h2>Вход владельца</h2><form id="login-form"><label for="owner-password">Пароль</label><input id="owner-password" type="password" autocomplete="current-password" required maxlength="256"><button>Войти</button></form></section>
<div id="toolbar"><button id="refresh">Обновить</button><button id="create">Добавить</button><label>Статус <select id="status"><option value="">Все</option></select></label><label>Тип клиента <select id="kind"><option value="">Все</option><option value="person">Частное лицо</option><option value="company">Компания</option></select></label><label>Архив <select id="archive"><option value="">Действующие</option><option value="true">Архив</option><option value="all">Все</option></select></label><div id="relation-filters" class="actions"></div><button id="view-toggle">Доска / список</button></div>
<div id="content"></div><footer id="pagination"><button id="prev">Назад</button><span id="page-number"></span><button id="next">Далее</button></footer>
</main><dialog id="editor" aria-labelledby="editor-title"><h2 id="editor-title">Запись</h2><form id="record-form"><div id="fields"></div><p id="form-message" role="status" aria-live="polite"></p><button id="save">Сохранить</button><button type="button" id="cancel">Отмена</button></form><button id="reload-record" type="button">Загрузить актуальные данные</button></dialog>
<dialog id="details" aria-labelledby="details-title"><h2 id="details-title">Карточка</h2><div id="detail-content"></div><button id="close-details">Закрыть</button></dialog>
<script src="operations.js"></script></body></html>
