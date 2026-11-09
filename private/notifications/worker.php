<?php
declare(strict_types=1);
// Retires any hosting cron still pointing at the old entry point. No queues run.
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
echo '{"ok":true,"retired":true,"sent":0}';
