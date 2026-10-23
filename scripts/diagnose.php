<?php
/** Read-only CLI diagnostics. Keep outside public_html. Never prints configuration values. */
declare(strict_types=1);
if (PHP_SAPI !== 'cli') { http_response_code(404); exit; }
ini_set('display_errors', '0');
$results=[];
function check_result(string $check, bool $ok, array $extra=[]): void {
    global $results;
    $results[]=['check'=>$check,'ok'=>$ok]+$extra;
}
function diagnostic_failure(string $check, Throwable $e): void {
    // Fixed metadata only: exception messages can contain passwords, SQL and paths.
    $meta=['type'=>get_class($e),'file'=>basename($e->getFile()),'line'=>$e->getLine()];
    if ($e instanceof PDOException) $meta['sqlstate']=(string)$e->getCode();
    check_result($check,false,$meta);
}
check_result('php_version', PHP_VERSION_ID>=80400, ['version'=>PHP_VERSION]);
foreach (['pdo_mysql','mbstring'] as $extension) check_result('extension_'.$extension,extension_loaded($extension));
$path=dirname(__DIR__).'/private/config.php';
check_result('config_readable',is_file($path) && is_readable($path));
if (is_file($path) && is_readable($path)) {
    try {
        $config=require $path;
        if (!is_array($config)) throw new RuntimeException('Invalid configuration');
        $valid=true;
        foreach (['app_url','db_host','db_name','db_user','db_password'] as $key) {
            if (!isset($config[$key]) || !is_string($config[$key])) $valid=false;
        }
        check_result('config_structure',$valid);
        check_result('https_url',is_string($config['app_url'] ?? null) && parse_url($config['app_url'],PHP_URL_SCHEME)==='https');
        check_result('setup_disabled',empty($config['setup_key']));
        $policy=dirname(__DIR__).'/private/privacy-policy.txt';
        $approved=($config['privacy_policy_approved'] ?? false)===true;
        $version=$config['privacy_policy_version'] ?? '';
        $versionValid=is_string($version) && preg_match('/^[A-Za-z0-9._-]{1,64}$/D',$version)===1;
        $text=is_file($policy) ? @file_get_contents($policy) : false;
        check_result('privacy_configuration',!$approved || ($versionValid && is_string($text) && trim($text)!==''),
            ['approved'=>$approved,'file_readable'=>is_string($text),'version_valid'=>$versionValid]);
        if ($valid) {
            try {
                $pdo=new PDO('mysql:host='.$config['db_host'].';port='.($config['db_port'] ?? 3306).';dbname='.$config['db_name'].';charset=utf8mb4',
                    $config['db_user'],$config['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false]);
                $pdo->exec('SET SESSION TRANSACTION READ ONLY');
                check_result('database_connection',true);
                foreach ([
                    'nd_admin'=>'id,password_hash',
                    'nd_leads'=>'id,name,contact,service,idea,status,notes,next_step,created,version,request_key,request_hash,consent,consent_at,policy_version,policy_hash',
                    'nd_sessions'=>'token,csrf,expires',
                    'nd_limits'=>'bucket,attempts,expires',
                ] as $table=>$columns) {
                    try { $pdo->query('SELECT '.$columns.' FROM '.$table.' LIMIT 0'); check_result('schema_'.$table,true); }
                    catch (Throwable $e) { diagnostic_failure('schema_'.$table,$e); }
                }
                $exists=(bool)$pdo->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn();
                check_result('administrator_exists',$exists);
            } catch (Throwable $e) { diagnostic_failure('database',$e); }
        }
    } catch (Throwable $e) { diagnostic_failure('config_load',$e); }
}
echo json_encode($results,JSON_UNESCAPED_UNICODE|JSON_PRETTY_PRINT|JSON_INVALID_UTF8_SUBSTITUTE),PHP_EOL;
exit(in_array(false,array_column($results,'ok'),true)?1:0);
