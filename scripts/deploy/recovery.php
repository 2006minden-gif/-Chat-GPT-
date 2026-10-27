<?php
/** Private, actual-data MySQL recovery rehearsal. Never restores over source tables. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
final class RecoveryFailure extends RuntimeException {}
function nr_need(bool $condition,string $code):void{if(!$condition)throw new RecoveryFailure($code);}
function nr_ident(string $name):string{nr_need((bool)preg_match('/^[A-Za-z_][A-Za-z0-9_]{0,63}$/D',$name),'recovery_identifier_invalid');return '`'.$name.'`';}
function nr_pdo(array $c):PDO{return new PDO('mysql:host='.$c['db_host'].';port='.($c['db_port']??3306).';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_EMULATE_PREPARES=>false,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC,PDO::ATTR_STRINGIFY_FETCHES=>true,PDO::MYSQL_ATTR_MULTI_STATEMENTS=>false]);}
function nr_file(string $path,string $body):void{nr_need(!file_exists($path)&&!is_link($path),'recovery_path_collision');$h=fopen($path,'x');nr_need(is_resource($h),'recovery_file_failed');try{chmod($path,0600);nr_need(fwrite($h,$body)===strlen($body),'recovery_file_failed');fflush($h);if(function_exists('fsync'))fsync($h);}finally{fclose($h);}}
function nr_encoded(array $values):array{return array_map(static fn($v)=>$v===null?null:base64_encode((string)$v),array_values($values));}
function nr_rows(PDO $pdo,string $table,array $meta,callable $row):array{
 $order=implode(',',array_map('nr_ident',$meta['primary']));
 $q=$pdo->query('SELECT '.implode(',',array_map('nr_ident',$meta['columns'])).' FROM '.nr_ident($table).' ORDER BY '.$order);
 $hash=hash_init('sha256');$count=0;
 while($values=$q->fetch(PDO::FETCH_NUM)){$encoded=nr_encoded($values);$line=json_encode($encoded,JSON_THROW_ON_ERROR)."\n";hash_update($hash,$line);$row($encoded);$count++;}
 $q->closeCursor();return ['rows'=>$count,'sha256'=>hash_final($hash)];
}
function nr_snapshot(PDO $pdo,string $folder):array{
 nr_need(!file_exists($folder)&&!is_link($folder),'recovery_path_collision');nr_need(mkdir($folder,0700,true),'recovery_directory_failed');
 foreach(['TRIGGERS'=>'TRIGGER_SCHEMA','ROUTINES'=>'ROUTINE_SCHEMA','EVENTS'=>'EVENT_SCHEMA'] as $kind=>$field)nr_need((int)$pdo->query('SELECT COUNT(*) FROM information_schema.'.$kind.' WHERE '.$field.'=DATABASE()')->fetchColumn()===0,'recovery_schema_objects_unsupported');
 $tables=$pdo->query('SELECT TABLE_NAME,TABLE_TYPE,ENGINE,DATA_LENGTH,INDEX_LENGTH FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() ORDER BY TABLE_NAME')->fetchAll();
 nr_need(count($tables)>0&&count($tables)<=500,'recovery_table_set_unsupported');$meta=[];$size=0;
 foreach($tables as $t){$name=$t['TABLE_NAME'];nr_need((bool)preg_match('/^nd_[A-Za-z0-9_]+$/D',$name)&&$t['TABLE_TYPE']==='BASE TABLE'&&$t['ENGINE']==='InnoDB','recovery_table_set_unsupported');$size+=(int)$t['DATA_LENGTH']+(int)$t['INDEX_LENGTH'];
  $create=$pdo->query('SHOW CREATE TABLE '.nr_ident($name))->fetch(PDO::FETCH_NUM)[1];
  nr_need(!preg_match('/\b(DATA DIRECTORY|INDEX DIRECTORY|TABLESPACE|PARTITION BY)\b/i',$create),'recovery_schema_unsupported');
  $fields=$pdo->query('SHOW COLUMNS FROM '.nr_ident($name))->fetchAll();foreach($fields as $f)nr_need(!str_contains(strtoupper($f['Extra']),'GENERATED'),'recovery_schema_unsupported');
  $keys=$pdo->query('SHOW INDEX FROM '.nr_ident($name)." WHERE Key_name='PRIMARY'")->fetchAll();usort($keys,fn($a,$b)=>(int)$a['Seq_in_index']<=>(int)$b['Seq_in_index']);nr_need(count($keys)>0,'recovery_primary_key_required');
  $meta[$name]=['create'=>$create,'columns'=>array_column($fields,'Field'),'primary'=>array_column($keys,'Column_name')];
 }
 nr_need(disk_free_space($folder)>max(16777216,$size*3),'recovery_insufficient_space');
 $foreign=$pdo->query('SELECT TABLE_NAME,CONSTRAINT_NAME,COLUMN_NAME,REFERENCED_TABLE_SCHEMA,REFERENCED_TABLE_NAME,REFERENCED_COLUMN_NAME,ORDINAL_POSITION FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA=DATABASE() AND REFERENCED_TABLE_NAME IS NOT NULL ORDER BY TABLE_NAME,CONSTRAINT_NAME,ORDINAL_POSITION')->fetchAll();
 $database=(string)$pdo->query('SELECT DATABASE()')->fetchColumn();
 foreach($foreign as $fk)nr_need($fk['REFERENCED_TABLE_SCHEMA']===$database&&isset($meta[$fk['TABLE_NAME']],$meta[$fk['REFERENCED_TABLE_NAME']]),'recovery_external_reference');
 $path=$folder.'/rows.jsonl';$h=fopen($path,'x');nr_need(is_resource($h),'recovery_file_failed');chmod($path,0600);
 $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');$pdo->exec('SET TRANSACTION READ ONLY');$pdo->exec('START TRANSACTION WITH CONSISTENT SNAPSHOT');
 try{
  foreach($meta as $name=>&$table){$table['data']=nr_rows($pdo,$name,$table,function($values)use($h,$name){$line=json_encode([$name,$values],JSON_THROW_ON_ERROR)."\n";nr_need(fwrite($h,$line)===strlen($line),'recovery_file_failed');});}unset($table);
  fflush($h);if(function_exists('fsync'))fsync($h);$pdo->commit();
 }catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}finally{fclose($h);}
 $manifest=['format'=>'neurodelo-private-db-v1','created_at'=>gmdate('c'),'tables'=>$meta,'foreign_keys'=>$foreign,'data_sha256'=>hash_file('sha256',$path)];
 nr_file($folder.'/schema.json',json_encode($manifest,JSON_THROW_ON_ERROR));
 return $manifest;
}
function nr_restore_verify(PDO $pdo,string $folder):array{
 foreach(['schema.json','rows.jsonl'] as $file)nr_need(is_file($folder.'/'.$file)&&!is_link($folder.'/'.$file),'recovery_backup_missing');
 $manifest=json_decode(file_get_contents($folder.'/schema.json'),true,512,JSON_THROW_ON_ERROR);
 nr_need(($manifest['format']??'')==='neurodelo-private-db-v1'&&hash_file('sha256',$folder.'/rows.jsonl')===$manifest['data_sha256'],'recovery_backup_checksum_mismatch');
 $tables=$manifest['tables'];$prefix='nd_r_'.bin2hex(random_bytes(6)).'_';$map=[];$created=[];$proof=null;$clean=false;
 foreach($tables as $name=>$meta){nr_ident($name);$map[$name]=$prefix.substr(hash('sha256',$name),0,24);}
 nr_need(count(array_unique($map))===count($map),'recovery_shadow_collision');
 $q=$pdo->prepare('SELECT COUNT(*) FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=?');foreach($map as $name){$q->execute([$name]);nr_need((int)$q->fetchColumn()===0,'recovery_shadow_collision');}
 nr_file($folder.'/shadow-plan.json',json_encode(['prefix'=>$prefix,'tables'=>array_values($map),'source_tables'=>array_keys($map)],JSON_THROW_ON_ERROR));
 try{
  $pdo->exec('SET FOREIGN_KEY_CHECKS=0');
  foreach($tables as $name=>$meta){
   nr_need(str_starts_with($meta['create'],'CREATE TABLE '.nr_ident($name)),'recovery_schema_unsupported');
   $sql=preg_replace('/^CREATE TABLE `[^`]+`/','CREATE TABLE '.nr_ident($map[$name]),$meta['create'],1);
   $sql=preg_replace_callback('/CONSTRAINT `([^`]+)`/',fn($m)=>'CONSTRAINT '.nr_ident($prefix.substr(hash('sha256',$name.':'.$m[1]),0,28)),$sql);
   $sql=preg_replace_callback('/REFERENCES `([^`]+)`/',function($m)use($map){nr_need(isset($map[$m[1]]),'recovery_external_reference');return 'REFERENCES '.nr_ident($map[$m[1]]);},$sql);
   $pdo->exec($sql);$created[]=$map[$name];
  }
  $statements=[];$counts=array_fill_keys(array_keys($tables),0);$h=fopen($folder.'/rows.jsonl','r');nr_need(is_resource($h),'recovery_backup_missing');
  try{while(($line=fgets($h,16777217))!==false){nr_need(strlen($line)<16777216&&str_ends_with($line,"\n"),'recovery_backup_row_invalid');$row=json_decode($line,true,512,JSON_THROW_ON_ERROR);nr_need(is_array($row)&&count($row)===2&&isset($tables[$row[0]])&&is_array($row[1]),'recovery_backup_row_invalid');[$name,$values]=$row;$meta=$tables[$name];nr_need(count($values)===count($meta['columns']),'recovery_backup_row_invalid');
    $decoded=[];foreach($values as $v){nr_need($v===null||is_string($v),'recovery_backup_row_invalid');$decoded[]=$v===null?null:base64_decode($v,true);nr_need(end($decoded)!==false,'recovery_backup_row_invalid');}
    $statements[$name]??=$pdo->prepare('INSERT INTO '.nr_ident($map[$name]).' ('.implode(',',array_map('nr_ident',$meta['columns'])).') VALUES ('.implode(',',array_fill(0,count($decoded),'?')).')');$statements[$name]->execute($decoded);$counts[$name]++;
   }nr_need(feof($h),'recovery_backup_read_failed');}finally{fclose($h);}
  nr_need(hash_file('sha256',$folder.'/rows.jsonl')===$manifest['data_sha256'],'recovery_backup_checksum_mismatch');
  $pdo->exec('SET FOREIGN_KEY_CHECKS=1');$checks=[];
  foreach($tables as $name=>$meta){$actual=nr_rows($pdo,$map[$name],$meta,static function($unused){});nr_need($actual===$meta['data']&&$counts[$name]===$actual['rows'],'recovery_row_verification_failed');$checks[$name]=$actual;}
  $constraints=[];foreach($manifest['foreign_keys'] as $fk)$constraints[$fk['TABLE_NAME'].':'.$fk['CONSTRAINT_NAME']][]=$fk;
  foreach($constraints as $fields){$first=$fields[0];$on=[];$nonnull=[];foreach($fields as $f){$on[]='c.'.nr_ident($f['COLUMN_NAME']).'=p.'.nr_ident($f['REFERENCED_COLUMN_NAME']);$nonnull[]='c.'.nr_ident($f['COLUMN_NAME']).' IS NOT NULL';}
   $sql='SELECT 1 FROM '.nr_ident($map[$first['TABLE_NAME']]).' c LEFT JOIN '.nr_ident($map[$first['REFERENCED_TABLE_NAME']]).' p ON '.implode(' AND ',$on).' WHERE '.implode(' AND ',$nonnull).' AND p.'.nr_ident($first['REFERENCED_COLUMN_NAME']).' IS NULL LIMIT 1';nr_need($pdo->query($sql)->fetchColumn()===false,'recovery_foreign_key_verification_failed');
  }
  $proof=['verified'=>true,'backup_sha256'=>$manifest['data_sha256'],'schema_sha256'=>hash_file('sha256',$folder.'/schema.json'),'tables_verified'=>count($checks),'rows_verified'=>array_sum(array_column($checks,'rows')),'foreign_keys_verified'=>count($constraints),'source_data_written'=>false];
 }finally{
  $pdo->exec('SET FOREIGN_KEY_CHECKS=0');foreach(array_reverse($created) as $name){nr_need(str_starts_with($name,$prefix)&&in_array($name,$map,true),'recovery_cleanup_refused');$pdo->exec('DROP TABLE '.nr_ident($name));}
  $pdo->exec('SET FOREIGN_KEY_CHECKS=1');$clean=true;
 }
 nr_need($proof!==null&&$clean,'recovery_verification_failed');$proof['shadow_tables_removed']=true;
 nr_file($folder.'/verified.json',json_encode($proof,JSON_THROW_ON_ERROR));return $proof;
}
function nr_rehearse(array $config,string $folder):array{
 $source=nr_pdo($config);$lock='nd_migrate_'.substr(hash('sha256',$config['db_name']),0,40);$q=$source->prepare('SELECT GET_LOCK(?,0)');$q->execute([$lock]);nr_need((int)$q->fetchColumn()===1,'recovery_migration_busy');
 try{nr_snapshot($source,$folder);return nr_restore_verify(nr_pdo($config),$folder);}
 finally{$q=$source->prepare('SELECT RELEASE_LOCK(?)');$q->execute([$lock]);}
}
