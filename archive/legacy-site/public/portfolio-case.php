<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
require dirname(__DIR__).'/private/publication/core.php';
security_headers();
$preview=isset($_GET['preview']);
header('Cache-Control: no-store');
try{
    pub_gate();
    if($preview){
        current_session();
        header('X-Robots-Tag: noindex,nofollow');
        $v=pub_version((int)$_GET['preview']);
        $p=pub_record((int)$v['publication_id']);
    }else{
        $slug=$_GET['case']??'';
        if(!is_string($slug))crm_fail(404,'Работа не найдена.');
        $p=crm_query("SELECT * FROM nd_publications WHERE slug=? AND kind='portfolio' AND state='PUBLISHED'",[$slug])->fetch();
        if(!$p)crm_fail(404,'Работа не опубликована.');
        $v=pub_version((int)$p['published_version_id']);
        if(!pub_live($p,$v))crm_fail(404,'Работа не опубликована.');
    }
    $b=$v['body'];
    $e=fn($s)=>htmlspecialchars((string)$s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
}
catch(CrmFailure $x){
    http_response_code($x->status);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!doctype html><html lang="ru"><head><meta charset="utf-8"><script src="/analytics.js?v=notice-20261102" defer></script><meta name="viewport" content="width=device-width,initial-scale=1"><title>Портфолио — НейроДело</title><link rel="icon" href="/favicon.svg"><link rel="stylesheet" href="/styles.css?v=brand-messengers-20261027"><link rel="stylesheet" href="/services/guide.css?v=brand-messengers-20261027"><link rel="stylesheet" href="/publications.css?v=portfolio-brand-20261103"><link rel="stylesheet" href="/brand-ui.css?v=20261105-layout"></head><body>';
    echo '<header class="header wrap"><a class="logo" href="/"><span class="spark">✳︎</span> НейроДело<span class="logo-dot">.</span></a><nav aria-label="Навигация"><a href="/">Главная</a><a href="/services.php">Услуги</a><a href="/portfolio.php">Портфолио</a></nav></header>';
    echo '<main class="wrap guide"><h1>'.htmlspecialchars($x->getMessage(),ENT_QUOTES,'UTF-8').'</h1><p class="guide-intro">Эта работа ещё не опубликована или была снята с показа.</p><p><a class="button primary" href="/portfolio.php">Вернуться в портфолио<span>→</span></a></p></main>';
    echo '<footer class="wrap footer"><a class="logo" href="/"><span class="spark">✳︎</span> НейроДело.</a><span>Ваша идея. Наши технологии.</span><span>© 2026 НейроДело</span><a class="legal-link" href="/privacy.php">Конфиденциальность</a><a class="legal-link" href="/portfolio.php">Портфолио</a><a class="legal-link" href="/sitemap.php">Карта сайта</a></footer>';
    echo '</body></html>';
    exit;
}
?>
<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title><?= $e($b['title']) ?> — Портфолио — НейроДело</title><meta name="description" content="<?= $e($b['short_description']??'') ?>"><link rel="icon" href="/favicon.ico" sizes="any"><link rel="icon" type="image/svg+xml" href="/favicon.svg"><link rel="stylesheet" href="/styles.css?v=brand-messengers-20261027"><link rel="stylesheet" href="/services/guide.css?v=brand-messengers-20261027"><link rel="stylesheet" href="/publications.css?v=portfolio-brand-20261103"><link rel="stylesheet" href="/analytics.css?v=notice-20261102"><link rel="stylesheet" href="/brand-ui.css?v=20261105-layout"></head><body><?= nd_analytics_noscript() ?>
<header class="header wrap"><a class="logo" href="/"><span class="spark">✳︎</span> НейроДело<span class="logo-dot">.</span></a><nav aria-label="Навигация"><a href="/">Главная</a><a href="/services.php">Услуги</a><a href="/reviews.php">Отзывы</a></nav><a class="header-cta" href="<?= $preview?'#contact':'/?case='.$e($p['slug']).'#contact' ?>">Обсудить проект<span>→</span></a></header>
<main class="wrap guide">
<p style="margin-top:25px"><a href="/portfolio.php" style="color:#8bb7ff;text-decoration:underline;text-underline-offset:3px">← Все работы</a></p>
<?php if($preview): ?><p class="guide-note">Приватный предпросмотр редакции <?= $e($v['revision_number']) ?>. Это не публикация.</p><?php endif; ?>
<h1><?= $e($b['title']) ?></h1>
<p class="guide-intro"><?= $e(pub_categories()[$b['category']??'website']??'') ?></p>
<article>
<?php foreach(['task'=>'Задача','work'=>'Что выполнено','result'=>'Результат','text'=>'О проекте'] as $key=>$label):if(!empty($b[$key])): ?>
<section><h2><?= $label ?></h2><p class="case-text"><?= $e($b[$key]) ?></p></section>
<?php endif;endforeach; ?>
<?php if(!empty($b['project_url'])): ?><p><a href="<?= $e($b['project_url']) ?>" target="_blank" rel="noopener noreferrer">Открыть публичный проект ↗</a></p><?php endif; ?>
<h2>Галерея</h2>
<p class="guide-intro">Изображения и видео расположены в согласованном порядке. Внешние видео открываются на соответствующем сервисе только по вашему действию.</p>
<section id="case-gallery" class="publication-grid" data-case="<?= $e($p['slug']) ?>" data-version="<?= $e($v['id']) ?>" data-mode="<?= $preview?'owner':'public' ?>"></section>
<p><a class="button primary" href="<?= $preview?'/#contact':'/?case='.$e($p['slug']).'#contact' ?>">Обсудить похожий проект<span>→</span></a></p>
</article>
</main>
<footer class="wrap footer"><a class="logo" href="/"><span class="spark">✳︎</span> НейроДело.</a><span>Ваша идея. Наши технологии.</span><span>© <span id="year">2026</span> НейроДело</span><a href="/">Наверх ↑</a><a class="legal-link" href="/privacy.php">Конфиденциальность</a><a class="legal-link" href="/portfolio.php">Портфолио</a><a class="legal-link" href="/reviews.php">Отзывы</a><a class="legal-link" href="/sitemap.php">Карта сайта</a><a class="owner-entry" href="/studio.php" aria-label="Вход для владельца" title="Кабинет">◈</a></footer>
<script src="/publication-gallery.js"></script><script src="/portfolio-case.js"></script></body></html>
