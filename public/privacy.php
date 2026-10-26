<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');
try {
    $document=privacy_document();
    $policy=$document['settings'];
    $available=$policy['enabled'];
} catch(Throwable $e){server_error($e);}
$esc=static fn(string $value):string=>htmlspecialchars($value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Как НейроДело работает с данными: просмотр сайта, локальный бриф, обращения в Telegram и служебные cookie."><title>Политика конфиденциальности — НейроДело</title><link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="canonical" href="https://neurodelo.pro/privacy.php"><link rel="stylesheet" href="/styles.css"></head><body>
<header class="header wrap"><a class="logo" href="/">НейроДело<span class="logo-dot">.</span></a><a class="header-cta" href="/services.php">Услуги и бриф ↗</a></header>
<main class="wrap section legal-page"><div class="eyebrow">ОТКРЫТО О ДАННЫХ</div><h1>Политика конфиденциальности</h1>
<?php if($available): ?>
<p>Версия: <?= $esc($policy['version']) ?></p><div class="policy-text"><?= $esc($document['text']) ?></div>
<?php else: ?>
<article data-privacy-mode="notice"><p class="policy-status">Приём заявок через форму отключён.</p><p>Версия документа для формы ещё не активна. Связаться с владельцем можно через <a href="https://t.me/minden2006">@minden2006</a>.</p></article>
<?php endif; ?><p><a href="/consent.php">Согласие на обработку персональных данных →</a></p></main><footer class="wrap footer"><a href="/">Главная</a><a href="/services.php">Услуги и бриф</a><a href="/sitemap.php">Карта сайта</a></footer></body></html>
