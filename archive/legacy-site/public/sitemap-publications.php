<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/publication/core.php';security_headers();header('Content-Type: application/xml; charset=utf-8');header('Cache-Control: no-store');
try{pub_gate();$urls=[];foreach(crm_query("SELECT * FROM nd_publications WHERE kind='portfolio' AND state='PUBLISHED' ORDER BY id") as $p){$v=pub_version((int)$p['published_version_id']);if(pub_live($p,$v))$urls[]='https://neurodelo.pro/portfolio-case.php?case='.rawurlencode($p['slug']);}}
catch(Throwable $e){http_response_code(503);echo '<?xml version="1.0" encoding="UTF-8"?><error>Карта работ временно недоступна</error>';exit;}
echo '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">';foreach($urls as $url)echo '<url><loc>'.htmlspecialchars($url,ENT_XML1|ENT_QUOTES,'UTF-8').'</loc></url>';echo '</urlset>';
