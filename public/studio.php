<?php
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
$html=file_get_contents(__DIR__.'/crm.html');
if((config()['crm_operations_enabled']??false)===true)$html=str_replace('<main class="wrap">','<main class="wrap"><p><a href="/workspace.php">Открыть рабочую CRM →</a></p>',$html);
echo $html;
