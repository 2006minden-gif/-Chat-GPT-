<?php
declare(strict_types=1);
$path=rawurldecode(parse_url($_SERVER['REQUEST_URI']??'/',PHP_URL_PATH)?:'/');
$pages=['/'=>'index.php','/index.php'=>'index.php','/portfolio.php'=>'portfolio.php','/portfolio-case.php'=>'portfolio-case.php','/studio.php'=>'studio.php','/portfolio-api.php'=>'portfolio-api.php'];
$assets=['/styles.css','/brand-ui.css','/publications.css','/site.css','/site.js','/portfolio-editor.js','/favicon.ico','/favicon.svg','/robots.txt','/sitemap.xml'];
if(PHP_SAPI==='cli-server'&&in_array($path,$assets,true))return false;
$maintenance=dirname(__DIR__).'/portfolio-transition.json';
if(is_file($maintenance)&&in_array($path,array_keys($pages),true)){
 $state=json_decode((string)file_get_contents($maintenance),true);
 if(($state['phase']??'prepare')!=='verify'||!in_array($_SERVER['REQUEST_METHOD'],['GET','HEAD'],true)){http_response_code(503);header('Retry-After: 30');header('Content-Type: text/html; charset=utf-8');echo '<!doctype html><meta charset="utf-8"><p>Обновляем портфолио. Повторите действие немного позже.</p><a href="/">Главная</a>';exit;}
}
if(isset($pages[$path])){require __DIR__.'/'.$pages[$path];exit;}
http_response_code(preg_match('#^/(private|archive|database|scripts|manual-templates)(/|$)|(^|/)(\.|index\.html|crm\.html)|~|\.(bak|sql|key|ini)$#i',$path)?403:404);
header('Content-Type: text/html; charset=utf-8');header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
echo '<!doctype html><html lang="ru"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>НейроДело</title><p>Страница не найдена.</p><p><a href="/">Главная</a> · <a href="/portfolio.php">Портфолио</a></p></html>';
