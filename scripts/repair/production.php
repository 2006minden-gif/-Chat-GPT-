<?php
/** One-time CLI-only, server-local repair. Never exports config bytes, tokens or parser messages. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
final class RepairFailure extends RuntimeException {}
function rp_assert(bool $ok,string $code):void {if(!$ok)throw new RepairFailure($code);}
function rp_read(string $path):string {
    rp_assert(!is_link($path)&&is_file($path)&&is_readable($path),'unsafe_or_missing_file');
    $s=@file_get_contents($path);rp_assert(is_string($s)&&strlen($s)<=262144,'file_read_or_size_failed');return $s;
}
function rp_file_hash(string $path):string {
    rp_assert(!is_link($path)&&is_file($path)&&is_readable($path),'unsafe_or_missing_file');
    $hash=@hash_file('sha256',$path);rp_assert(is_string($hash)&&strlen($hash)===64,'file_hash_failed');return $hash;
}
function rp_backup_copy(string $source,string $destination,string $expected):void {
    rp_assert(rp_file_hash($source)===$expected,'source_changed_during_backup');
    rp_assert(!file_exists($destination)&&!is_link($destination),'backup_file_collision');
    $in=fopen($source,'rb');$out=fopen($destination,'x+b');rp_assert(is_resource($in)&&is_resource($out),'backup_open_failed');chmod($destination,0600);
    try{rp_assert(stream_copy_to_stream($in,$out)!==false&&fflush($out),'backup_copy_failed');if(function_exists('fsync'))rp_assert(fsync($out),'backup_sync_failed');}finally{fclose($in);fclose($out);}
    rp_assert(rp_file_hash($source)===$expected&&rp_file_hash($destination)===$expected,'backup_integrity_failed');
}
function rp_syntax(string $s):array {
    rp_assert(function_exists('token_get_all'),'tokenizer_extension_required');
    try{token_get_all($s,TOKEN_PARSE);return ['valid'=>true,'line'=>null];}
    catch(ParseError $e){return ['valid'=>false,'line'=>$e->getLine()];}
}
function rp_tokens(string $s):array {
    $tokens=[];$offset=0;
    foreach(token_get_all($s) as $t){$text=is_array($t)?$t[1]:$t;$id=is_array($t)?$t[0]:null;
        if(!in_array($id,[T_WHITESPACE,T_COMMENT,T_DOC_COMMENT],true))$tokens[]=['id'=>$id,'text'=>$text,'offset'=>$offset,'end'=>$offset+strlen($text)];
        $offset+=strlen($text);
    }return $tokens;
}
function rp_literal_signature(string $s):string {
    // Scalar token spellings, flags, comments and whitespace remain byte-identical, not reserialized.
    $out=[];foreach(token_get_all($s) as $t)if(is_array($t))$out[]=[$t[0],$t[1]];
    return hash('sha256',serialize($out));
}
function rp_static_config(string $s):bool {
    if(!rp_syntax($s)['valid'])return false;$t=rp_tokens($s);$i=0;
    $is=static function(string $text)use(&$t,&$i):bool{return isset($t[$i])&&$t[$i]['text']===$text;};
    $eat=static function(string $text)use(&$i,$is):void{rp_assert($is($text),'nonliteral_configuration');$i++;};
    try{
        rp_assert(($t[$i++]['id']??null)===T_OPEN_TAG,'nonliteral_configuration');
        if(($t[$i]['id']??null)===T_DECLARE){$i++;$eat('(');$eat('strict_types');$eat('=');$eat('1');$eat(')');$eat(';');}
        rp_assert(($t[$i++]['id']??null)===T_RETURN,'nonliteral_configuration');
        $value=null;
        $value=static function(int $depth=0)use(&$value,&$i,$t,$is,$eat):void{
            rp_assert($depth<16,'nonliteral_configuration');$id=$t[$i]['id']??null;
            if($is('[')||$id===T_ARRAY){$array=$id===T_ARRAY;if($array){$i++;$eat('(');}else{$eat('[');}$close=$array?')':']';
                if(!$is($close))while(true){$value($depth+1);if(($t[$i]['id']??null)===T_DOUBLE_ARROW){$i++;$value($depth+1);}if(!$is(','))break;$i++;if($is($close))break;}
                $eat($close);return;
            }
            if($is('-')){$i++;rp_assert(in_array($t[$i]['id']??null,[T_LNUMBER,T_DNUMBER],true),'nonliteral_configuration');$i++;return;}
            rp_assert(in_array($id,[T_CONSTANT_ENCAPSED_STRING,T_LNUMBER,T_DNUMBER],true)||($id===T_STRING&&in_array(strtolower($t[$i]['text']),['true','false','null'],true)),'nonliteral_configuration');$i++;
        };
        rp_assert($is('[')||($t[$i]['id']??null)===T_ARRAY,'nonliteral_configuration');$value();
        if($is(';'))$i++;
        if(($t[$i]['id']??null)===T_CLOSE_TAG)$i++;
        if(($t[$i]['id']??null)===T_INLINE_HTML&&trim($t[$i]['text'])==='')$i++;
        return $i===count($t);
    }catch(RepairFailure $e){return false;}
}
function rp_config_candidate(string $s):array {
    $syntax=rp_syntax($s);
    if($syntax['valid']){rp_assert(rp_static_config($s),'nonliteral_configuration');return ['content'=>$s,'kind'=>'no_change','line'=>null];}
    $t=rp_tokens($s);$candidates=[];
    foreach($t as $i=>$token){
        // Insert only a comma between a literal value and a subsequent array key. No quotes/values changed.
        if($i<1||$token['id']!==T_CONSTANT_ENCAPSED_STRING||($t[$i+1]['id']??null)!==T_DOUBLE_ARROW)continue;
        $previous=$t[$i-1];$isValue=in_array($previous['id'],[T_CONSTANT_ENCAPSED_STRING,T_LNUMBER,T_DNUMBER],true)
            ||($previous['id']===T_STRING&&in_array(strtolower($previous['text']),['true','false','null'],true))||in_array($previous['text'],[']',')'],true);
        if(!$isValue)continue;
        $pos=$previous['end'];$candidate=substr($s,0,$pos).','.substr($s,$pos);
        if(rp_static_config($candidate)&&hash_equals(rp_literal_signature($s),rp_literal_signature($candidate)))$candidates[]=['content'=>$candidate,'kind'=>'missing_comma','line'=>substr_count(substr($s,0,$pos),"\n")+1];
    }
    $last=end($t);
    if($last&&in_array($last['text'],[']',')'],true)){
        $pos=$last['end'];$candidate=substr($s,0,$pos).';'.substr($s,$pos);
        if(rp_static_config($candidate)&&hash_equals(rp_literal_signature($s),rp_literal_signature($candidate)))$candidates[]=['content'=>$candidate,'kind'=>'missing_terminal_semicolon','line'=>substr_count(substr($s,0,$pos),"\n")+1];
    }
    rp_assert(count($candidates)===1,'unique_literal_preserving_repair_not_found');return $candidates[0];
}
function rp_block():string {
    return <<<'RULES'
# BEGIN NEURODELO ISSUE10 SECURITY
# Public code/assets remain available. Private backups and diagnostic copies never do.
<FilesMatch "(?i)(~|^#.*#$|^\.|\.(bak|bkp|backup|old|orig|save|swp|swo|tmp|temp)(\.|$)|\.(sql|sqlite3?|dump|ini|log|pem|key|p12|pfx|zip|tar|tgz|gz|7z|rar)$)">
    Require all denied
</FilesMatch>
<FilesMatch "(?i)^(config(\.example)?\.php|phpinfo\.php|diagnose\.php|debug\.php)$">
    Require all denied
</FilesMatch>
# Block hidden directories as well as files, preserving ACME certificate renewal.
<If "%{REQUEST_URI} =~ m#(^|/)(\.|%2[eE])# && %{REQUEST_URI} !~ m#^/(\.|%2[eE])well-known/acme-challenge/[A-Za-z0-9_-]+$#">
    Require all denied
</If>
# END NEURODELO ISSUE10 SECURITY
RULES;
}
function rp_htaccess_candidate(string $s):string {
    if(str_contains($s,'# BEGIN NEURODELO ISSUE10 SECURITY')){rp_assert(str_contains($s,rp_block()),'managed_rules_changed');return $s;}
    rp_assert(!str_contains($s,'# END NEURODELO ISSUE10 SECURITY'),'incomplete_managed_rules');
    return $s.(str_ends_with($s,"\n")?'':"\n").rp_block()."\n";
}
function rp_inspect(string $root):array {
    $config=rp_read($root.'/private/config.php');$syntax=rp_syntax($config);$candidate=null;
    try{$candidate=rp_config_candidate($config);}catch(RepairFailure $e){}
    $out=['ok'=>true,'read_only'=>true,'php'=>PHP_VERSION,'configuration'=>['syntax_valid'=>$syntax['valid'],'error_type'=>$syntax['valid']?null:'ParseError','error_line'=>$syntax['line'],'automatic_repair_available'=>$candidate!==null,'repair_kind'=>$candidate['kind']??null,'repair_line'=>$candidate['line']??null],'backup_copies'=>[]];
    foreach(['~.htaccess','index~.html'] as $name){$path=$root.'/public_html/'.$name;$row=['exists'=>is_file($path),'symlink'=>is_link($path)];
        if($row['exists']&&!$row['symlink']){$data=@file_get_contents($path,false,null,0,65536);rp_assert(is_string($data),'backup_sample_unreadable');$row+=['bytes'=>filesize($path),'scan_complete'=>filesize($path)<=65536,'private_key_marker'=>(bool)preg_match('/-----BEGIN [^-]*PRIVATE KEY-----/',$data),'credential_assignment_marker'=>(bool)preg_match('/(?:password|secret|api_key)\s*[\x22\x27]?\s*(?:=>|=|:)/i',$data),'php_config_marker'=>str_contains($data,'db_password')];}
        $out['backup_copies'][$name]=$row;
    }
    $inventory=['complete'=>true,'scanned'=>0,'backup_style'=>0,'hidden_entry'=>0,'dump_or_archive'=>0,'symlinks'=>0];
    $iterator=new RecursiveIteratorIterator(new RecursiveDirectoryIterator($root.'/public_html',FilesystemIterator::SKIP_DOTS));
    $iterator->setMaxDepth(5);
    foreach($iterator as $entry){if(++$inventory['scanned']>2000){$inventory['complete']=false;break;}
        if($entry->isLink()){$inventory['symlinks']++;continue;}$name=$entry->getFilename();$relative=substr($entry->getPathname(),strlen($root.'/public_html/'));
        if(preg_match('/(~|^#.*#$|\.(bak|bkp|backup|old|orig|swp|swo|save|tmp|temp)(\.|$))/i',$name))$inventory['backup_style']++;
        if(preg_match('#(^|/)\.#',$relative))$inventory['hidden_entry']++;
        if(preg_match('/\.(sql|sqlite3?|dump|zip|tar|tgz|gz|7z|rar)$/i',$name))$inventory['dump_or_archive']++;
    }
    $out['public_inventory']=$inventory;
    $rules=rp_read($root.'/public_html/.htaccess');$out['managed_rules_present']=str_contains($rules,rp_block());return $out;
}

function rp_layout(string $root):void {
    foreach(['private','public_html'] as $dir)rp_assert(is_dir($root.'/'.$dir)&&!is_link($root.'/'.$dir)&&is_writable($root.'/'.$dir),'unsafe_application_directory');
}
function rp_save(string $path,array $data):void {
    rp_assert(!is_link($path)&&!file_exists($path.'.tmp'),'unsafe_metadata_path');
    rp_assert(file_put_contents($path.'.tmp',json_encode($data,JSON_THROW_ON_ERROR),LOCK_EX)!==false,'metadata_write_failed');
    chmod($path.'.tmp',0600);rp_assert(rename($path.'.tmp',$path),'metadata_rename_failed');
}
function rp_json(string $path):array {
    $v=json_decode(rp_read($path),true,64,JSON_THROW_ON_ERROR);rp_assert(is_array($v),'invalid_metadata');return $v;
}
function rp_fixed():array {return ['config'=>'private/config.php','rules'=>'public_html/.htaccess','copy_rules'=>'public_html/~.htaccess','copy_index'=>'public_html/index~.html'];}
function rp_base(string $root):string {
    $base=$root.'/.neurodelo-repair';rp_assert(!is_link($base),'unsafe_repair_directory');
    if(!is_dir($base))rp_assert(mkdir($base,0700),'repair_directory_failed');chmod($base,0700);return $base;
}
function rp_plan(string $root,string $id):string {
    rp_assert((bool)preg_match('/^[a-z0-9][a-z0-9-]{0,79}$/D',$id),'invalid_plan_id');
    $base=$root.'/.neurodelo-repair';rp_assert(is_dir($base)&&!is_link($base),'repair_plan_missing');
    $path=$base.'/'.$id;rp_assert(is_dir($path)&&!is_link($path),'repair_plan_missing');return $path;
}
function rp_manifest(string $plan):array {
    $m=rp_json($plan.'/manifest.json');$fixed=rp_fixed();
    rp_assert(($m['schema']??0)===1&&($m['rules_version']??'')===hash('sha256',rp_block()),'repair_version_mismatch');
    rp_assert(isset($m['files']['config'],$m['files']['rules'])&&array_diff(array_keys($m['files']),array_keys($fixed))===[],'invalid_file_manifest');
    foreach($m['files'] as $key=>$file){rp_assert(is_array($file)&&preg_match('/^[a-f0-9]{64}$/D',$file['before']??'')===1,'invalid_file_manifest');rp_assert(hash_equals($file['before'],rp_file_hash($plan.'/'.$key.'.before')),'backup_integrity_failed');}
    return $m;
}
function rp_atomic(string $path,string $data,string $id,int $mode):void {
    rp_assert(!is_link($path),'symlink_refused');$tmp=dirname($path).'/.nd-repair-'.$id.'-'.basename($path).'.tmp';
    rp_assert(!file_exists($tmp)&&!is_link($tmp),'temporary_file_collision');
    $f=@fopen($tmp,'x+b');rp_assert(is_resource($f),'temporary_file_failed');
    try {
        chmod($tmp,0600);$left=$data;while($left!==''){$n=fwrite($f,$left);rp_assert(is_int($n)&&$n>0,'temporary_write_failed');$left=substr($left,$n);}
        rp_assert(fflush($f),'temporary_flush_failed');if(function_exists('fsync'))rp_assert(fsync($f),'temporary_sync_failed');fclose($f);$f=null;
        rp_assert(hash('sha256',rp_read($tmp))===hash('sha256',$data),'temporary_integrity_failed');chmod($tmp,$mode&0777);rp_assert(rename($tmp,$path),'atomic_rename_failed');
    } finally {if(is_resource($f))fclose($f);if(is_file($tmp)&&!is_link($tmp))unlink($tmp);}
}

function rp_preflight(string $configFile):array {
    rp_assert(rp_static_config(rp_read($configFile)),'nonliteral_configuration');
    $c=require $configFile;rp_assert(is_array($c),'invalid_configuration');
    foreach(['db_host','db_name','db_user','db_password','app_url'] as $key)rp_assert(isset($c[$key])&&is_string($c[$key]),'invalid_configuration');
    rp_assert(rtrim($c['app_url'],'/')==='https://neurodelo.pro'||(getenv('NEURO_REPAIR_TEST')==='1'&&str_starts_with($configFile,sys_get_temp_dir().'/')&&str_starts_with($c['app_url'],'http://127.0.0.1:')),'unexpected_application_url');
    if(getenv('NEURO_REPAIR_TEST_FAKE_PDO')==='1'&&getenv('NEURO_REPAIR_TEST')==='1'&&str_starts_with($configFile,sys_get_temp_dir().'/'))return ['pdo'=>true,'synthetic'=>true,'privacy_approved'=>($c['privacy_policy_approved']??false)===true];
    $p=new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
    $p->exec('SET SESSION TRANSACTION READ ONLY');
    foreach(['nd_admin'=>'id,password_hash','nd_leads'=>'id,version,request_key,request_hash,consent,consent_at,policy_version,policy_hash','nd_sessions'=>'token,csrf,expires','nd_limits'=>'bucket,attempts,expires'] as $table=>$cols)$p->query('SELECT '.$cols.' FROM '.$table.' LIMIT 0');
    return ['pdo'=>true,'database_version'=>$p->query('SELECT VERSION()')->fetchColumn(),'admin_exists'=>(bool)$p->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn(),'privacy_approved'=>($c['privacy_policy_approved']??false)===true];
}
function rp_summary(string $plan,array $m):array {
    return ['ok'=>true,'plan_id'=>basename($plan),'state'=>$m['state'],'backup_verified'=>true,'recovery_verified'=>true,'repair_kind'=>$m['repair_kind'],'repair_line'=>$m['repair_line'],'literal_values_preserved'=>rp_literal_signature(rp_read(dirname(dirname($plan)).'/private/config.php'))===$m['scalar_signature'],'quarantined_copies'=>count($m['quarantined']??[]),'configuration_syntax_valid'=>rp_syntax(rp_read(dirname(dirname($plan)).'/private/config.php'))['valid']];
}
function rp_prepare(string $root,string $id):array {
    rp_layout($root);$base=rp_base($root);rp_assert(!is_file($base.'/active.json'),'pending_repair_requires_resolution');
    rp_assert(preg_match('/^[a-z0-9][a-z0-9-]{0,79}$/D',$id)===1,'invalid_plan_id');$plan=$base.'/'.$id;rp_assert(!file_exists($plan)&&!is_link($plan),'plan_already_exists');
    $config=rp_read($root.'/private/config.php');$candidate=rp_config_candidate($config);$rules=rp_read($root.'/public_html/.htaccess');$newRules=rp_htaccess_candidate($rules);
    $needed=0;foreach(rp_fixed() as $relative){$file=$root.'/'.$relative;if(is_file($file)&&!is_link($file))$needed+=filesize($file);}
    rp_assert(disk_free_space($root)>$needed*3+16777216,'insufficient_backup_space');
    rp_assert(mkdir($plan,0700),'plan_directory_failed');$files=[];
    // ALL original targets are backed up, verified and restoration-tested before public/config mutation.
    foreach(rp_fixed() as $key=>$relative){$source=$root.'/'.$relative;if(!file_exists($source)&&!is_link($source)){rp_assert(!in_array($key,['config','rules'],true),'required_file_missing');continue;}
        $sha=rp_file_hash($source);rp_backup_copy($source,$plan.'/'.$key.'.before',$sha);
        rp_backup_copy($plan.'/'.$key.'.before',$plan.'/restore-check',$sha);unlink($plan.'/restore-check');
        $files[$key]=['before'=>$sha,'mode'=>fileperms($source)&0777];
    }
    foreach(['config'=>$candidate['content'],'rules'=>$newRules] as $key=>$data){rp_assert(file_put_contents($plan.'/'.$key.'.next',$data,LOCK_EX)!==false,'candidate_write_failed');chmod($plan.'/'.$key.'.next',0600);$files[$key]['after']=hash('sha256',$data);}
    $m=['schema'=>1,'rules_version'=>hash('sha256',rp_block()),'state'=>'prepared','files'=>$files,'quarantined'=>[],'repair_kind'=>$candidate['kind'],'repair_line'=>$candidate['line'],'scalar_signature'=>rp_literal_signature($config)];
    rp_save($plan.'/manifest.json',$m);rp_save($base.'/active.json',['id'=>$id]);
    rp_manifest($plan);rp_assert(rp_static_config(rp_read($plan.'/config.next'))&&rp_literal_signature(rp_read($plan.'/config.next'))===$m['scalar_signature'],'literal_values_changed');
    $out=rp_summary($plan,$m);$out['candidate_preflight']=rp_preflight($plan.'/config.next');return $out;
}
function rp_probes(string $id):array {
    return ['.nd-repair-'.$id.'.tmp','nd-repair-'.$id.'.bak','.nd-repair-'.$id.'/probe.txt'];
}
function rp_clean_probes(string $root,string $id):void {
    foreach(rp_probes($id) as $name){$p=$root.'/public_html/'.$name;if(file_exists($p)||is_link($p)){rp_assert(rp_read($p)==='NEURODELO_SYNTHETIC_SECURITY_PROBE','probe_changed');rp_assert(unlink($p),'probe_cleanup_failed');}}
    $dir=$root.'/public_html/.nd-repair-'.$id;if(is_dir($dir)&&!is_link($dir))rp_assert(rmdir($dir),'probe_cleanup_failed');
}
function rp_rollback(string $root,string $id):array {
    $plan=rp_plan($root,$id);$m=rp_manifest($plan);$fixed=rp_fixed();
    rp_assert(in_array($m['state'],['prepared','applying','applied','confirmed','rolled_back'],true),'invalid_plan_state');
    $keepRules=$m['state']==='confirmed'||($m['keep_verified_rules']??false)===true;
    foreach(['config','rules'] as $key){$sha=rp_file_hash($root.'/'.$fixed[$key]);rp_assert(in_array($sha,[$m['files'][$key]['before'],$m['files'][$key]['after']],true),'rollback_external_change');}
    rp_clean_probes($root,$id);
    foreach(['config','rules'] as $key){if($key==='rules'&&$keepRules)continue;if(rp_file_hash($root.'/'.$fixed[$key])!==$m['files'][$key]['before'])rp_atomic($root.'/'.$fixed[$key],rp_read($plan.'/'.$key.'.before'),$id.'-rollback',$m['files'][$key]['mode']);rp_assert(rp_file_hash($root.'/'.$fixed[$key])===$m['files'][$key]['before'],'rollback_integrity_failed');}
    // Quarantined copies NEVER move back to public_html, including after rollback.
    $m['state']='rolled_back';$m['keep_verified_rules']=$keepRules;rp_save($plan.'/manifest.json',$m);$base=dirname($plan);
    if(is_file($base.'/active.json')){rp_assert(rp_json($base.'/active.json')['id']===$id,'active_plan_changed');unlink($base.'/active.json');}
    return ['ok'=>true,'plan_id'=>$id,'state'=>'rolled_back','bytes_restored'=>true,'security_rules_retained'=>$keepRules,'backup_copies_remain_private'=>true,'healthy'=>false];
}
function rp_apply(string $root,string $id):array {
    $plan=rp_plan($root,$id);$m=rp_manifest($plan);$fixed=rp_fixed();rp_assert($m['state']==='prepared','plan_not_prepared');
    foreach($m['files'] as $key=>$file)rp_assert(rp_file_hash($root.'/'.$fixed[$key])===$file['before'],'source_changed_since_backup');
    foreach(['config','rules'] as $key)rp_assert(hash('sha256',rp_read($plan.'/'.$key.'.next'))===$m['files'][$key]['after'],'candidate_changed');
    rp_assert(rp_static_config(rp_read($plan.'/config.next'))&&rp_literal_signature(rp_read($plan.'/config.next'))===$m['scalar_signature'],'literal_values_changed');
    foreach(rp_probes($id) as $probe)rp_assert(!file_exists($root.'/public_html/'.$probe)&&!is_link($root.'/public_html/'.$probe),'probe_collision');
    rp_assert(!file_exists($root.'/public_html/.nd-repair-'.$id)&&!is_link($root.'/public_html/.nd-repair-'.$id),'probe_collision');
    $preflight=rp_preflight($plan.'/config.next');$m['state']='applying';rp_save($plan.'/manifest.json',$m);
    try{
        rp_assert(mkdir($plan.'/quarantine',0700),'quarantine_directory_failed');
        foreach(['copy_rules','copy_index'] as $key)if(isset($m['files'][$key])){
            rp_assert(rename($root.'/'.$fixed[$key],$plan.'/quarantine/'.$key),'quarantine_failed');chmod($plan.'/quarantine/'.$key,0600);$m['quarantined'][]=$key;rp_save($plan.'/manifest.json',$m);
        }
        foreach(['rules','config'] as $key){rp_atomic($root.'/'.$fixed[$key],rp_read($plan.'/'.$key.'.next'),$id,$m['files'][$key]['mode']);rp_assert(rp_file_hash($root.'/'.$fixed[$key])===$m['files'][$key]['after'],'applied_integrity_failed');}
        rp_assert(rp_static_config(rp_read($root.'/private/config.php'))&&rp_literal_signature(rp_read($root.'/private/config.php'))===$m['scalar_signature'],'literal_values_changed');
        $live=rp_preflight($root.'/private/config.php');
        rp_assert(mkdir($root.'/public_html/.nd-repair-'.$id,0755),'probe_directory_failed');
        foreach(rp_probes($id) as $relative){$p=$root.'/public_html/'.$relative;rp_assert(!file_exists($p)&&!is_link($p),'probe_collision');rp_atomic($p,'NEURODELO_SYNTHETIC_SECURITY_PROBE',$id,0644);}
        $m['state']='applied';rp_save($plan.'/manifest.json',$m);$out=rp_summary($plan,$m);$out['preflight']=$live;$out['http_confirmation_required']=true;return $out;
    }catch(Throwable $e){try{rp_rollback($root,$id);}catch(Throwable $rollback){throw new RepairFailure('repair_failed_and_rollback_requires_attention');}throw new RepairFailure('repair_failed_and_rolled_back');}
}
function rp_confirm(string $root,string $id,array $receipt):array {
    $plan=rp_plan($root,$id);$m=rp_manifest($plan);rp_assert($m['state']==='applied','repair_not_applied');
    rp_assert(($receipt['plan_id']??'')===$id&&($receipt['ok']??false)===true&&($receipt['health']['ok']??false)===true&&($receipt['health']['complete']??false)===true&&!empty($receipt['health']['checks'])&&!in_array(false,array_map(static fn($r)=>($r['ok']??false)===true,$receipt['health']['checks']),true),'successful_http_confirmation_required');
    $expected=['/~.htaccess','/index~.html','/'.rp_probes($id)[0],'/'.rp_probes($id)[1],'/'.rp_probes($id)[2]];
    foreach($expected as $url)foreach(['GET','HEAD'] as $method)rp_assert(in_array($receipt['protection'][$url][$method]??0,[403,404],true),'backup_url_not_protected');
    foreach(['config'=>'private/config.php','rules'=>'public_html/.htaccess'] as $key=>$path)rp_assert(hash('sha256',rp_read($root.'/'.$path))===$m['files'][$key]['after'],'applied_file_changed');
    rp_assert(rp_literal_signature(rp_read($root.'/private/config.php'))===$m['scalar_signature'],'literal_values_changed');rp_preflight($root.'/private/config.php');rp_clean_probes($root,$id);
    $m['state']='confirmed';$m['keep_verified_rules']=true;rp_save($plan.'/manifest.json',$m);rp_save($plan.'/http-receipt.json',$receipt);$base=dirname($plan);
    rp_assert(rp_json($base.'/active.json')['id']===$id,'active_plan_changed');unlink($base.'/active.json');$out=rp_summary($plan,$m);$out['healthy']=true;return $out;
}

if(!defined('NEURO_REPAIR_LIBRARY')){
    try{
        rp_assert(PHP_VERSION_ID>=80400,'php_84_required');$op=$argv[1]??'inspect';$root=$argv[2]??'/home/n/neurodepro';
        rp_assert($root==='/home/n/neurodepro'||(getenv('NEURO_REPAIR_TEST')==='1'&&str_starts_with($root,sys_get_temp_dir().'/')),'unexpected_root');
        rp_assert(realpath($root)===$root&&!is_link($root),'unsafe_root');
        if($op==='inspect')$out=rp_inspect($root);
        elseif($op==='status'){$id=$argv[3]??'';$out=rp_summary(rp_plan($root,$id),rp_manifest(rp_plan($root,$id)));}
        else {
            rp_layout($root);rp_assert(in_array($op,['prepare','apply','rollback','confirm','status'],true),'unknown_operation');$id=$argv[3]??'';
            $base=rp_base($root);rp_assert(!is_link($base.'/repair.lock'),'unsafe_lock');$lock=fopen($base.'/repair.lock','c+b');rp_assert(is_resource($lock)&&flock($lock,LOCK_EX|LOCK_NB),'repair_busy');chmod($base.'/repair.lock',0600);
            try{$out=match($op){'prepare'=>rp_prepare($root,$id),'apply'=>rp_apply($root,$id),'rollback'=>rp_rollback($root,$id),'confirm'=>rp_confirm($root,$id,json_decode(base64_decode($argv[4]??'',true)?:'{}',true,64,JSON_THROW_ON_ERROR)),'status'=>rp_summary(rp_plan($root,$id),rp_manifest(rp_plan($root,$id)))};}finally{flock($lock,LOCK_UN);fclose($lock);}
        }
        echo json_encode($out,JSON_UNESCAPED_SLASHES),"\n";
    }catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e instanceof RepairFailure?$e->getMessage():'repair_operation_failed','type'=>get_class($e)]),"\n";exit(1);}
}
