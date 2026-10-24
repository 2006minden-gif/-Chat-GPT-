<?php
/** Read-only diagnostic; no setup, schema writes, file changes, passwords or raw log lines. */
if (PHP_SAPI!=='cli') {http_response_code(404);exit;}
ini_set('display_errors','0');
$root='/home/n/neurodepro';$out=array('read_only'=>true,'php'=>PHP_VERSION,'files'=>array(),'extensions'=>array('pdo_mysql'=>extension_loaded('pdo_mysql'),'mbstring'=>extension_loaded('mbstring')));
foreach(array('public_html/.htaccess','public_html/privacy.php','public_html/api.php','private/app.php','private/config.php') as $path){
 $full=$root.'/'.$path;$out['files'][$path]=array('exists'=>is_file($full),'readable'=>is_readable($full));
 if(is_file($full)&&is_readable($full)&&$path!=='private/config.php')$out['files'][$path]['sha256']=hash_file('sha256',$full);
}
try {
 $c=require $root.'/private/config.php';
 if(!is_array($c))throw new RuntimeException('invalid_config_type');
 $out['config_keys']=array();foreach(array('app_url','db_host','db_name','db_user','db_password') as $key)$out['config_keys'][$key]=isset($c[$key])&&is_string($c[$key])&&($key==='db_password'||$c[$key]!=='');
 $out['app_url_expected']=isset($c['app_url'])&&rtrim($c['app_url'],'/')==='https://neurodelo.pro';
 $out['privacy']=array('approved'=>isset($c['privacy_policy_approved'])&&$c['privacy_policy_approved']===true,'version_valid'=>isset($c['privacy_policy_version'])&&is_string($c['privacy_policy_version'])&&preg_match('/^[A-Za-z0-9._-]{1,64}$/D',$c['privacy_policy_version'])===1,'file_readable'=>is_readable($root.'/private/privacy-policy.txt'));
 if(!in_array(false,$out['config_keys'],true)){
  $p=new PDO('mysql:host='.$c['db_host'].';port='.(isset($c['db_port'])?$c['db_port']:3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],array(PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION));
  $p->exec('SET SESSION TRANSACTION READ ONLY');$out['pdo']=true;$out['database_version']=$p->query('SELECT VERSION()')->fetchColumn();
  $out['tables']=array();foreach(array('nd_admin','nd_leads','nd_sessions','nd_limits','nd_schema_migrations') as $table){$q=$p->prepare('SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');$q->execute(array($table));$out['tables'][$table]=(bool)$q->fetchColumn();}
  if($out['tables']['nd_admin'])$out['admin_exists']=(bool)$p->query('SELECT id FROM nd_admin WHERE id=1')->fetchColumn();
 }
} catch(Throwable $e){$out['configuration_error']=array('type'=>get_class($e),'file'=>basename($e->getFile()),'line'=>$e->getLine());if($e instanceof PDOException)$out['configuration_error']['sqlstate']=(string)$e->getCode();}
$log=$root.'/error_log';$out['log_readable']=is_readable($log);$out['backend_events']=array();
if(is_file($log)&&is_readable($log)){
 $f=fopen($log,'rb');$size=filesize($log);if($size>262144)fseek($f,-262144,SEEK_END);$text=stream_get_contents($f);fclose($f);
 foreach(explode("\n",$text) as $line)if(preg_match('/NeuroDelo (\{.*\})/',$line,$match)){
  $event=json_decode($match[1],true);if(!is_array($event))continue;$safe=array();
  foreach(array('event','id','type','file','line','sqlstate') as $key)if(isset($event[$key]))$safe[$key]=$key==='file'?basename($event[$key]):$event[$key];
  $out['backend_events'][]=$safe;
 }
 $out['backend_events']=array_slice($out['backend_events'],-20);
}
echo json_encode($out,JSON_UNESCAPED_SLASHES),"\n";
