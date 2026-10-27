<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
require dirname(__DIR__).'/app.php';require __DIR__.'/max.php';
try{echo json_encode(max_pump(10));}
catch(Throwable $e){echo '{"ok":false,"error":"notification_worker_failed"}';exit(1);}
