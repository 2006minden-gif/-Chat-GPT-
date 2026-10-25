<?php
declare(strict_types=1);
function cat_manage(string $kind,int $id,string $action,array $d):array{
 return crm_idempotent('catalog:manage:'.$kind.':'.$id.':'.$action,$d,function()use($kind,$id,$action,$d){
 $table=$kind==='template'?'nd_catalog_templates':'nd_catalog_services';$versions=$kind==='template'?'nd_catalog_template_versions':'nd_catalog_service_versions';$fk=$kind.'_id';$old=$id?cat_record($kind,$id,true):null;if($old)crm_version($d,$old);
 if($action==='save'){
  if($old&&$old['state']==='ARCHIVED')crm_fail(409,'Архивная запись закрыта для изменений.');$body=$kind==='template'?cat_template($d['body']??null):cat_service($d['body']??null);
  if(!$old){if($kind==='template')crm_query('INSERT INTO nd_catalog_templates(title) VALUES (?)',[$body['title']]);else{$slug=cc_text($d,'slug',80);if(!preg_match('/^[a-z][a-z0-9-]{2,79}$/D',$slug))crm_fail(422,'Адрес услуги: 3–80 латинских букв, цифр и дефисов.');crm_query('INSERT INTO nd_catalog_services(slug) VALUES (?)',[$slug]);}$id=(int)db()->lastInsertId();$n=1;}else{$n=(int)$old['head_revision']+1;if($kind==='template')crm_query('UPDATE nd_catalog_templates SET title=? WHERE id=?',[$body['title'],$id]);crm_query('UPDATE '.$table.' SET head_revision=?,version=version+1 WHERE id=?',[$n,$id]);}
  $raw=ai_json($body);if($kind==='template')crm_query('INSERT INTO '.$versions.'(template_id,revision_number,body,checksum) VALUES (?,?,?,?)',[$id,$n,$raw,hash('sha256',$raw)]);
  else{$tid=cc_id($d['template_version_id']??null);$t=cat_version('template',$tid);$parent=cat_record('template',(int)$t['template_id']);if(!$t['published_at']||$parent['state']!=='PUBLISHED')crm_fail(422,'Выберите опубликованную редакцию анкеты.');$questions=[];foreach($t['data']['steps'] as $step)foreach($step['questions'] as $q)$questions[$q['id']]=$q;foreach($body['packages'] as $p)foreach($p['quantity_rules'] as $rule)if(!isset($questions[$rule['question']])||$questions[$rule['question']]['type']!=='number')crm_fail(422,'Правило количества должно ссылаться на числовой вопрос анкеты.');crm_query('INSERT INTO '.$versions.'(service_id,template_version_id,revision_number,body,checksum) VALUES (?,?,?,?,?)',[$id,$tid,$n,$raw,hash('sha256',$raw)]);}
  return ['ok'=>true,'id'=>$id,'version_id'=>(int)db()->lastInsertId(),'record'=>cat_record($kind,$id)];
 }
 if(!$old)crm_fail(404,'Запись не найдена.');if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите действие владельца.');
 if($action==='publish'){
  if($old['state']==='ARCHIVED')crm_fail(409,'Нельзя публиковать архивную запись.');$v=crm_query('SELECT id FROM '.$versions.' WHERE '.$fk.'=? AND revision_number=?',[$id,$old['head_revision']])->fetchColumn();$v=cat_version($kind,(int)$v);if(($d['checksum']??null)!==$v['checksum'])crm_fail(409,'Подтвердите точную редакцию для публикации.');
  if($kind==='template'){cat_template($v['data']);crm_query('UPDATE nd_catalog_template_versions SET published_at=COALESCE(published_at,UTC_TIMESTAMP()) WHERE id=?',[$v['id']]);crm_query("UPDATE nd_catalog_templates SET state='PUBLISHED',version=version+1 WHERE id=?",[$id]);}
  else{cat_service($v['data']);$t=cat_version('template',(int)$v['template_version_id']);if(!$t['published_at']||cat_record('template',(int)$t['template_id'])['state']!=='PUBLISHED')crm_fail(409,'Анкета снята с публикации.');crm_query('UPDATE nd_catalog_service_versions SET published_by=1,published_at=COALESCE(published_at,UTC_TIMESTAMP()) WHERE id=?',[$v['id']]);crm_query("UPDATE nd_catalog_services SET state='PUBLISHED',published_revision=?,version=version+1 WHERE id=?",[$v['revision_number'],$id]);}
 }elseif(in_array($action,['unpublish','archive'],true))crm_query('UPDATE '.$table.' SET state=?,version=version+1 WHERE id=?',[$action==='archive'?'ARCHIVED':'UNPUBLISHED',$id]);else crm_fail(404,'Действие не найдено.');
 return ['ok'=>true,'id'=>$id,'record'=>cat_record($kind,$id)];
 });
}
function cat_owner_detail(string $kind,int $id):array{$r=cat_record($kind,$id);$table=$kind==='template'?'nd_catalog_template_versions':'nd_catalog_service_versions';$v=crm_query('SELECT id FROM '.$table.' WHERE '.$kind.'_id=? ORDER BY revision_number DESC LIMIT 20',[$id])->fetchAll();$r['versions']=array_map(fn($x)=>cat_version($kind,(int)$x['id']),$v);return ['ok'=>true,'record'=>$r];}
