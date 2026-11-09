<?php
declare(strict_types=1);
// Legacy bootstrap is intentionally closed. This also stops hosting cron jobs
// and direct old entry points left outside the new deployment allowlist.
if(PHP_SAPI==='cli'){echo '{"ok":true,"retired":true}';exit;}
http_response_code(410);header('Content-Type: text/plain; charset=utf-8');header('Cache-Control: no-store');
echo 'Этот раздел НейроДело закрыт.';exit;
