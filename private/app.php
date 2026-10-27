<?php
declare(strict_types=1);
function config(): array {
    static $config;
    if ($config === null) {
        $path = __DIR__ . '/config.php';
        if (!is_file($path)) fail(503, 'Сайт ещё не настроен. Напишите нам в Telegram.');
        $config = require $path;
        if(is_array($config)){require_once __DIR__.'/release-features.php';$config=nd_release_config($config);}
        if (!is_array($config) || empty($config['app_url'])) fail(503, 'Не завершена настройка сервера');
    }
    return $config;
}
function db(): PDO {
    static $pdo;
    if (!$pdo) {
        $c = config();
        $pdo = new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port'] ?? 3306).';dbname='.$c['db_name'].';charset=utf8mb4', $c['db_user'], $c['db_password'], [PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);
    }
    return $pdo;
}
function security_headers(): void {
    header('X-Content-Type-Options: nosniff');
    header('X-Frame-Options: DENY');
    header('Referrer-Policy: no-referrer');
    header("Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'");
}
function json_response(array $data, int $status=200): void {
    http_response_code($status);
    header('Content-Type: application/json; charset=utf-8');
    echo json_encode($data, JSON_UNESCAPED_UNICODE | JSON_INVALID_UTF8_SUBSTITUTE);
    exit;
}
function fail(int $status, string $message, string $code=''): void { json_response(['detail'=>$message,'error_code'=>$code], $status); }
function same_origin(): void {
    $expected = rtrim(config()['app_url'], '/');
    if (isset($_SERVER['HTTP_ORIGIN']) && $_SERVER['HTTP_ORIGIN'] !== $expected) fail(403, 'Недопустимый источник запроса');
    if (($_SERVER['HTTP_SEC_FETCH_SITE'] ?? '') === 'cross-site') fail(403, 'Недопустимый источник запроса');
}
function input(): array {
    if ((int)($_SERVER['CONTENT_LENGTH'] ?? 0) > 65536) fail(413, 'Слишком большой запрос');
    if (stripos($_SERVER['CONTENT_TYPE'] ?? '', 'application/json') !== 0) fail(415, 'Ожидается JSON');
    $body = file_get_contents('php://input', false, null, 0, 65537);
    if (strlen($body) > 65536) fail(413, 'Слишком большой запрос');
    $data = json_decode($body, true);
    if (!is_array($data) || json_last_error() !== JSON_ERROR_NONE) fail(400, 'Некорректный запрос');
    return $data;
}
function field(array $data, string $name, int $max, bool $required=true): string {
    $value = $data[$name] ?? null;
    if (!is_string($value) || !mb_check_encoding($value, 'UTF-8')) fail(422, 'Проверьте заполнение полей');
    $value = trim($value);
    if (mb_strlen($value, 'UTF-8') > $max || ($required && $value === '')) fail(422, 'Проверьте заполнение полей');
    return $value;
}
function rate(string $kind, int $max): void {
    $pdo=db(); $now=time();
    $bucket=hash('sha256', $kind.':'.($_SERVER['REMOTE_ADDR'] ?? 'unknown'));
    $pdo->prepare('DELETE FROM nd_limits WHERE expires <= ?')->execute([$now]);
    $pdo->beginTransaction();
    try {
        $pdo->prepare('INSERT INTO nd_limits (bucket,attempts,expires) VALUES (?,1,?) ON DUPLICATE KEY UPDATE attempts=attempts+1')->execute([$bucket,$now+900]);
        $q=$pdo->prepare('SELECT attempts FROM nd_limits WHERE bucket=? FOR UPDATE');$q->execute([$bucket]);$count=(int)$q->fetchColumn();
        $pdo->commit();
    } catch (Throwable $e) {if($pdo->inTransaction())$pdo->rollBack();throw $e;}
    if($count>$max) {header('Retry-After: 900');fail(429,'Слишком много попыток. Попробуйте через 15 минут.');}
}
function current_session(bool $write=false): array {
    $raw=$_COOKIE['nd_session'] ?? '';
    if (!is_string($raw) || strlen($raw)!==64) fail(401,'Войдите в CRM');
    $q=db()->prepare('SELECT * FROM nd_sessions WHERE token=? AND expires>?');$q->execute([hash('sha256',$raw),time()]);$row=$q->fetch();
    if(!$row)fail(401,'Войдите в CRM');
    if($write) {
        same_origin();
        if(!hash_equals($row['csrf'],$_SERVER['HTTP_X_CSRF_TOKEN'] ?? ''))fail(403,'Обновите страницу и повторите действие');
    }
    return $row;
}
function session_cookie(string $token, int $expiry): void {
    setcookie('nd_session',$token,['expires'=>$expiry,'path'=>'/','secure'=>parse_url(config()['app_url'],PHP_URL_SCHEME)==='https','httponly'=>true,'samesite'=>'Strict']);
}
function statuses(): array {return ['Новая','Обсуждаем','В работе','Завершена','Отказ'];}
function server_error(Throwable $e): void {
    $id=bin2hex(random_bytes(8));
    // Only metadata: no exception messages, SQL, parameters, credentials or request bodies.
    $meta=['event'=>'backend_failure','id'=>$id,'type'=>get_class($e),
           'file'=>basename($e->getFile()),'line'=>$e->getLine()];
    if($e instanceof PDOException)$meta['sqlstate']=$e->getCode();
    error_log('NeuroDelo '.json_encode($meta,JSON_UNESCAPED_SLASHES));
    header('X-Request-ID: '.$id);
    fail(503,'Сервис временно недоступен. Попробуйте позже или напишите в Telegram.');
}
function valid_contact(string $contact): bool {
    if (filter_var($contact, FILTER_VALIDATE_EMAIL)!==false) return true;
    if (preg_match('#^https://max\.ru/u/[A-Za-z0-9_-]{1,180}$#D',$contact)) return true;
    if (preg_match('/^@[A-Za-z][A-Za-z0-9_]{4,31}$/D', $contact)) return true;
    // Supported telephone region: Russia, +7/8 + 10 digits (area/mobile codes 3,4,8,9).
    if (!preg_match('/^\+?[0-9 ()-]+$/D',$contact)) return false;
    $digits=preg_replace('/[^0-9]/','',$contact);
    if(str_starts_with($contact,'+') && !str_starts_with($digits,'7'))return false;
    return (bool)preg_match('/^[78][3489][0-9]{9}$/D',$digits);
}
/** Owner-authorized, versioned public legal documents; contains no secrets. */
function release_legal_documents(): array {
    $file=__DIR__.'/legal/privacy-2026-10-27-v2.json';
    $raw=@file_get_contents($file);
    $data=$raw===false ? null : json_decode($raw,true);
    if (!is_array($data) || ($data['version']??'')!=='privacy-2026-10-27-v2'
        || ($data['activation_requested']??false)!==true) return [];
    foreach(['policy','consent','owner','address','contact'] as $key) {
        if (!is_string($data[$key]??null) || trim($data[$key])==='') return [];
    }
    return $data;
}
function privacy_document(): array {
    $c=config();$version=$c['privacy_policy_version'] ?? '';
    $disabled=['settings'=>['enabled'=>false,'version'=>'','url'=>'/privacy.php','hash'=>''],'text'=>''];
    // An explicit emergency stop always wins. Existing configured policies retain authority.
    if (($c['privacy_policy_disabled']??false)===true) return $disabled;
    if ($version==='') {
        $legal=release_legal_documents();
        if (!$legal) return $disabled;
        return ['settings'=>['enabled'=>true,'version'=>$legal['version'],'url'=>'/privacy.php',
            'hash'=>hash('sha256',$legal['policy']."\nCONSENT\n".$legal['consent'])],'text'=>$legal['policy']];
    }
    if (($c['privacy_policy_approved'] ?? false)!==true || !is_string($version)
        || !preg_match('/^[A-Za-z0-9._-]{1,64}$/D',$version)) return $disabled;
    $file=__DIR__.'/privacy-policy.txt';
    if (!is_file($file)) return $disabled;
    // A failed read returns false. Never pass it to trim/hash under strict PHP 8.
    // Suppress the filesystem warning (which can contain a private path), log only a fixed event.
    $text=@file_get_contents($file);
    if ($text===false) {
        error_log('NeuroDelo {"event":"privacy_policy_unreadable"}');
        return $disabled;
    }
    if (trim($text)==='') return $disabled;
    return ['settings'=>['enabled'=>true,'version'=>$version,'url'=>'/privacy.php','hash'=>hash('sha256',$text)],'text'=>$text];
}
function privacy_settings(): array {
    return privacy_document()['settings'];
}
