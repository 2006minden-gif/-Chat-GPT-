<?php
require dirname(__DIR__).'/private/app.php';
security_headers();header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
readfile(__DIR__.'/crm.html');
