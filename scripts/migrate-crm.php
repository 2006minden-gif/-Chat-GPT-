<?php
/** Explicit CLI only; no deployment integration. Maintenance window + private DB backup required. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');$pdo=null;$locked=false;
try {
 $op=$argv[1]??'status';if(count($argv)>2||!in_array($op,['up','down','status'],true))throw new RuntimeException();
 require dirname(__DIR__).'/private/app.php';$pdo=db();$pdo->exec("SET time_zone='+00:00'");
 $q=$pdo->prepare('SELECT GET_LOCK(?,0)');$q->execute(['nd_migrate_'.substr(hash('sha256',config()['db_name']),0,40)]);
 if((int)$q->fetchColumn()!==1)throw new RuntimeException();$locked=true;
 $dir=dirname(__DIR__).'/database/migrations/006_crm_operations/';$up=file_get_contents($dir.'up.sql');$down=file_get_contents($dir.'down.sql');
 $split=fn($s)=>array_values(array_filter(array_map('trim',explode(';',preg_replace('/^--[^\n]*$/m','',$s)))));
 $q=$pdo->query("SELECT * FROM nd_schema_migrations WHERE version='006_crm_operations'");$row=$q->fetch();
 if($op==='status'){echo json_encode(['state'=>$row['state']??'not_applied','completed_steps'=>$row['completed_steps']??0]);}
 else {
  foreach(['004_crm_foundation','005_customer_auth'] as $v){$q=$pdo->prepare('SELECT * FROM nd_schema_migrations WHERE version=?');$q->execute([$v]);$dep=$q->fetch();$d=dirname(__DIR__).'/database/migrations/'.$v.'/';if(!$dep||$dep['state']!=='applied'||$dep['up_checksum']!==hash_file('sha256',$d.'up.sql')||$dep['down_checksum']!==hash_file('sha256',$d.'down.sql'))throw new RuntimeException();}
  if($row&&($row['up_checksum']!==hash('sha256',$up)||$row['down_checksum']!==hash('sha256',$down)))throw new RuntimeException();
  if($pdo->query("SELECT 1 FROM nd_schema_migrations WHERE version>'006_crm_operations' LIMIT 1")->fetchColumn())throw new RuntimeException();
  if($op==='up'){
   if($row&&$row['state']!=='applied')throw new RuntimeException();
   if(!$row){
    foreach(['nd_crm_requests','nd_crm_conversions','nd_crm_notifications'] as $t){$q=$pdo->prepare('SELECT 1 FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=?');$q->execute([$t]);if($q->fetchColumn())throw new RuntimeException();}
    foreach(['nd_deals'=>['due_on','loss_reason'],'nd_orders'=>['due_on','notes'],'nd_employees'=>['position']] as $t=>$cols)foreach($cols as $col){$q=$pdo->prepare('SELECT 1 FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=? AND column_name=?');$q->execute([$t,$col]);if($q->fetchColumn())throw new RuntimeException();}
    $pdo->prepare("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state) VALUES ('006_crm_operations',?,?,'applying')")->execute([hash('sha256',$up),hash('sha256',$down)]);
    foreach($split($up) as $i=>$sql){$pdo->exec($sql);$pdo->prepare("UPDATE nd_schema_migrations SET completed_steps=? WHERE version='006_crm_operations'")->execute([$i+1]);}
    $pdo->exec("UPDATE nd_schema_migrations SET state='applied',applied_at=UTC_TIMESTAMP() WHERE version='006_crm_operations'");
   }
   echo "006 applied\n";
  }elseif($row){
   // Empty-only rollback. Never discard operational history, fields or idempotency receipts.
   if($row['state']!=='applied')throw new RuntimeException();
   $pdo->exec('LOCK TABLES nd_deals WRITE,nd_orders WRITE,nd_employees WRITE,nd_crm_requests WRITE,nd_crm_conversions WRITE,nd_crm_notifications WRITE,nd_schema_migrations WRITE');
   foreach(['nd_crm_requests','nd_crm_conversions','nd_crm_notifications'] as $t)if($pdo->query('SELECT 1 FROM '.$t.' LIMIT 1')->fetchColumn())throw new RuntimeException();
   foreach(['nd_deals'=>'due_on IS NOT NULL OR loss_reason IS NOT NULL','nd_orders'=>'due_on IS NOT NULL OR notes IS NOT NULL','nd_employees'=>'position IS NOT NULL'] as $t=>$w)if($pdo->query('SELECT 1 FROM '.$t.' WHERE '.$w.' LIMIT 1')->fetchColumn())throw new RuntimeException();
   foreach($split($down) as $sql)$pdo->exec($sql);
   $pdo->exec("DELETE FROM nd_schema_migrations WHERE version='006_crm_operations'");echo "006 rolled back\n";
  }else echo "006 not applied\n";
 }
}catch(Throwable $e){fwrite(STDERR,"Migration stopped safely. Check dependencies/checksums, maintenance lock, partial state and empty-only rollback requirements. Restore a verified private backup for partial DDL; do not rerun or force.\n");exit(1);}
finally{if($pdo&&$locked){$pdo->exec('UNLOCK TABLES');$q=$pdo->prepare('SELECT RELEASE_LOCK(?)');$q->execute(['nd_migrate_'.substr(hash('sha256',config()['db_name']),0,40)]);}}
