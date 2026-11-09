<?php
require dirname(__DIR__).'/private/site.php';require dirname(__DIR__).'/private/site-view.php';security_headers();
$html=file_get_contents(__DIR__.'/index.html');ob_start();
try{$items=[];foreach(query("SELECT * FROM nd_publications WHERE kind='portfolio' AND state='PUBLISHED' ORDER BY sort_order,id DESC")->fetchAll() as $p)if(site_live($p)){$item=site_item($p);if(($item['body']['featured']??false)===true)$items[]=$item;}
if($items){echo '<section class="section wrap" id="portfolio"><h2>Выбранные работы.</h2><div class="publication-grid">';foreach(array_slice($items,0,3) as $item)site_card($item);echo '</div><p><a href="/portfolio.php">Всё портфолио →</a></p></section>';}}
catch(Throwable $e){echo '<section class="wrap"><p><a href="/portfolio.php">Открыть портфолио →</a></p></section>';}
echo str_replace('<!-- PORTFOLIO -->',ob_get_clean(),$html);
