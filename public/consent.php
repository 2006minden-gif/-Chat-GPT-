<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');
$legal=release_legal_documents();
if (!$legal) {http_response_code(503);exit('Документ временно недоступен.');}
$esc=static fn(string $value):string=>htmlspecialchars($value,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
?><!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Согласие на обработку данных — НейроДело</title><link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="canonical" href="https://neurodelo.pro/consent.php"><link rel="stylesheet" href="/styles.css"></head><body><header class="header wrap"><a class="logo" href="/">НейроДело.</a><a class="header-cta" href="/#contact">К форме обращения ↗</a></header><main class="wrap section legal-page"><h1>Согласие на обработку персональных данных</h1><p>Версия: <?= $esc($legal['version']) ?></p><div class="policy-text"><?= $esc($legal['consent']) ?></div><p>Согласие подтверждается только самостоятельной отметкой перед отправкой формы.</p></main><footer class="wrap footer"><a href="/privacy.php">Политика конфиденциальности</a><a href="/sitemap.php">Карта сайта</a><a href="/">Главная</a></footer></body></html>
