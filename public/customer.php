<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
require_once dirname(__DIR__).'/private/customer-settings-state.php';$customerPolicy=ca_privacy_settings();$e=fn($v)=>htmlspecialchars((string)$v,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
$view=$_GET['view']??'login';
if(!is_string($view)||!in_array($view,['login','register','forgot','reset','invite','verify','resend'],true))$view='login';
$titles=['login'=>'Войти в кабинет','register'=>'Создать аккаунт','forgot'=>'Восстановить пароль','reset'=>'Новый пароль','invite'=>'Принять приглашение','verify'=>'Подтвердить email','resend'=>'Повторить подтверждение'];
?>
<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title><?= $titles[$view] ?> — НейроДело</title><link rel="stylesheet" href="styles.css"><link rel="stylesheet" href="crm.css"><link rel="stylesheet" href="customer.css"></head>
<body data-view="<?= $view ?>"><header class="wrap header"><a class="logo" href="/">НейроДело<span class="logo-dot">.</span></a><span class="eyebrow">КАБИНЕТ КЛИЕНТА</span></header>
<main class="wrap"><section class="login-panel customer-panel"><div class="eyebrow">ВАШИ ИДЕИ. НАШ СЛЕДУЮЩИЙ ШАГ.</div><h1 id="page-title"><?= $titles[$view] ?><span class="pink">.</span></h1>
<p id="availability" role="status">Проверяем доступность кабинета…</p>
<form id="customer-form"><fieldset id="auth-fields" disabled><legend class="visually-hidden"><?= $titles[$view] ?></legend>
<?php if($view==='register'): ?><label for="customer-name">Имя</label><input id="customer-name" name="name" autocomplete="name" maxlength="190" required><?php endif; ?>
<?php if(in_array($view,['login','register','forgot','resend'],true)): ?><label for="customer-email">Email</label><input id="customer-email" name="email" type="email" autocomplete="email" maxlength="190" required><?php endif; ?>
<?php if(in_array($view,['login','register','invite','reset'],true)): ?><label for="customer-password">Пароль</label><div class="password-row"><input id="customer-password" name="password" type="password" autocomplete="<?= $view==='login'?'current-password':'new-password' ?>" <?= $view==='login'?'':'minlength="12"' ?> maxlength="72" aria-describedby="password-help" required><button type="button" id="toggle-password" aria-controls="customer-password" aria-pressed="false">Показать</button></div><p id="password-help" class="field-help">От 12 символов, буквы и цифры. Не более 72 байт.</p><?php endif; ?>
<?php if(in_array($view,['register','invite','reset'],true)): ?><label for="customer-repeat">Повторите пароль</label><input id="customer-repeat" name="password_confirmation" type="password" autocomplete="new-password" minlength="12" maxlength="72" required><?php endif; ?>
<?php if(in_array($view,['register','invite','verify','login'],true)): ?><label class="customer-consent" for="customer-consent"><input type="checkbox" id="customer-consent" name="consent" <?= $view==='login'?'':'required' ?>><span>Я согласен(на) на обработку данных на условиях <a href="<?= $e($customerPolicy['consent_url']??$customerPolicy['url']) ?>" target="_blank" rel="noopener">отдельного согласия</a> и <a href="<?= $e($customerPolicy['url']) ?>" target="_blank" rel="noopener">политики кабинета</a><?= $view==='login'?' (подтвердите при обновлении документов)':'' ?>.</span></label><?php endif; ?>
<button id="customer-submit" class="button primary"><?= $titles[$view] ?> →</button></fieldset></form>
<p id="customer-message" role="status" aria-live="polite"></p>
<nav class="customer-nav" aria-label="Кабинет"><a href="/customer.php">Вход</a><a href="/customer.php?view=register">Регистрация</a><a href="/customer.php?view=forgot">Забыли пароль?</a><a href="/customer.php?view=resend">Нет письма?</a></nav>
<section id="customer-home" hidden><h2>Вы в кабинете</h2><p id="customer-identity"></p><?php if((config()['crm_operations_enabled']??false)===true): ?><p><a href="/orders.php">Рабочий цикл моих заказов →</a></p><p><a href="/portal.php">Мои заказы и проекты →</a></p><?php endif; ?><button id="customer-logout" class="button primary" type="button">Выйти</button></section>
<a href="/" class="back-link">← Вернуться на сайт</a></section></main><script src="customer.js"></script></body></html>
