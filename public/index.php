<?php
require dirname(__DIR__).'/private/app.php';
security_headers();
readfile(__DIR__.'/index.html');
