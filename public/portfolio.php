<?php
declare(strict_types=1);require dirname(__DIR__).'/private/site.php';require dirname(__DIR__).'/private/site-view.php';security_headers();
$items=[];$unavailable=false;try{foreach(query("SELECT * FROM nd_publications WHERE kind='portfolio' AND state='PUBLISHED' ORDER BY sort_order,id DESC")->fetchAll() as $p)if(site_live($p))$items[]=site_item($p);}catch(Throwable $e){$unavailable=true;http_response_code(503);}
site_header('Портфолио');?>
<main class="wrap site-main"><span class="eyebrow">РАБОТЫ НЕЙРОДЕЛО</span><h1>Портфолио <span class="serif">проектов.</span></h1><p class="guide-intro">Сайты, приложения и ИИ-агенты.</p><section class="publication-grid">
<?php foreach($items as $item)site_card($item);if(!$items): ?><p><?= $unavailable?'Портфолио временно недоступно. Попробуйте открыть его позже.':'Новые работы скоро появятся здесь.' ?></p><?php endif; ?>
</section><p class="site-contact"><a class="button primary" href="/#contact">Обсудить похожий проект →</a></p></main><?php site_footer(); ?>
