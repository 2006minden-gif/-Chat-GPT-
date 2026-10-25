<?php
require dirname(__DIR__).'/private/app.php';
security_headers();
$html=file_get_contents(__DIR__.'/index.html');if((config()['catalog_enabled']??false)===true)$html=preg_replace('~</nav>~','<a href="/catalog.php">Каталог услуг</a></nav>',$html,1);echo $html;
