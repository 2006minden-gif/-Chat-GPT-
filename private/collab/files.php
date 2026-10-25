<?php
declare(strict_types=1);
function cc_storage(bool $create=false):string{
 $root=dirname(__DIR__).'/collaboration-files';
 if(is_link($root))crm_fail(503,'Приватное хранилище недоступно.');
 if(!is_dir($root)&&(!$create||!mkdir($root,0700)))crm_fail(503,'Приватное хранилище недоступно.');
 $real=realpath($root);$private=realpath(dirname(__DIR__));if($real!==$private.'/collaboration-files')crm_fail(503,'Приватное хранилище недоступно.');
 if(PHP_SAPI!=='cli'){$web=realpath($_SERVER['DOCUMENT_ROOT']??'');if(!$web||$real===$web||str_starts_with($real,$web.'/'))crm_fail(503,'Хранилище должно находиться вне публичного каталога.');}return $real;
}
function cc_file(array $a,int $id,bool $lock=false):array{
 $r=crm_query('SELECT * FROM nd_cc_files WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');cc_project($a,(int)$r['project_id']);
 if($a['type']==='customer'&&($r['visibility']!=='customer'||$r['archived_at']!==null))crm_fail(404,'Запись не найдена.');if($r['mime']==='application/json'){require_once dirname(__DIR__).'/production/seal.php';prod_managed_file($a,$r);}return $r;
}
function cc_file_path(array $r):string{
 if(!preg_match('/^[a-f0-9]{64}$/D',$r['storage_key']))crm_fail(503,'Файл временно недоступен.');$path=cc_storage().'/'.$r['storage_key'];
 if(is_link($path)||!is_file($path)||filesize($path)!==(int)$r['size_bytes']||!hash_equals($r['checksum'],hash_file('sha256',$path)))crm_fail(503,'Файл временно недоступен. Свяжитесь с владельцем.');return $path;
}
function cc_validate_file(array $f):array{
 if(in_array($f['error']??UPLOAD_ERR_NO_FILE,[UPLOAD_ERR_INI_SIZE,UPLOAD_ERR_FORM_SIZE],true))crm_fail(422,'Файл превышает серверный лимит загрузки.');
 if(($f['error']??UPLOAD_ERR_NO_FILE)!==UPLOAD_ERR_OK||!isset($f['tmp_name'])||!is_string($f['tmp_name'])||!is_uploaded_file($f['tmp_name']))crm_fail(422,'Файл не загружен полностью. Выберите его и повторите отправку.');
 $size=filesize($f['tmp_name']);$max=min(10485760,max(1,(int)(config()['collaboration_file_max_bytes']??5242880)));
 if(!$size||$size>$max)crm_fail(422,'Файл пустой или превышает допустимый размер. Максимум: '.$max.' байт.');
 if(isset($f['full_path'])&&$f['full_path']!==($f['name']??''))crm_fail(422,'Пути в имени файла запрещены.');
 $name=$f['name']??'';if(!is_string($name)||!mb_check_encoding($name,'UTF-8')||mb_strlen($name)>190||preg_match('~[\x00-\x1f\x7f/\\\\]~',$name)||$name==='.'||str_contains($name,'..'))crm_fail(422,'Недопустимое имя файла.');
 $ext=strtolower(pathinfo($name,PATHINFO_EXTENSION));$allowed=['pdf'=>'application/pdf','jpg'=>'image/jpeg','jpeg'=>'image/jpeg','png'=>'image/png','webp'=>'image/webp','docx'=>'application/vnd.openxmlformats-officedocument.wordprocessingml.document','xlsx'=>'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'];
 if(!isset($allowed[$ext]))crm_fail(422,'Разрешены PDF, JPG, PNG, WebP, DOCX, XLSX.');
 if(!class_exists('finfo'))crm_fail(503,'Для загрузки требуется настройка модуля Fileinfo.');
 $mime=(new finfo(FILEINFO_MIME_TYPE))->file($f['tmp_name']);$bytes=file_get_contents($f['tmp_name']);
 if(preg_match('/<\?(?:php|=)|<script\b|^MZ|^\x7fELF/i',$bytes))crm_fail(422,'Обнаружен недопустимый исполняемый контент.');
 if(in_array($ext,['jpg','jpeg','png','webp'],true)){
  $image=@getimagesize($f['tmp_name']);if(!$image||($image['mime']??'')!==$allowed[$ext]||$mime!==$allowed[$ext]||$image[0]>12000||$image[1]>12000||$image[0]*$image[1]>40000000)crm_fail(422,'Формат изображения не соответствует файлу.');
 }elseif($ext==='pdf'){
  if($mime!=='application/pdf'||!str_starts_with($bytes,'%PDF-')||!str_contains(substr($bytes,-1024),'%%EOF')||preg_match('~/JavaScript|/JS\b|/Launch|/EmbeddedFile|/OpenAction|/RichMedia|/XFA~i',$bytes))crm_fail(422,'Разрешён только обычный PDF без активного содержимого.');
 }else{
  if(!class_exists('ZipArchive'))crm_fail(503,'Для DOCX/XLSX требуется модуль ZipArchive.');
  if(!in_array($mime,[$allowed[$ext],'application/zip'],true))crm_fail(422,'Формат документа не соответствует расширению.');
  $zip=new ZipArchive();if($zip->open($f['tmp_name'],ZipArchive::RDONLY)!==true)crm_fail(422,'Документ повреждён.');
  try{
   if($zip->numFiles>256)crm_fail(422,'Слишком сложный документ.');$total=0;$names=[];
   for($i=0;$i<$zip->numFiles;$i++){
    $s=$zip->statIndex($i);$n=$s['name'];if(isset($names[$n])||str_starts_with($n,'/')||str_contains($n,'..')||str_contains($n,'\\')||preg_match('~(^|/)(embeddings|activeX|vbaProject)|\.(bin|exe|dll|php|html|js|svg)$~i',$n)||($s['encryption_method']??0)!==0)crm_fail(422,'Документ содержит запрещённые компоненты.');$names[$n]=true;
    $entryExt=strtolower(pathinfo($n,PATHINFO_EXTENSION));if(!str_ends_with($n,'/')&&!in_array($entryExt,['xml','rels','png','jpg','jpeg','webp'],true))crm_fail(422,'Неподдерживаемое вложение внутри офисного документа.');
    $total+=$s['size'];if($s['size']>5242880||$total>20971520||($s['comp_size']>0&&$s['size']/$s['comp_size']>200))crm_fail(422,'Документ слишком велик после распаковки.');
    if(in_array($entryExt,['png','jpg','jpeg','webp'],true)){$imageBytes=$zip->getFromIndex($i,5242881);if($imageBytes===false||(new finfo(FILEINFO_MIME_TYPE))->buffer($imageBytes)!==$allowed[$entryExt])crm_fail(422,'Недопустимое изображение внутри документа.');}
    if(str_ends_with($n,'.xml')||str_ends_with($n,'.rels')){$xml=$zip->getFromIndex($i,5242881);if($xml===false||preg_match('/<!DOCTYPE|<!ENTITY|macroEnabled|TargetMode\s*=\s*[\x22\x27]External/i',$xml))crm_fail(422,'Активное или внешнее содержимое документа запрещено.');}
   }
   $main=$ext==='docx'?'word/document.xml':'xl/workbook.xml';$types=$zip->getFromName('[Content_Types].xml');
   if(!isset($names[$main])||!isset($names['_rels/.rels'])||!is_string($types)||!str_contains($types,$ext==='docx'?'wordprocessingml.document.main+xml':'spreadsheetml.sheet.main+xml'))crm_fail(422,'Это не поддерживаемый офисный документ.');
  }finally{$zip->close();}
 }
 return ['display_name'=>$name,'mime'=>$allowed[$ext],'size_bytes'=>$size,'checksum'=>hash_file('sha256',$f['tmp_name'])];
}
function cc_capacity(int $used,int $size,int $quota,int|float|false $free):void{if($used+$size>$quota||$free===false||$free<$size+16777216)crm_fail(507,'Недостаточно места в приватном хранилище.');}
function cc_cleanup_upload(string $path):string{
 // A commit error may have an unknown outcome. Never discard bytes on assumption alone.
 if(is_link($path)||!is_file($path)||!preg_match('/^[a-f0-9]{64}$/D',basename($path)))return 'retained';
 try{if(dirname($path)!==cc_storage())return 'retained';$exists=crm_query('SELECT 1 FROM nd_cc_files WHERE storage_key=? LIMIT 1',[basename($path)])->fetchColumn();}
 catch(Throwable $e){return 'retained_unknown';}
 if($exists)return 'retained';return @unlink($path)?'removed':'retained';
}
function cc_upload(array $a):array{
 $project=filter_var($_POST['project_id']??'',FILTER_VALIDATE_INT);if(!$project)crm_fail(422,'Выберите проект.');cc_project($a,$project,true);$meta=cc_validate_file($_FILES['file']??[]);
 $key=$_POST['request_key']??'';$visibility=$a['type']==='customer'?'customer':($_POST['visibility']??'internal');if(!in_array($visibility,['internal','customer'],true))crm_fail(422,'Выберите доступ к файлу.');
 $root=cc_storage(true);$lock=fopen($root.'/.quota.lock','c');if(!$lock||is_link($root.'/.quota.lock')||!flock($lock,LOCK_EX))crm_fail(503,'Хранилище занято. Повторите позже.');chmod($root.'/.quota.lock',0600);$stored=null;
 try{
  return cc_mutation($a,'upload',['request_key'=>$key,'project_id'=>$project,'meta'=>$meta,'visibility'=>$visibility],function()use($a,$project,$meta,$root,$visibility,&$stored){
   cc_project($a,$project,true,true);$used=0;foreach(new DirectoryIterator($root) as $entry){if($entry->isDot()||$entry->getFilename()==='.quota.lock')continue;if($entry->isLink()||!$entry->isFile())crm_fail(503,'Хранилище требует проверки владельцем.');$used+=$entry->getSize();}
   $quota=min(536870912,max(1,(int)(config()['collaboration_total_max_bytes']??104857600)));$free=disk_free_space($root);
   cc_capacity($used,$meta['size_bytes'],$quota,$free);
   $storage=bin2hex(random_bytes(32));$candidate=$root.'/'.$storage;if(file_exists($candidate)||!move_uploaded_file($_FILES['file']['tmp_name'],$candidate))crm_fail(503,'Не удалось сохранить файл. Повторите отправку.');$stored=$candidate;
   if(!chmod($stored,0600)||filesize($stored)!==$meta['size_bytes']||hash_file('sha256',$stored)!==$meta['checksum'])crm_fail(503,'Не удалось подтвердить сохранение файла.');
   crm_query('INSERT INTO nd_cc_files(project_id,storage_key,display_name,mime,size_bytes,checksum,actor_type,actor_id,visibility) VALUES (?,?,?,?,?,?,?,?,?)',[$project,$storage,$meta['display_name'],$meta['mime'],$meta['size_bytes'],$meta['checksum'],$a['type'],$a['id'],$visibility]);$id=(int)db()->lastInsertId();cc_event($a,$project,'file_uploaded');return ['ok'=>true,'id'=>$id,'file'=>cc_public_file(cc_file($a,$id))];
  });
 }catch(Throwable $e){if($stored)cc_cleanup_upload($stored);throw $e;}finally{flock($lock,LOCK_UN);fclose($lock);}
}
function cc_file_update(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'file/'.$id,$d,function()use($a,$id,$d){$f=cc_file($a,$id,true);if($f['mime']==='application/json'){require_once dirname(__DIR__).'/production/seal.php';prod_managed_file($a,$f,true);}cc_project($a,(int)$f['project_id'],true,true);crm_version($d,$f);
 $visibility=$d['visibility']??$f['visibility'];if(!in_array($visibility,['internal','customer'],true)||!isset($d['archived'])||!is_bool($d['archived']))crm_fail(422,'Проверьте параметры доступа.');
 crm_query('UPDATE nd_cc_files SET visibility=?,archived_at=?,version=version+1 WHERE id=?',[$visibility,$d['archived']?gmdate('Y-m-d H:i:s'):null,$id]);cc_event($a,(int)$f['project_id'],'file_access_changed');return ['ok'=>true,'file'=>cc_public_file(cc_file($a,$id))];});
}
function cc_download(array $a,int $id):never{
 $f=cc_file($a,$id);$path=cc_file_path($f);header('Content-Type: '.$f['mime']);header('X-Content-Type-Options: nosniff');header('Content-Disposition: attachment; filename="download"; filename*=UTF-8\'\''.rawurlencode($f['display_name']));header('Content-Length: '.$f['size_bytes']);header('Cache-Control: private, no-store');readfile($path);exit;
}
