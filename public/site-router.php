<?php
declare(strict_types=1);
$path=rawurldecode(parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH)?:'/');
$pages=['/'=>'index.php','/index.php'=>'index.php','/portfolio.php'=>'portfolio.php','/portfolio-case.php'=>'portfolio-case.php','/studio.php'=>'studio.php','/portfolio-api.php'=>'portfolio-api.php'];
$assets=['/styles.css','/brand-ui.css','/publications.css','/site.css','/site.js','/portfolio-editor.js','/favicon.ico','/favicon.svg','/robots.txt','/sitemap.xml'];
if(PHP_SAPI==='cli-server'&&in_array($path,$assets,true))return false;
if(isset($pages[$path])){require __DIR__.'/'.$pages[$path];exit;}
http_response_code(preg_match('#^/(private|archive|database|scripts|manual-templates)(/|$)|(^|/)(\.|index\.html|crm\.html)|~|\.(bak|sql|key|ini)$#i',$path)?403:410);
header('Content-Type: text/html; charset=utf-8');header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
echo '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>НейроДело</title><p>Этот раздел закрыт.</p><p><a href="/">Главная</a> · <a href="/portfolio.php">Портфолио</a></p></html>';
