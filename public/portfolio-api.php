<?php
declare(strict_types=1);
ini_set('display_errors','0');require dirname(__DIR__).'/private/site.php';security_headers();header('X-Robots-Tag: noindex, nofollow');
try{
 $r=$_GET['r']??'';$method=$_SERVER['REQUEST_METHOD'];
 if($r==='login'&&$method==='POST'){
  same_origin();rate('portfolio-login',10);$d=input();$password=text_field($d,'password',256,true);$hash=query('SELECT password_hash FROM nd_admin WHERE id=1')->fetchColumn();if(!$hash||!password_verify($password,$hash))fail(401,'Неверный пароль.');
  $old=$_COOKIE['nd_session']??'';if(is_string($old))query('DELETE FROM nd_sessions WHERE token=? OR expires<=?',[hash('sha256',$old),time()]);$raw=bin2hex(random_bytes(32));$csrf=bin2hex(random_bytes(32));query('INSERT INTO nd_sessions(token,csrf,expires) VALUES (?,?,?)',[hash('sha256',$raw),$csrf,time()+28800]);session_cookie($raw,time()+28800);json_response(['ok'=>true,'csrf'=>$csrf]);
 }
 if($r==='media'&&in_array($method,['GET','HEAD'],true)){
  $id=filter_var($_GET['id']??0,FILTER_VALIDATE_INT);$f=query('SELECT * FROM nd_publication_media WHERE id=? AND deleted_at IS NULL AND purged_at IS NULL',[$id])->fetch();if(!$f||$f['kind']!=='upload')fail(404,'Файл не найден.');$allowed=false;
  if(($_GET['mode']??'')==='owner'){current_session();$allowed=true;}else{foreach(query("SELECT * FROM nd_publications WHERE kind='portfolio' AND state='PUBLISHED'")->fetchAll() as $p)if(site_live($p)&&in_array((int)$id,array_map('intval',array_column(site_version((int)$p['published_version_id'])['media']??[],'id')),true)){$allowed=true;break;}}
  if(!$allowed||!preg_match('/^[a-f0-9]{64}$/D',$f['storage_key']))fail(404,'Файл не опубликован.');$path=site_storage().'/'.$f['storage_key'];if(is_link($path)||!is_file($path)||filesize($path)!==(int)$f['size_bytes']||!hash_equals($f['checksum'],hash_file('sha256',$path)))fail(404,'Файл недоступен.');
  header('Content-Type: '.$f['mime']);header('Content-Disposition: inline; filename="portfolio-'.$id.'"');header('Content-Length: '.filesize($path));if($method!=='HEAD')readfile($path);exit;
 }
 $s=current_session($method!=='GET');
 if($r==='session'&&$method==='GET')json_response(['csrf'=>$s['csrf']]);
 if($r==='items'&&$method==='GET')json_response(['items'=>array_map(fn($p)=>site_item($p,true),query("SELECT * FROM nd_publications WHERE kind='portfolio' AND state<>'ARCHIVED' ORDER BY sort_order,id DESC")->fetchAll()),'categories'=>site_categories()]);
 if($method==='POST'){
  if($r==='logout'){query('DELETE FROM nd_sessions WHERE token=?',[$s['token']]);session_cookie('',1);json_response(['ok'=>true]);}
  if($r==='upload'){rate('portfolio-upload',60);json_response(site_upload());}
  $d=input();if($r==='save')json_response(site_save($d));
  if($r==='archive'){$id=$d['id']??null;if(!is_int($id))fail(422,'Проверьте работу.');$p=site_record($id);if((int)$p['version']!==($d['version']??null))fail(409,'Работа уже изменена. Обновите список.');$q=query("UPDATE nd_publications SET state='ARCHIVED',published_version_id=NULL,version=version+1 WHERE id=? AND version=?",[$id,$d['version']]);if($q->rowCount()!==1)fail(409,'Работа уже изменена.');json_response(['ok'=>true]);}
 }
 fail(404,'Действие не найдено.');
}catch(Throwable $e){error_log('NeuroDelo portfolio operation failed');fail(503,'Не удалось выполнить действие. Изменения не подтверждены; повторите попытку.');}
