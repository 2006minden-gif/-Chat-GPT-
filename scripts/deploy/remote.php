<?php
/** Private CLI deployment agent. Only allowlisted code files; never imports test data. */
declare(strict_types=1);
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
ini_set('display_errors','0');ini_set('serialize_precision','-1');umask(0077);
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
    return ['public_html/.htaccess', 'public_html/ai-public-api.php', 'public_html/ai-widget.js', 'public_html/ai.css', 'public_html/ai.js', 'public_html/ai.php', 'public_html/api-client.js', 'public_html/api.php', 'public_html/billing.css', 'public_html/billing.js', 'public_html/billing.php', 'public_html/catalog-api.php', 'public_html/catalog-owner.js', 'public_html/catalog-owner.php', 'public_html/catalog.css', 'public_html/catalog.js', 'public_html/catalog.php', 'public_html/client-settings.js', 'public_html/client-settings.php', 'public_html/collab-download.php', 'public_html/collab-print.js', 'public_html/collab-print.php', 'public_html/collaboration.css', 'public_html/collaboration.js', 'public_html/collaboration.php', 'public_html/consent.php', 'public_html/contract-settings.js', 'public_html/contract-settings.php', 'public_html/crm.css', 'public_html/crm.html', 'public_html/crm.js', 'public_html/customer-api.php', 'public_html/customer-owner.js', 'public_html/customer-privacy.php', 'public_html/customer.css', 'public_html/customer.js', 'public_html/customer.php', 'public_html/documents.js', 'public_html/documents.php', 'public_html/favicon.ico', 'public_html/favicon.svg', 'public_html/finance.js', 'public_html/finance.php', 'public_html/handoff.js', 'public_html/handoff.php', 'public_html/help.php', 'public_html/index.html', 'public_html/index.php', 'public_html/invoice-document.php', 'public_html/lifecycle-api.php', 'public_html/manual-invoice.php', 'public_html/max-api.php', 'public_html/max-app.js', 'public_html/max-link.js', 'public_html/max-link.php', 'public_html/max-settings.js', 'public_html/max-webhook.php', 'public_html/max.php', 'public_html/operations.css', 'public_html/operations.js', 'public_html/order-workflow-api.php', 'public_html/order-workflow.js', 'public_html/order-workflow.php', 'public_html/ordering.js', 'public_html/ordering.php', 'public_html/orders.js', 'public_html/orders.php', 'public_html/owner-context.js', 'public_html/owner-schedule-editor.js', 'public_html/owner-setup.js', 'public_html/owner-setup.php', 'public_html/payment-webhook.php', 'public_html/portal.js', 'public_html/portal.php', 'public_html/portfolio-case.js', 'public_html/portfolio-case.php', 'public_html/portfolio-entry.js', 'public_html/portfolio-home.js', 'public_html/portfolio.php', 'public_html/pricing.js', 'public_html/privacy.php', 'public_html/production.css', 'public_html/production.js', 'public_html/production.php', 'public_html/prospect-api.php', 'public_html/prospect-owner.js', 'public_html/prospect-owner.php', 'public_html/prospect.js', 'public_html/prospect.php', 'public_html/publication-api.php', 'public_html/publication-gallery.js', 'public_html/publication-owner.js', 'public_html/publication-owner.php', 'public_html/publication-permission-entry.js', 'public_html/publication-permissions.js', 'public_html/publication-permissions.php', 'public_html/publications.css', 'public_html/publications.js', 'public_html/reviews.php', 'public_html/robots.txt', 'public_html/script.js', 'public_html/services.php', 'public_html/services/guide.css', 'public_html/services/guide.js', 'public_html/sitemap-publications.php', 'public_html/sitemap.php', 'public_html/sitemap.xml', 'public_html/studio.php', 'public_html/styles.css', 'public_html/support-api.php', 'public_html/support.js', 'public_html/support.php', 'public_html/workspace.php', 'private/.htaccess', 'private/ai/approvals.php', 'private/ai/context.php', 'private/ai/core.php', 'private/ai/engine.php', 'private/ai/provider.php', 'private/ai/public.php', 'private/ai/read.php', 'private/ai/registry.php', 'private/ai/routes.php', 'private/ai/rules.php', 'private/ai/schema.php', 'private/ai/tasks.php', 'private/app.php', 'private/billing/core.php', 'private/billing/hooks.php', 'private/billing/invoices.php', 'private/billing/notifications.php', 'private/billing/payments.php', 'private/billing/provider.php', 'private/billing/read.php', 'private/billing/routes.php', 'private/catalog/bindings.php', 'private/catalog/contracts.php', 'private/catalog/core.php', 'private/catalog/manage.php', 'private/catalog/offers.php', 'private/catalog/read.php', 'private/catalog/requests.php', 'private/catalog/routes.php', 'private/collab/approvals.php', 'private/collab/core.php', 'private/collab/documents.php', 'private/collab/files.php', 'private/collab/messages.php', 'private/collab/routes.php', 'private/crm/core.php', 'private/crm/portal.php', 'private/crm/read.php', 'private/crm/routes.php', 'private/crm/write.php', 'private/customer-auth.php', 'private/customer-mail.php', 'private/customer-settings-state.php', 'private/customer-settings.php', 'private/legal/portal-draft.php', 'private/legal/privacy-2026-10-26-v1.json', 'private/legal/privacy-2026-10-27-v2.json', 'private/lifecycle/access.php', 'private/lifecycle/closure.php', 'private/lifecycle/contract-details.php', 'private/lifecycle/contract-package.php', 'private/lifecycle/contract-routes.php', 'private/lifecycle/dashboard.php', 'private/lifecycle/documents.php', 'private/lifecycle/flow.php', 'private/lifecycle/package/01_contract.docx', 'private/lifecycle/package/02_specification.docx', 'private/lifecycle/package/03_acceptance_act.docx', 'private/lifecycle/package/04_change_agreement.docx', 'private/lifecycle/package/05_portfolio_permission.docx', 'private/lifecycle/package/06_review_permission.docx', 'private/lifecycle/package/catalog.json', 'private/lifecycle/package/logo.png', 'private/lifecycle/payments.php', 'private/lifecycle/pdf.php', 'private/lifecycle/prospects.php', 'private/lifecycle/routes.php', 'private/lifecycle/schedule.php', 'private/lifecycle/templates.php', 'private/manual/actions.php', 'private/manual/core.php', 'private/manual/routes.php', 'private/manual/seal.php', 'private/maxapp/core.php', 'private/maxapp/session.php', 'private/notifications/max.php', 'private/notifications/worker.php', 'private/owner-bootstrap.json', 'private/owner-bootstrap.php', 'private/pricing/automation.php', 'private/pricing/core.php', 'private/pricing/engine.php', 'private/pricing/routes.php', 'private/product-navigation.php', 'private/production/artifacts.php', 'private/production/contracts.php', 'private/production/core.php', 'private/production/costs.php', 'private/production/engine.php', 'private/production/packages.php', 'private/production/plans.php', 'private/production/qa.php', 'private/production/read.php', 'private/production/registry.php', 'private/production/routes.php', 'private/production/seal.php', 'private/publication/core.php', 'private/publication/media.php', 'private/release-features.php', 'private/services/catalog.php', 'private/support/core.php', 'private/vendor/tfpdf/DEJAVU-LICENSE.txt', 'private/vendor/tfpdf/LICENSE.txt', 'private/vendor/tfpdf/NOTICE.txt', 'private/vendor/tfpdf/font/unifont/DejaVuSans-Bold.ttf', 'private/vendor/tfpdf/font/unifont/DejaVuSans.ttf', 'private/vendor/tfpdf/font/unifont/ttfonts.php', 'private/vendor/tfpdf/tfpdf.php', 'private/workflow/core.php', 'private/workflow/diagnostics.php', 'private/workflow/prepare.php'];
}
function hash_file_safe(string $path):?string {
    $parent=$path;do {insist(!is_link($parent),'symlink_refused');$next=dirname($parent);if($next===$parent)break;$parent=$next;} while(true);
    if(!file_exists($path))return null;
    insist(is_file($path)&&is_readable($path),'non_regular_file');return hash_file('sha256',$path);
}
function protected_files(string $root):array {
    return ['private/config.php'=>hash_file_safe($root.'/private/config.php'),'private/privacy-policy.txt'=>hash_file_safe($root.'/private/privacy-policy.txt')];
}
function assert_protected(string $root,array $before):void {insist(protected_files($root)===$before,'protected_file_changed');}
/** Schema metadata only: no customer rows, credentials, dumps or SQL text in evidence. */
function database_inventory(PDO $pdo):array {
    $tables=$pdo->query("SELECT table_name FROM information_schema.tables WHERE table_schema=DATABASE() ORDER BY table_name")->fetchAll(PDO::FETCH_COLUMN);
    $tables=array_values(array_filter($tables,fn($t)=>is_string($t)&&preg_match('/^nd_[a-z_]+$/D',$t)===1));
    $journal=[];
    if(in_array('nd_schema_migrations',$tables,true)) {
        $rows=$pdo->query('SELECT version,state,up_checksum,down_checksum FROM nd_schema_migrations ORDER BY version LIMIT 100')->fetchAll(PDO::FETCH_ASSOC);
        foreach($rows as $row) {
            insist(preg_match('/^[0-9]{3}_[a-z_]+$/D',$row['version'])===1,'invalid_migration_journal');
            $journal[]=['version'=>$row['version'],'state'=>$row['state'],'up_checksum'=>$row['up_checksum'],'down_checksum'=>$row['down_checksum']];
        }
    }
    $columns=$pdo->query("SELECT table_name,column_name,column_type,is_nullable,column_key FROM information_schema.columns WHERE table_schema=DATABASE() AND LEFT(table_name,3)='nd_' ORDER BY table_name,ordinal_position")->fetchAll(PDO::FETCH_ASSOC);
    return ['mysql_version'=>(string)$pdo->query('SELECT VERSION()')->fetchColumn(),'tables'=>$tables,'journal'=>$journal,'schema_sha256'=>hash('sha256',json_encode($columns))];
}
function safe_subprocess_diagnostic(string $path):array {
    $stage=basename($path)==='database.sql.error'?'database_dump':'migration_operator';$out=['stage'=>$stage,'code'=>'unclassified_private_subprocess_failure'];
    if(is_link($path)||!is_file($path)||filesize($path)>65536)return $out;
    $text=(string)file_get_contents($path);$j=json_decode(trim($text),true);
    $allowed=['invalid_configuration','strict_sql_mode_required','migration_files_missing','invalid_migration_manifest','migration_busy','migration_checksum_mismatch','partial_migration_requires_empty_rollback','unmanaged_table_collision','innodb_baseline_required','rollback_refused_nonempty_auth','newer_migration_applied','migration_failed','migration_004_required','migration_005_required','migration_006_required','migration_007_required','migration_008_required','migration_009_required','migration_010_required','migration_011_required','migration_012_required'];
    if(is_array($j)&&in_array($j['error']??'',$allowed,true))$out['code']=$j['error'];
    elseif(preg_match('/(?:Error|error|Got error|ERROR)[ :]+(?:\(([0-9]{3,4})\)|([0-9]{3,4}))/',$text,$m)){$out['code']='mysql_error_'.($m[1]!==''?$m[1]:$m[2]);}
    return $out;
}
function migration_diagnostics(string $root):array {
    $dirs=glob($root.'/.neurodelo-deploy/backups/*',GLOB_ONLYDIR)?:[];usort($dirs,fn($a,$b)=>filemtime($b)<=>filemtime($a));$out=[];
    foreach($dirs as $dir){if(is_link($dir))continue;foreach(array_merge(glob($dir.'/migration-*.log.error')?:[],glob($dir.'/database.sql.error')?:[]) as $path){if(is_link($path)||!is_file($path)||filesize($path)===0)continue;$row=safe_subprocess_diagnostic($path);$row['release_id']=basename($dir);if(preg_match('/^migration-([0-9]{3}_[a-z_]+)\.log\.error$/D',basename($path),$m))$row['migration']=$m[1];$out[]=$row;}if(count($out)>=3)break;}return array_slice($out,0,3);
}
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
    insist(str_starts_with((string)$pdo->query('SELECT VERSION()')->fetchColumn(),'5.7.'),'mysql_57_required');
    $pdo->exec('SET SESSION TRANSACTION READ ONLY');
    $pdo->query('SELECT id,password_hash FROM nd_admin LIMIT 0');
    $pdo->query('SELECT id,version,request_key,request_hash,consent,consent_at,policy_version,policy_hash FROM nd_leads LIMIT 0');
    $pdo->query('SELECT token,csrf,expires FROM nd_sessions LIMIT 0');$pdo->query('SELECT bucket,attempts,expires FROM nd_limits LIMIT 0');
    return ['ok'=>true,'php'=>PHP_VERSION,'database_connected'=>true,'admin_exists'=>(bool)$pdo->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn(),
            'privacy_approved'=>($c['privacy_policy_approved']??false)===true,'database_inventory'=>database_inventory($pdo),'prior_private_failures'=>migration_diagnostics($root),'strict_sql_mode'=>(bool)preg_match('/\bSTRICT_(TRANS_TABLES|ALL_TABLES)\b/',(string)$pdo->query('SELECT @@SESSION.sql_mode')->fetchColumn())];
}
function remove_tree(string $path):void {
    // Only managed backup/staging trees call this; unlink a leftover link, never follow it.
    if(is_link($path)){insist(unlink($path),'cleanup_failed');return;}
    if(is_dir($path)) {foreach(scandir($path) as $name)if($name!=='.'&&$name!=='..')remove_tree($path.'/'.$name);insist(rmdir($path),'cleanup_failed');}
    elseif(file_exists($path))insist(unlink($path),'cleanup_failed');
}
function verify_bundle(string $candidate,string $id):array {
    $m=read_json($candidate.'/manifest.json');
    insist(($m['schema_version']??0)===1&&preg_match('/^[a-f0-9]{40}$/D',$m['revision']??'')===1,'invalid_manifest');
    $actual=array_keys($m['files']??[]);$expected=paths();sort($actual);sort($expected);insist($actual===$expected,'release_allowlist_mismatch');
    insist(($m['keep_backups']??0)>=2&&($m['keep_backups']??0)<=20,'invalid_retention');
    foreach(array_keys($m['tools']) as $path)insist(!str_starts_with($path,'private/')&&!str_starts_with($path,'public_html/'),'unsafe_tool_path');
    foreach(array_merge($m['files'],$m['tools']) as $path=>$hash) {
        insist(!in_array('..',explode('/',$path),true)&&!in_array('.',explode('/',$path),true)&&!str_contains($path,'//'),'unsafe_release_path');
        insist(preg_match('#^(public_html|private)/[A-Za-z0-9_./-]+$|^(remote|recovery|reviewed-migrations)\.php$|^scripts/migrate(?:-[a-z]+)?\.php$|^database/(schema\.sql|migrations/[0-9]{3}_[a-z_]+\.sql|migrations/[0-9]{3}_[a-z_]+/(up|down)\.sql)$#D',$path)===1,'unsafe_release_path');
        insist(is_string($hash)&&preg_match('/^[a-f0-9]{64}$/D',$hash)===1&&hash_file_safe($candidate.'/'.$path)===$hash,'release_checksum_mismatch');
    }
    $allowed=array_merge(array_keys($m['files']),array_keys($m['tools']),['manifest.json','baseline.json']);
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($candidate,FilesystemIterator::SKIP_DOTS));
    foreach($iterator as $file) {insist(!$file->isLink(),'symlink_refused');if($file->isFile())insist(in_array(substr($file->getPathname(),strlen($candidate)+1),$allowed,true),'unexpected_release_file');}
    return $m;
}
function atomic_copy(string $source,string $destination,string $id,int $mode=0644):void {
    hash_file_safe($destination);
    if(!is_dir(dirname($destination)))insist(mkdir(dirname($destination),str_contains($destination,'/public_html/')?0755:0700,true),'destination_directory_failed');
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
    if($code!==0){$diagnostic=safe_subprocess_diagnostic($error);throw new DeployFailure($diagnostic['stage'].'_failed:'.$diagnostic['code']);}
}
function migrate_approved(string $root,string $candidate,array $m,string $backup):array {
    $entries=$m['migrations']??[];if(!$entries)return [];
    $c=require $root.'/private/config.php';
    $pdo=new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $exists=(bool)$pdo->query("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='nd_schema_migrations'")->fetchColumn();
    $pending=[];$reviewed=false;
    if(is_file($candidate.'/reviewed-migrations.php'))require_once $candidate.'/reviewed-migrations.php';
    foreach($entries as $entry) {
        insist(is_bool($entry['automatic']??null)&&is_bool($entry['required']??null)&&preg_match('/^[0-9]{3}_[a-z_]+$/D',$entry['version']??'')===1,'invalid_migration_approval');
        foreach(['up','down'] as $direction)insist(hash_file_safe($candidate.'/database/migrations/'.$entry['version'].'/'.$direction.'.sql')===($entry[$direction.'_sha256']??null),'migration_checksum_mismatch');
        $row=false;if($exists){$q=$pdo->prepare('SELECT * FROM nd_schema_migrations WHERE version=?');$q->execute([$entry['version']]);$row=$q->fetch(PDO::FETCH_ASSOC);}
        if($row){insist($row['state']==='applied'&&$row['up_checksum']===$entry['up_sha256']&&$row['down_checksum']===$entry['down_sha256'],'migration_state_or_checksum_mismatch');continue;}
        if(!$entry['automatic']){insist(!$entry['required'],'manual_migration_approval_required');continue;}
        if(($entry['kind']??'')==='reviewed_additive'){insist(function_exists('reviewed_migration')&&reviewed_migration($entry,$candidate),'unapproved_reviewed_migration');$reviewed=true;$pending[]=$entry['version'];continue;}
        insist($entry['version']==='004_crm_foundation'&&$entry['kind']==='additive','unapproved_automatic_migration');
        $up=(string)file_get_contents($candidate.'/database/migrations/'.$entry['version'].'/up.sql');
        $sql=preg_replace('/^--[^\n]*$/m','',$up);$statements=array_values(array_filter(array_map('trim',explode(';',$sql))));
        insist(count($statements)===12,'unsupported_automatic_migration');
        foreach($statements as $statement)insist(preg_match('/^CREATE TABLE nd_[a-z_]+\s*\([\s\S]+\)\s*ENGINE=InnoDB[\s\S]*$/D',$statement)===1,'destructive_migration_refused');
        $pending[]=$entry['version'];
    }
    if(!$pending)return [];
    // A prior genuinely healthy delivery and this CI's real dump/restore test are mandatory.
    $state=read_json(dirname(dirname($backup)).'/state.json');$previous=$state['last_release']??'';
    insist(is_string($previous)&&preg_match('/^[a-zA-Z0-9_-]{1,120}$/D',$previous)===1&&($m['verification_contract']??'')==='ci-mysql57-backup-restore-v1','pipeline_backup_recovery_not_verified');
    $good=read_json(dirname(dirname($backup)).'/backups/good-'.$previous.'/backup.json');
    $current=read_json($backup.'/backup.json');
    insist(($good['baseline']['ok']??false)===true&&($current['baseline']['ok']??false)===true,'pipeline_backup_recovery_not_verified');
    foreach($good['files'] as $path=>$entry)insist(hash_file_safe(dirname(dirname($backup)).'/backups/good-'.$previous.'/files/'.$path)===$entry['before'],'verified_recovery_snapshot_corrupt');
    if($reviewed){
        insist(($m['database_recovery_required']??false)===true,'database_recovery_required');
        reviewed_recovery_proof(dirname(dirname($backup)).'/backups/'.$previous.'/database-recovery');
        reviewed_recovery_proof($backup.'/database-recovery');
        foreach(['fileinfo','zip','openssl','tokenizer','mbstring','pdo_mysql'] as $extension)insist(extension_loaded($extension),'lifecycle_extension_missing_'.$extension);
    }
    if($reviewed){$proof=read_json($backup.'/database-recovery/verified.json');save_json($backup.'/database.json',['format'=>'verified-private-jsonl-schema-v1','directory'=>'database-recovery','sha256'=>$proof['backup_sha256'],'schema_sha256'=>$proof['schema_sha256'],'restore'=>'operator-approved only; never auto-import']);}
    else {
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
        $command=['mysqldump','--defaults-file='.$defaults,'--single-transaction','--quick','--skip-lock-tables','--no-tablespaces'];
        if(str_contains($options,'set-gtid-purged'))$command[]='--set-gtid-purged=OFF';
        if(str_contains($options,'column-statistics'))$command[]='--column-statistics=0';
        $command[]='--databases';$command[]=$c['db_name'];execute_private($command,$backup.'/database.sql');
        insist(filesize($backup.'/database.sql')>0,'empty_database_backup');
        save_json($backup.'/database.json',['sha256'=>hash_file('sha256',$backup.'/database.sql'),'restore'=>'operator-approved only; never auto-import']);
        $statePath=dirname(dirname($backup)).'/state.json';$state=read_json($statePath);$state['database_recovery_backup']=basename($backup);save_json($statePath,$state);
    } finally {if(is_file($defaults))unlink($defaults);}
    }
    $configLink=$candidate.'/private/config.php';insist(!file_exists($configLink)&&!is_link($configLink),'candidate_config_collision');
    insist(symlink($root.'/private/config.php',$configLink),'candidate_config_link_failed');
    try {
        foreach($entries as $entry)if(in_array($entry['version'],$pending,true))execute_private([getenv('NEURO_PHP_BIN')?:PHP_BINARY,$candidate.'/'.($entry['operator']??'scripts/migrate.php'),'up'],$backup.'/migration-'.$entry['version'].'.log');
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
    insist(!empty($meta['files'])&&!array_diff(array_keys($meta['files']),paths()),'backup_allowlist_mismatch');
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
        // Prove recovery by restoring each backed-up code file to private scratch and hashing it.
        $scratch=$backup.'/recovery-check';insist(mkdir($scratch,0700),'recovery_test_failed');
        foreach($entries as $path=>$entry)if($entry['before']!==null) {
            $target=$scratch.'/'.$path;if(!is_dir(dirname($target)))mkdir(dirname($target),0700,true);
            insist(copy($backup.'/files/'.$path,$target)&&hash_file_safe($target)===$entry['before'],'recovery_test_failed');
        }
        remove_tree($scratch);
        $meta=['revision'=>$m['revision'],'files'=>$entries,'protected'=>$protected,'baseline'=>$baseline,'keep_backups'=>$m['keep_backups']];
        save_json($backup.'/backup.json',$meta);
        $state['active']=$id;if(($baseline['ok']??false)===true)$state['known_good_backup']=$id;save_json($stateRoot.'/state.json',$state);
        $databaseRecovery=null;
        if(($m['database_recovery_required']??false)===true){require_once $candidate.'/recovery.php';$databaseRecovery=nr_rehearse(require $root.'/private/config.php',$backup.'/database-recovery');$state['database_recovery_backup']=$id;save_json($stateRoot.'/state.json',$state);}
        $migrated=migrate_approved($root,$candidate,$m,$backup);
        foreach(paths() as $path)atomic_copy($candidate.'/'.$path,$root.'/'.$path,$id);
        assert_protected($root,$protected);
        $actual=[];foreach(paths() as $path){$actual[$path]=hash_file_safe($root.'/'.$path);insist($actual[$path]===$m['files'][$path],'deployed_hash_mismatch');}
        $result=['database_recovery'=>$databaseRecovery,'backup_verified'=>true,'recovery_verified'=>true,'files_sha256'=>$actual,'ok'=>true,'applied'=>true,'revision'=>$m['revision'],'migrations'=>$migrated,'baseline_healthy'=>$baseline['ok']??false];
    }
    echo json_encode($result,JSON_UNESCAPED_SLASHES),PHP_EOL;
} catch(Throwable $e) {
    echo json_encode(['ok'=>false,'error'=>($e instanceof DeployFailure||$e instanceof RecoveryFailure)?$e->getMessage():'private_operation_failed','type'=>get_class($e),'file'=>basename($e->getFile()),'line'=>$e->getLine(),'writes_started'=>isset($state)&&(($state['active']??null)===$id||($state['last_release']??null)===$id)],JSON_UNESCAPED_SLASHES),PHP_EOL;exit(1);
} finally {if(is_resource($lock)){flock($lock,LOCK_UN);fclose($lock);}}
