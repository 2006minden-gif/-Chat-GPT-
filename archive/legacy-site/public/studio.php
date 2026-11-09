<?php
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
require_once dirname(__DIR__).'/private/owner-navigation.php';
ob_start();owner_navigation(true);$navigation=ob_get_clean();
$html=file_get_contents(__DIR__.'/crm.html');
echo preg_replace('~<nav class="owner-tools".*?</nav>~s',$navigation,$html,1);
