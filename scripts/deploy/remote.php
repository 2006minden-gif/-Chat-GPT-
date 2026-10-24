<?php
/** Private CLI deployment agent. Only allowlisted code files; never imports test data. */
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
ini_set('display_errors','0');umask(0077);
final class DeployFailure extends RuntimeException {}
function insist(bool $condition,string $code):void {if(!$condition)throw new DeployFailure($code);}
function read_json(string $path):array {
    insist(is_file($path)&&!is_link($path),'metadata_missing');
    $value=json_decode((string)file_get_contents($path),true,512,JSON_THROW_ON_ERROR);
    insist(is_array($value),'invalid_metadata');return $value;
}
function save_json(string $path,array $value):void {
    if(basename($path)==='backup.json'&&!isset($value['created_at']))$value['created_at']=microtime(true);
    $tmp=$path.'.tmp';insist(!is_link($path)&&!is_link($tmp),'unsafe_metadata_path');
    insist(file_put_contents($tmp,json_encode($value,JSON_PRETTY_PRINT|JSON_UNESCAPED_SLASHES),LOCK_EX)!==false,'metadata_write_failed');
    chmod($tmp,0600);insist(rename($tmp,$path),'metadata_rename_failed');
}
function paths():array {
    $public=['.htaccess','api-client.js','api.php','crm.css','crm.html','crm.js','index.html','index.php','privacy.php','script.js','studio.php','styles.css'];
    return array_merge(array_map(fn($p)=>'public_html/'.$p,$public),['private/.htaccess','private/app.php']);
}
function hash_file_safe(string $path):?string {
    insist(!is_link($path),'symlink_refused');
    if(!file_exists($path))return null;
    insist(is_file($path)&&is_readable($path),'non_regular_file');return hash_file('sha256',$path);
}
function protected_files(string $root):array {
    return ['private/config.php'=>hash_file_safe($root.'/private/config.php'),'private/privacy-policy.txt'=>hash_file_safe($root.'/private/privacy-policy.txt')];
}
function assert_protected(string $root,array $before):void {insist(protected_files($root)===$before,'protected_file_changed');}
function preflight(string $root):array {
    insist(PHP_VERSION_ID>=80400,'php_84_required');
    insist(extension_loaded('pdo_mysql')&&extension_loaded('mbstring')&&function_exists('proc_open'),'php_capability_missing');
    foreach(['public_html','private'] as $name)insist(is_dir($root.'/'.$name)&&!is_link($root.'/'.$name)&&is_writable($root.'/'.$name),'unsafe_application_directory');
    foreach(paths() as $path)hash_file_safe($root.'/'.$path);
    $protected=protected_files($root);insist($protected['private/config.php']!==null,'config_missing');
    $c=require $root.'/private/config.php';insist(is_array($c),'invalid_configuration');
    foreach(['db_host','db_name','db_user','db_password','app_url'] as $key)insist(isset($c[$key])&&is_string($c[$key]),'invalid_configuration');
    insist(rtrim($c['app_url'],'/')==='https://neurodelo.pro','unexpected_application_url');
    $pdo=new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $pdo->exec('SET SESSION TRANSACTION READ ONLY');
    $pdo->query('SELECT id,password_hash FROM nd_admin LIMIT 0');
    $pdo->query('SELECT id,version,request_key,request_hash,consent,consent_at,policy_version,policy_hash FROM nd_leads LIMIT 0');
    $pdo->query('SELECT token,csrf,expires FROM nd_sessions LIMIT 0');$pdo->query('SELECT bucket,attempts,expires FROM nd_limits LIMIT 0');
    return ['ok'=>true,'php'=>PHP_VERSION,'database_connected'=>true,'admin_exists'=>(bool)$pdo->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn(),
            'privacy_approved'=>($c['privacy_policy_approved']??false)===true];
}
function remove_tree(string $path):void {
    insist(!is_link($path),'symlink_refused');
    if(is_dir($path)) {foreach(scandir($path) as $name)if($name!=='.'&&$name!=='..')remove_tree($path.'/'.$name);insist(rmdir($path),'cleanup_failed');}
    elseif(file_exists($path))insist(unlink($path),'cleanup_failed');
}
function verify_bundle(string $candidate,string $id):array {
    $m=read_json($candidate.'/manifest.json');
    insist(($m['schema_version']??0)===1&&preg_match('/^[a-f0-9]{40}$/D',$m['revision']??'')===1,'invalid_manifest');
    $actual=array_keys($m['files']??[]);$expected=paths();sort($actual);sort($expected);insist($actual===$expected,'release_allowlist_mismatch');
    insist(($m['keep_backups']??0)>=2&&($m['keep_backups']??0)<=20,'invalid_retention');
    foreach(array_merge($m['files'],$m['tools']) as $path=>$hash) {
        insist(preg_match('#^(public_html/[A-Za-z0-9_.-]+|private/(app.php|\.htaccess)|remote.php|scripts/migrate.php|database/migrations/[0-9]{3}_[a-z_]+/(up|down)\.sql)$#D',$path)===1,'unsafe_release_path');
        insist(is_string($hash)&&preg_match('/^[a-f0-9]{64}$/D',$hash)===1&&hash_file_safe($candidate.'/'.$path)===$hash,'release_checksum_mismatch');
    }
    $allowed=array_merge(array_keys($m['files']),array_keys($m['tools']),['manifest.json','baseline.json']);
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($candidate,FilesystemIterator::SKIP_DOTS));
    foreach($iterator as $file) {insist(!$file->isLink(),'symlink_refused');if($file->isFile())insist(in_array(substr($file->getPathname(),strlen($candidate)+1),$allowed,true),'unexpected_release_file');}
    return $m;
}
function atomic_copy(string $source,string $destination,string $id,int $mode=0644):void {
    insist(!is_link($destination),'symlink_refused');
    $tmp=dirname($destination).'/.nd-'.$id.'-'.basename($destination).'.tmp';
    insist(!file_exists($tmp)&&!is_link($tmp),'temporary_file_collision');
    try {insist(copy($source,$tmp),'file_copy_failed');chmod($tmp,$mode);insist(hash_file('sha256',$source)===hash_file('sha256',$tmp),'copy_checksum_mismatch');insist(rename($tmp,$destination),'file_rename_failed');}
    finally {if(is_file($tmp)&&!is_link($tmp))unlink($tmp);}
}
function prune(string $stateRoot,array $state,int $keep):void {
    $base=$stateRoot.'/backups';$valid=[];
    foreach(glob($base.'/*',GLOB_ONLYDIR) as $dir) {
        if(is_link($dir)||!preg_match('/^[a-zA-Z0-9_-]{1,120}$/D',basename($dir))||!is_file($dir.'/backup.json'))continue;
        $metadata=read_json($dir.'/backup.json');$valid[basename($dir)]=(float)($metadata['created_at']??filemtime($dir.'/backup.json'));
    }
    arsort($valid);$preserve=array_slice(array_keys($valid),0,$keep);
    foreach(['known_good_backup','database_recovery_backup','active','last_release'] as $key)if(!empty($state[$key]))$preserve[]=$state[$key];
    foreach($valid as $id=>$unused)if(!in_array($id,$preserve,true)) {
        remove_tree($base.'/'.$id);
        $incoming=$stateRoot.'/incoming/'.$id;
        if(is_dir($incoming)&&!is_link($incoming))remove_tree($incoming);
    }
}
function execute_private(array $command,string $stdoutPath):void {
    $error=$stdoutPath.'.error';$p=proc_open($command,[0=>['file','/dev/null','r'],1=>['file',$stdoutPath,'w'],2=>['file',$error,'w']],$pipes);
    insist(is_resource($p),'subprocess_start_failed');$code=proc_close($p);chmod($stdoutPath,0600);if(is_file($error))chmod($error,0600);
    insist($code===0,'private_subprocess_failed');
}
function migrate_approved(string $root,string $candidate,array $m,string $backup):array {
    $entries=$m['migrations']??[];if(!$entries)return [];
    $c=require $root.'/private/config.php';
    $pdo=new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $exists=(bool)$pdo->query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='nd_schema_migrations'")->fetchColumn();
    $pending=[];
    foreach($entries as $entry) {
        insist(is_bool($entry['automatic']??null)&&is_bool($entry['required']??null)&&preg_match('/^[0-9]{3}_[a-z_]+$/D',$entry['version']??'')===1,'invalid_migration_approval');
        foreach(['up','down'] as $direction)insist(hash_file_safe($candidate.'/database/migrations/'.$entry['version'].'/'.$direction.'.sql')===($entry[$direction.'_sha256']??null),'migration_checksum_mismatch');
        $row=false;if($exists){$q=$pdo->prepare('SELECT * FROM nd_schema_migrations WHERE version=?');$q->execute([$entry['version']]);$row=$q->fetch(PDO::FETCH_ASSOC);}
        if($row){insist($row['state']==='applied'&&$row['up_checksum']===$entry['up_sha256']&&$row['down_checksum']===$entry['down_sha256'],'migration_state_or_checksum_mismatch');continue;}
        if(!$entry['automatic']){insist(!$entry['required'],'manual_migration_approval_required');continue;}
        insist($entry['version']==='004_crm_foundation'&&$entry['kind']==='additive','unapproved_automatic_migration');
        $up=(string)file_get_contents($candidate.'/database/migrations/'.$entry['version'].'/up.sql');
        $sql=preg_replace('/^--[^\n]*$/m','',$up);$statements=array_values(array_filter(array_map('trim',explode(';',$sql))));
        insist(count($statements)===12,'unsupported_automatic_migration');
        foreach($statements as $statement)insist(preg_match('/^CREATE TABLE nd_[a-z_]+\s*\([\s\S]+\)\s*ENGINE=InnoDB[\s\S]*$/D',$statement)===1,'destructive_migration_refused');
        $pending[]=$entry['version'];
    }
    if(!$pending)return [];
    // credentials are read from the existing protected config, never from GitHub or command arguments.
    $defaults=$backup.'/.mysql-client.cnf';
    $quote=static fn($v)=>'"'.str_replace(["\\","\"","\n","\r"],["\\\\","\\\"","\\n","\\r"],(string)$v).'"';
    $text="[client]\n";foreach(['host'=>$c['db_host'],'port'=>$c['db_port']??3306,'user'=>$c['db_user'],'password'=>$c['db_password']] as $key=>$value)$text.=$key.'='.$quote($value)."\n";
    insist(file_put_contents($defaults,$text)!==false,'database_backup_config_failed');chmod($defaults,0600);
    try {
        $size=(int)$pdo->query('SELECT COALESCE(SUM(data_length+index_length),0) FROM information_schema.tables WHERE table_schema=DATABASE()')->fetchColumn();
        insist(disk_free_space($backup)>max(16777216,$size*2),'insufficient_database_backup_space');
        $help=proc_open(['mysqldump','--help'],[0=>['file','/dev/null','r'],1=>['pipe','w'],2=>['file','/dev/null','w']],$helpPipes);
        insist(is_resource($help),'dump_client_unavailable');$options=(string)stream_get_contents($helpPipes[1],1048576);fclose($helpPipes[1]);insist(proc_close($help)===0,'dump_client_unavailable');
        insist(str_contains($options,'no-tablespaces'),'dump_client_not_supported');
        $command=['mysqldump','--defaults-extra-file='.$defaults,'--single-transaction','--quick','--skip-lock-tables','--no-tablespaces'];
        if(str_contains($options,'set-gtid-purged'))$command[]='--set-gtid-purged=OFF';
        if(str_contains($options,'column-statistics'))$command[]='--column-statistics=0';
        $command[]='--databases';$command[]=$c['db_name'];execute_private($command,$backup.'/database.sql');
        insist(filesize($backup.'/database.sql')>0,'empty_database_backup');
        save_json($backup.'/database.json',['sha256'=>hash_file('sha256',$backup.'/database.sql'),'restore'=>'operator-approved only; never auto-import']);
        $statePath=dirname(dirname($backup)).'/state.json';$state=read_json($statePath);$state['database_recovery_backup']=basename($backup);save_json($statePath,$state);
    } finally {if(is_file($defaults))unlink($defaults);}
    $configLink=$candidate.'/private/config.php';insist(!file_exists($configLink)&&!is_link($configLink),'candidate_config_collision');
    insist(symlink($root.'/private/config.php',$configLink),'candidate_config_link_failed');
    try {
        execute_private([getenv('NEURO_PHP_BIN')?:PHP_BINARY,$candidate.'/scripts/migrate.php','up'],$backup.'/migration.log');
        // Confirm persistence in the migration journal, not only a successful process exit.
        foreach($entries as $entry)if(in_array($entry['version'],$pending,true)) {
            $q=$pdo->prepare('SELECT state,up_checksum,down_checksum FROM nd_schema_migrations WHERE version=?');$q->execute([$entry['version']]);$row=$q->fetch(PDO::FETCH_ASSOC);
            insist($row&&$row['state']==='applied'&&$row['up_checksum']===$entry['up_sha256']&&$row['down_checksum']===$entry['down_sha256'],'migration_persistence_not_confirmed');
        }
        // Never execute down or import this database dump automatically.
    } finally {if(is_link($configLink))unlink($configLink);}
    return $pending;
}
function rollback(string $root,string $stateRoot,array &$state,string $id):array {
    insist(preg_match('/^[a-zA-Z0-9_-]{1,120}$/D',$id)===1,'invalid_release_id');
    $protectedNow=protected_files($root);
    $backup=$stateRoot.'/backups/'.$id;$meta=read_json($backup.'/backup.json');
    insist(array_keys($meta['files'])===paths(),'backup_allowlist_mismatch');
    // Validate the entire rollback before touching any destination.
    foreach($meta['files'] as $path=>$entry) {
        $current=hash_file_safe($root.'/'.$path);
        insist($current===$entry['before']||$current===$entry['candidate'],'rollback_conflicting_manual_change');
        if($entry['before']!==null)insist(hash_file_safe($backup.'/files/'.$path)===$entry['before'],'backup_checksum_mismatch');
    }
    foreach($meta['files'] as $path=>$entry) {
        if(hash_file_safe($root.'/'.$path)===$entry['before'])continue;
        if($entry['before']===null)insist(unlink($root.'/'.$path),'rollback_remove_failed');
        else atomic_copy($backup.'/files/'.$path,$root.'/'.$path,$id,(int)$entry['mode']);
    }
    foreach($meta['files'] as $path=>$entry)insist(hash_file_safe($root.'/'.$path)===$entry['before'],'rollback_file_verification_failed');
    assert_protected($root,$protectedNow);
    $state['active']=null;$state['last_result']='files_restored_health_unverified';$state['rollback_pending']=$id;save_json($stateRoot.'/state.json',$state);
    return ['ok'=>true,'files_restored'=>true,'health_verified'=>false,'baseline'=>$meta['baseline'],'id'=>$id];
}
$lock=null;
try {
    $op=$argv[1]??'';$root=$argv[2]??'';$id=$argv[3]??'';
    insist(in_array($op,['preflight','apply','finalize','mark-unhealthy','rollback','recover','confirm-rollback'],true),'invalid_operation');
    insist(is_dir($root)&&!is_link($root)&&realpath($root)===$root,'invalid_account_root');
    if($op==='preflight') {echo json_encode(preflight($root),JSON_UNESCAPED_SLASHES),PHP_EOL;exit;}
    insist(preg_match('/^[a-zA-Z0-9_-]{1,120}$/D',$id)===1,'invalid_release_id');
    $stateRoot=$root.'/.neurodelo-deploy';
    foreach(['incoming','backups'] as $directory)insist(!is_link($stateRoot.'/'.$directory),'symlink_refused');
    insist(is_dir($stateRoot)&&!is_link($stateRoot),'deployment_directory_missing');
    $lock=fopen($stateRoot.'/lock','c');insist(is_resource($lock)&&flock($lock,LOCK_EX|LOCK_NB),'deployment_busy');chmod($stateRoot.'/lock',0600);
    $state=is_file($stateRoot.'/state.json')?read_json($stateRoot.'/state.json'):[];
    if($op==='rollback'||$op==='recover') {
        $target=$op==='rollback'?$id:($state['active']??$state['last_release']??null);
        insist(is_string($target),'no_recovery_point');
        if($op==='rollback')insist(($state['active']??null)===$id||($state['last_release']??null)===$id,'release_writes_not_started');
        $result=rollback($root,$stateRoot,$state,$target);
    } elseif($op==='confirm-rollback') {
        insist(($state['last_result']??'')==='files_restored_health_unverified'&&($state['rollback_pending']??'')===$id,'rollback_not_pending');
        $state['last_result']='rollback_verified_to_baseline';save_json($stateRoot.'/state.json',$state);
        $result=['ok'=>true,'rollback_verified_to_baseline'=>true];
    } elseif($op==='finalize'||$op==='mark-unhealthy') {
        insist(($state['active']??'')===$id,'release_not_pending');$meta=read_json($stateRoot.'/backups/'.$id.'/backup.json');
        foreach($meta['files'] as $path=>$entry)insist(hash_file_safe($root.'/'.$path)===$entry['candidate'],'published_file_verification_failed');
        assert_protected($root,$meta['protected']);
        $after=read_json($stateRoot.'/incoming/'.$id.'/after-health.json');
        if($op==='mark-unhealthy') {
            $before=$meta['baseline'];insist(($before['ok']??true)===false&&($before['complete']??false)===true&&($after['ok']??true)===false&&($after['complete']??false)===true,'preexisting_failure_evidence_required');
            insist(array_keys($before['checks'])===array_keys($after['checks']),'health_check_set_changed');
            foreach($after['checks'] as $path=>$check)if(!$check['ok']) {
                insist(!$before['checks'][$path]['ok'],'new_regression_requires_rollback');
                foreach(['status','content_type','enabled','version','redirected','sha256'] as $key)insist(($check[$key]??null)===($before['checks'][$path][$key]??null),'new_regression_requires_rollback');
            }
            $state['active']=null;$state['last_release']=$id;$state['last_result']='unhealthy_preexisting';save_json($stateRoot.'/state.json',$state);prune($stateRoot,$state,(int)$meta['keep_backups']);
            echo json_encode(['ok'=>true,'healthy'=>false,'known_good_advanced'=>false]),PHP_EOL;exit;
        }
        insist(($after['ok']??false)===true&&($after['complete']??false)===true,'successful_health_evidence_required');
        $goodId='good-'.$id;$good=$stateRoot.'/backups/'.$goodId;insist(!file_exists($good)&&mkdir($good,0700),'good_snapshot_failed');
        $goodEntries=[];
        foreach($meta['files'] as $path=>$entry) {
            if(!is_dir(dirname($good.'/files/'.$path)))mkdir(dirname($good.'/files/'.$path),0700,true);
            insist(copy($root.'/'.$path,$good.'/files/'.$path),'good_snapshot_failed');chmod($good.'/files/'.$path,0600);
            insist(hash_file_safe($good.'/files/'.$path)===$entry['candidate'],'good_snapshot_checksum_failed');
            $goodEntries[$path]=['before'=>$entry['candidate'],'candidate'=>$entry['candidate'],'mode'=>fileperms($root.'/'.$path)&0777];
        }
        save_json($good.'/backup.json',['revision'=>$meta['revision'],'files'=>$goodEntries,'protected'=>protected_files($root),'baseline'=>$after,'keep_backups'=>$meta['keep_backups']]);
        $state['known_good_backup']=$goodId;$state['active']=null;$state['last_release']=$id;$state['last_result']='healthy';save_json($stateRoot.'/state.json',$state);
        prune($stateRoot,$state,(int)$meta['keep_backups']);$result=['ok'=>true,'revision'=>$meta['revision'],'files_verified'=>true];
    } else {
        insist(empty($state['active']),'unfinished_release_requires_recovery');preflight($root);
        $candidate=$stateRoot.'/incoming/'.$id;insist(is_dir($candidate)&&!is_link($candidate),'candidate_missing');
        $m=verify_bundle($candidate,$id);$baseline=read_json($candidate.'/baseline.json');
        // baseline.json is uploaded separately after immutable bundle validation by the client.
        $protected=protected_files($root);$backup=$stateRoot.'/backups/'.$id;
        insist(!file_exists($backup)&&!is_link($backup),'backup_already_exists');
        if(!is_dir($stateRoot.'/backups'))mkdir($stateRoot.'/backups',0700);
        prune($stateRoot,$state,(int)$m['keep_backups']);
        $space=0;foreach(paths() as $path)if(is_file($root.'/'.$path))$space+=filesize($root.'/'.$path);
        insist(disk_free_space($stateRoot)>$space*2+8388608,'insufficient_backup_space');
        insist(mkdir($backup,0700),'backup_directory_failed');$entries=[];
        foreach(paths() as $path) {
            $before=hash_file_safe($root.'/'.$path);$entries[$path]=['before'=>$before,'candidate'=>$m['files'][$path],'mode'=>$before!==null?(fileperms($root.'/'.$path)&0777):0644];
            if($before!==null) {if(!is_dir(dirname($backup.'/files/'.$path)))mkdir(dirname($backup.'/files/'.$path),0700,true);insist(copy($root.'/'.$path,$backup.'/files/'.$path),'backup_copy_failed');chmod($backup.'/files/'.$path,0600);insist(hash_file_safe($backup.'/files/'.$path)===$before,'backup_checksum_mismatch');}
        }
        $meta=['revision'=>$m['revision'],'files'=>$entries,'protected'=>$protected,'baseline'=>$baseline,'keep_backups'=>$m['keep_backups']];
        save_json($backup.'/backup.json',$meta);
        $state['active']=$id;if(($baseline['ok']??false)===true)$state['known_good_backup']=$id;save_json($stateRoot.'/state.json',$state);
        $migrated=migrate_approved($root,$candidate,$m,$backup);
        foreach(paths() as $path)atomic_copy($candidate.'/'.$path,$root.'/'.$path,$id);
        assert_protected($root,$protected);
        $result=['ok'=>true,'applied'=>true,'revision'=>$m['revision'],'migrations'=>$migrated,'baseline_healthy'=>$baseline['ok']??false];
    }
    echo json_encode($result,JSON_UNESCAPED_SLASHES),PHP_EOL;
} catch(Throwable $e) {
    echo json_encode(['ok'=>false,'error'=>$e instanceof DeployFailure?$e->getMessage():'private_operation_failed','type'=>get_class($e),'file'=>basename($e->getFile()),'line'=>$e->getLine(),'writes_started'=>isset($state)&&(($state['active']??null)===$id||($state['last_release']??null)===$id)],JSON_UNESCAPED_SLASHES),PHP_EOL;exit(1);
} finally {if(is_resource($lock)){flock($lock,LOCK_UN);fclose($lock);}}
