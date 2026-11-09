<?php
declare(strict_types=1);
/** One-time, reversible separation of portfolio data and physical code removal. */
final class RetirementFailure extends RuntimeException {}
function pt_need(bool $ok,string $code):void {if(!$ok)throw new RetirementFailure($code);}
function pt_db(string $root):PDO {$c=require $root.'/private/config.php';return new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_EMULATE_PREPARES=>false]);}
function pt_ident(string $name):string {pt_need((bool)preg_match('/^nd_[a-z0-9_]{1,58}$/D',$name),'retirement_identifier');return '`'.$name.'`';}
function pt_query(PDO $p,string $sql,array $args=[]):PDOStatement {$q=$p->prepare($sql);$q->execute($args);return $q;}
function pt_base(string $root,bool $create=false):string {$base=$root.'/.neurodelo-retired';pt_need(!is_link($base),'retirement_archive_symlink');if($create&&!is_dir($base))pt_need(mkdir($base,0700),'retirement_archive_create');return $base;}
function pt_read(string $root):array {$p=pt_base($root).'/state.json';if(!is_file($p))return [];pt_need(!is_link($p),'retirement_state_symlink');return json_decode((string)file_get_contents($p),true,512,JSON_THROW_ON_ERROR);}
function pt_save(string $root,array $s):void {$base=pt_base($root,true);$p=$base.'/state.json';pt_need(!is_link($p)&&!is_link($p.'.tmp'),'retirement_state_symlink');pt_need(file_put_contents($p.'.tmp',json_encode($s,JSON_THROW_ON_ERROR|JSON_PRETTY_PRINT))!==false,'retirement_state_write');chmod($p.'.tmp',0600);pt_need(rename($p.'.tmp',$p),'retirement_state_write');}
function pt_tables(PDO $p):array {return $p->query('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')->fetchAll(PDO::FETCH_COLUMN);}
function pt_equal_set(array $a,array $b):bool {sort($a);sort($b);return $a===$b;}
function pt_archive_name(string $name):string {return 'nd_archive_'.substr($name,3);}
function pt_file_hash(string $path):string {return is_link($path)?hash('sha256','link:'.readlink($path)):(string)hash_file('sha256',$path);}
function pt_copy_tree(string $from,string $to,array &$manifest,string $relative=''):void {
    if(is_link($from)||is_file($from)){
        $hash=pt_file_hash($from);if(!is_dir(dirname($to)))pt_need(mkdir(dirname($to),0700,true),'retirement_copy_directory');
        if(!file_exists($to)&&!is_link($to)){
            if(is_link($from))pt_need(symlink(readlink($from),$to),'retirement_copy_link');
            else {pt_need(copy($from,$to),'retirement_copy_file');chmod($to,0600);}
        }
        pt_need(pt_file_hash($to)===$hash,'retirement_copy_checksum');$manifest[$relative]=['sha256'=>$hash,'link'=>is_link($from)];return;
    }
    pt_need(is_dir($from),'retirement_copy_missing');if(!is_dir($to))pt_need(mkdir($to,0700,true),'retirement_copy_directory');
    foreach(scandir($from) as $name)if($name!=='.'&&$name!=='..')pt_copy_tree($from.'/'.$name,$to.'/'.$name,$manifest,ltrim($relative.'/'.$name,'/'));
}
function pt_marker(string $root,string $phase):void {$p=$root.'/portfolio-transition.json';pt_need(!is_link($p),'retirement_marker_symlink');pt_need(file_put_contents($p,json_encode(['phase'=>$phase]))!==false,'retirement_marker_write');chmod($p,0600);}
function pt_summary(array $s):array {return ['phase'=>$s['phase']??'absent','archive_id'=>$s['id']??null,'legacy_tables_archived'=>count($s['rename']??[]),'files_archived'=>count($s['files']??[]),'copy'=>$s['copy']??null,'physical_cleanup_verified'=>($s['phase']??'')==='complete'];}
function pt_begin(string $root,string $candidate,array $m,string $id):array {
    $policy=$m['portfolio_retirement'];$s=pt_read($root);if(($s['phase']??'')==='complete')return pt_summary($s);
    if(in_array($s['phase']??'',['prepared','published','cleanup'],true))return pt_summary($s);
    pt_need(($s['phase']??'')===''||($s['phase']??'')==='rolled_back','retirement_recovery_required');
    $p=pt_db($root);$expected=array_merge($policy['legacy_tables'],$policy['auth_tables']);pt_need(pt_equal_set(pt_tables($p),$expected),'retirement_schema_changed');
    $base=pt_base($root,true);$archive=$base.'/'.$id;pt_need(!file_exists($archive)&&mkdir($archive,0700),'retirement_archive_collision');
    $map=[];foreach($policy['legacy_tables'] as $name)$map[$name]=pt_archive_name($name);
    $s=['id'=>$id,'revision'=>$m['revision'],'phase'=>'snapshot','rename'=>$map,'files'=>[],'keep'=>$policy['auth_tables'],'portfolio'=>$policy['portfolio_tables']];pt_save($root,$s);
    // Save every old source file, private document and configuration locally.
    foreach(['public_html','private','scripts','database'] as $dir)if(is_dir($root.'/'.$dir))pt_copy_tree($root.'/'.$dir,$archive.'/files/'.$dir,$s['files'],$dir);
    $s['config_before']=hash_file('sha256',$root.'/private/config.php');$s['phase']='renaming';pt_save($root,$s);
    pt_marker($root,'prepare');
    // Install the write/maintenance guard before changing table names. Existing
    // transactions drain at RENAME's metadata lock, so no committed edit is lost.
    pt_need(copy($candidate.'/public_html/site-router.php',$root.'/public_html/.portfolio-router.tmp'),'retirement_router_copy');chmod($root.'/public_html/.portfolio-router.tmp',0644);pt_need(rename($root.'/public_html/.portfolio-router.tmp',$root.'/public_html/site-router.php'),'retirement_router_copy');
    $pairs=[];foreach($map as $from=>$to)$pairs[]=pt_ident($from).' TO '.pt_ident($to);
    $p->exec('RENAME TABLE '.implode(',',$pairs));$s['phase']='renamed';pt_save($root,$s);return pt_summary($s);
}
function pt_populate(string $root,string $candidate,array $m,string $backup):array {
    $s=pt_read($root);if(in_array($s['phase']??'',['complete','prepared','published','cleanup'],true))return pt_summary($s);
    pt_need(($s['phase']??'')==='renamed','retirement_not_renamed');$p=pt_db($root);$archive=pt_base($root).'/'.$s['id'];
    $proof=json_decode((string)file_get_contents($backup.'/database-recovery/verified.json'),true,512,JSON_THROW_ON_ERROR);
    pt_need(($proof['verified']??false)&&($proof['source_data_written']??true)===false&&($proof['shadow_tables_removed']??false),'retirement_database_not_verified');
    $dbFiles=[];pt_copy_tree($backup.'/database-recovery',$archive.'/database-recovery',$dbFiles);$s['database_files']=$dbFiles;$s['database_proof']=$proof;
    // Capture any media committed while the original file snapshot was copied.
    if(is_dir($root.'/private/publication-files'))pt_copy_tree($root.'/private/publication-files',$archive.'/files/private/publication-files',$s['files'],'private/publication-files');
    $p->exec((string)file_get_contents($candidate.'/database/schema.sql'));
    $p->beginTransaction();try{
        $p->exec("INSERT INTO nd_pf_items(id,slug,state,head_revision,published_version_id,sort_order,version,rights_verified,created_at)
          SELECT p.id,p.slug,p.state,p.head_revision,p.published_version_id,p.sort_order,p.version,
          CASE WHEN p.order_id IS NULL OR JSON_UNQUOTE(JSON_EXTRACT(v.body_json,'$.owner_rights_confirmed'))='true' OR EXISTS(
            SELECT 1 FROM nd_archive_publication_permissions g JOIN nd_archive_lc_document_bindings b ON b.id=g.binding_id JOIN nd_archive_lc_templates t ON t.id=b.template_id
            WHERE g.version_id=p.published_version_id AND g.state='GRANTED' AND b.state='AGREED' AND b.order_id=p.order_id AND t.kind='portfolio_permission') THEN 1 ELSE 0 END,p.created_at
          FROM nd_archive_publications p LEFT JOIN nd_archive_publication_versions v ON v.id=p.published_version_id WHERE p.kind='portfolio'");
        $p->exec('INSERT INTO nd_pf_versions SELECT v.* FROM nd_archive_publication_versions v JOIN nd_pf_items p ON p.id=v.publication_id');
        $p->exec('INSERT INTO nd_pf_media SELECT * FROM nd_archive_publication_media');
        $checks=[];
        foreach([
          'items'=>['nd_pf_items',"SELECT id,slug,state,head_revision,published_version_id,sort_order,version,created_at FROM nd_archive_publications WHERE kind='portfolio' ORDER BY id",'id,slug,state,head_revision,published_version_id,sort_order,version,created_at'],
          'versions'=>['nd_pf_versions','SELECT v.* FROM nd_archive_publication_versions v JOIN nd_pf_items p ON p.id=v.publication_id ORDER BY v.id','*'],
          'media'=>['nd_pf_media','SELECT * FROM nd_archive_publication_media ORDER BY id','*']
        ] as $key=>[$table,$sql,$columns]){
            if($key==='versions')$sql='SELECT v.id,v.publication_id,v.revision_number,v.body_json,v.checksum,v.created_at FROM nd_archive_publication_versions v JOIN nd_pf_items p ON p.id=v.publication_id ORDER BY v.id';
            $before=$p->query($sql)->fetchAll(PDO::FETCH_NUM);$after=$p->query('SELECT '.$columns.' FROM '.pt_ident($table).' ORDER BY id')->fetchAll(PDO::FETCH_NUM);
            pt_need($before===$after,'retirement_portfolio_copy_mismatch');$checks[$key]=count($after);
        }
        foreach($p->query('SELECT body_json,checksum FROM nd_pf_versions') as $v)pt_need(hash_equals($v['checksum'],hash('sha256',$v['body_json'])),'retirement_version_checksum');
        $p->commit();$s['copy']=$checks;$s['phase']='prepared';pt_save($root,$s);
    }catch(Throwable $e){if($p->inTransaction())$p->rollBack();throw $e;}
    return pt_summary($s);
}
function pt_ready(string $root):void {$s=pt_read($root);if(($s['phase']??'')==='prepared'){$s['phase']='published';pt_save($root,$s);pt_marker($root,'verify');}}
function pt_rollback(string $root,?string $revision=null):void {
    $s=pt_read($root);pt_need(!(($s['phase']??'')==='complete'&&$revision===($s['revision']??null)),'retirement_old_application_restore_forbidden');if(!in_array($s['phase']??'',['renaming','renamed','prepared','published','snapshot'],true))return;
    $p=pt_db($root);$tables=pt_tables($p);$renamed=array_intersect(array_values($s['rename']),$tables);
    if($renamed){pt_need(count($renamed)===count($s['rename']),'retirement_partial_rename');pt_need(is_file($root.'/portfolio-transition.json'),'retirement_writes_not_frozen');
        $p->exec('SET FOREIGN_KEY_CHECKS=0');foreach(['nd_pf_versions','nd_pf_media','nd_pf_items'] as $name)$p->exec('DROP TABLE IF EXISTS '.pt_ident($name));$p->exec('SET FOREIGN_KEY_CHECKS=1');
        $pairs=[];foreach($s['rename'] as $old=>$new)$pairs[]=pt_ident($new).' TO '.pt_ident($old);$p->exec('RENAME TABLE '.implode(',',$pairs));
    }
    if(is_file($root.'/portfolio-transition.json'))unlink($root.'/portfolio-transition.json');$s['phase']='rolled_back';pt_save($root,$s);
}
function pt_retire_cron(string $root,string $archive):array {
    pt_need($root==='/home/n/neurodepro','retirement_cron_scope');$binary='/usr/bin/crontab';if(!is_executable($binary))return ['available'=>false,'removed'=>0];
    $pipes=[];$h=proc_open([$binary,'-l'],[0=>['file','/dev/null','r'],1=>['pipe','w'],2=>['file','/dev/null','w']],$pipes);pt_need(is_resource($h),'retirement_cron_read');$raw=stream_get_contents($pipes[1],262145);fclose($pipes[1]);$code=proc_close($h);
    if($code!==0&&$raw==='')return ['available'=>true,'removed'=>0];pt_need($code===0&&strlen($raw)<=262144,'retirement_cron_read');
    $lines=explode("\n",$raw);$keep=[];$removed=0;$targets=['private/notifications/worker.php','scripts/ai-worker.php','scripts/billing-worker.php','scripts/production-worker.php'];
    foreach($lines as $line){$match=false;foreach($targets as $target)if(str_contains($line,$root.'/'.$target)&&!str_starts_with(ltrim($line),'#'))$match=true;if($match)$removed++;else $keep[]=$line;}
    if($removed){$path=$archive.'/crontab.before';if(!file_exists($path)){pt_need(file_put_contents($path,$raw)!==false,'retirement_cron_backup');chmod($path,0600);}
        $h=proc_open([$binary,'-'],[0=>['pipe','r'],1=>['file','/dev/null','w'],2=>['file','/dev/null','w']],$pipes);pt_need(is_resource($h),'retirement_cron_write');fwrite($pipes[0],implode("\n",$keep));fclose($pipes[0]);pt_need(proc_close($h)===0,'retirement_cron_write');
    }return ['available'=>true,'removed'=>$removed];
}
function pt_cleanup(string $root,array $m,?callable $cron=null):array {
    $s=pt_read($root);pt_need(in_array($s['phase']??'',['published','cleanup','complete'],true),'retirement_not_published');
    if($s['phase']==='complete'){if(is_file($root.'/portfolio-transition.json'))unlink($root.'/portfolio-transition.json');return pt_summary($s)+['active_table_count'=>count($s['active_tables']),'legacy_operational_tables'=>0,'residual_legacy_files'=>0,'configuration_credentials_preserved'=>true,'cron'=>$s['cron']];}
    $archive=pt_base($root).'/'.$s['id'];pt_need(($s['database_proof']['verified']??false)===true,'retirement_archive_unverified');
    foreach($s['database_files'] as $path=>$entry)pt_need(pt_file_hash($archive.'/database-recovery/'.$path)===$entry['sha256'],'retirement_archive_corrupt');
    $p=pt_db($root);$expected=array_merge($s['keep'],$s['portfolio'],array_values($s['rename']));pt_need(pt_equal_set(pt_tables($p),$expected),'retirement_schema_changed');
    pt_need(in_array(hash_file('sha256',$root.'/private/config.php'),array_filter([$s['config_before'],$s['config_clean']??null]),true),'retirement_configuration_changed');
    $s['phase']='cleanup';pt_save($root,$s);$s['cron']=($cron??'pt_retire_cron')($root,$archive);pt_save($root,$s);
    $kept=[];foreach(array_keys($m['files']) as $path)$kept[$path]=true;
    $extra=['public_html'=>['.well-known','.user.ini','php.ini'],'private'=>['config.php','publication-files']];$moved=0;
    foreach(['public_html','private'] as $dir)foreach(scandir($root.'/'.$dir) as $name){
        if($name==='.'||$name==='..'||isset($kept[$dir.'/'.$name])||in_array($name,$extra[$dir],true))continue;
        $from=$root.'/'.$dir.'/'.$name;$to=$archive.'/removed/'.$dir.'/'.$name;
        pt_need(!file_exists($to)&&!is_link($to),'retirement_move_collision');if(!is_dir(dirname($to)))pt_need(mkdir(dirname($to),0700,true),'retirement_move_directory');
        $hash=is_dir($from)&&!is_link($from)?null:pt_file_hash($from);pt_need(rename($from,$to),'retirement_move_failed');if($hash!==null)pt_need(pt_file_hash($to)===$hash,'retirement_move_checksum');$moved++;
    }
    foreach(['scripts','database'] as $dir)if(is_dir($root.'/'.$dir)){pt_need(rename($root.'/'.$dir,$archive.'/removed/'.$dir),'retirement_auxiliary_move');$moved++;}
    $configFile=$root.'/private/config.php';$c=require $configFile;$clean=array_intersect_key($c,array_flip(['db_host','db_port','db_name','db_user','db_password','app_url']));
    pt_need(count($clean)>=5,'retirement_active_configuration');$tmp=$configFile.'.portfolio.tmp';pt_need(!file_exists($tmp)&&!is_link($tmp),'retirement_configuration_collision');
    pt_need(file_put_contents($tmp,"<?php\nreturn ".var_export($clean,true).";\n")!==false,'retirement_configuration_write');chmod($tmp,0600);$check=require $tmp;pt_need($check===$clean,'retirement_configuration_values');$s['config_clean']=hash_file('sha256',$tmp);pt_save($root,$s);pt_need(rename($tmp,$configFile),'retirement_configuration_write');
    foreach(['public_html','private'] as $dir)foreach(scandir($root.'/'.$dir) as $name)if($name!=='.'&&$name!=='..')pt_need(isset($kept[$dir.'/'.$name])||in_array($name,$extra[$dir],true),'retirement_residual_file');
    $s['phase']='complete';$s['moved_entries']=($s['moved_entries']??0)+$moved;$s['active_tables']=array_merge($s['keep'],$s['portfolio']);pt_save($root,$s);
    if(is_file($root.'/portfolio-transition.json'))unlink($root.'/portfolio-transition.json');
    return pt_summary($s)+['active_table_count'=>count($s['active_tables']),'legacy_operational_tables'=>0,'residual_legacy_files'=>0,'configuration_credentials_preserved'=>true];
}
