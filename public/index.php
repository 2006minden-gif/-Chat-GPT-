<?php
require dirname(__DIR__).'/private/app.php';
security_headers();
$pixel=nd_analytics_noscript();if($pixel!=='')echo str_replace('</body>',$pixel.'</body>',file_get_contents(__DIR__.'/index.html'));else readfile(__DIR__.'/index.html');
