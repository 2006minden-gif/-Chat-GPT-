<?php
declare(strict_types=1);
function cc_document(array $a,int $id,bool $lock=false):array{
 $d=crm_query('SELECT * FROM nd_cc_documents WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$d)crm_fail(404,'Запись не найдена.');cc_project($a,(int)$d['project_id']);
 if($a['type']==='customer'&&!crm_query("SELECT id FROM nd_cc_revisions WHERE document_id=? AND status IN ('sent','approved','changes_requested','finalized') LIMIT 1",[$id])->fetchColumn())crm_fail(404,'Запись не найдена.');return $d;
}
function cc_revision(array $a,int $id,bool $lock=false):array{
 $r=crm_query('SELECT * FROM nd_cc_revisions WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');$doc=cc_document($a,(int)$r['document_id']);
 if($a['type']==='customer'&&in_array($r['status'],['draft','ready'],true))crm_fail(404,'Запись не найдена.');
 $r['fields']=json_decode($r['body'],true,512,JSON_THROW_ON_ERROR);unset($r['body']);$r['document']=$doc;
 $files=crm_query('SELECT f.* FROM nd_cc_files f JOIN nd_cc_revision_files rf ON rf.file_id=f.id WHERE rf.revision_id=?'.($a['type']==='customer'?" AND f.visibility='customer' AND f.archived_at IS NULL":'').' ORDER BY f.id',[$id])->fetchAll();$r['files']=array_map('cc_public_file',$files);
 $r['approval']=crm_query('SELECT id,status,version,checksum,due_on,created_at FROM nd_cc_approvals WHERE revision_id=?',[$id])->fetch()?:null;
 if($r['approval'])$r['decision']=crm_query('SELECT decision,feedback,checksum,created_at FROM nd_cc_decisions WHERE approval_id=?',[$r['approval']['id']])->fetch()?:null;
 return $r;
}
function cc_fields(array $data):array{
 $fields=$data['fields']??[];if(!is_array($fields))crm_fail(422,'Проверьте разделы документа.');$out=[];
 foreach(['title','service','description','goal','requirements','functionality','design','constraints','deliverables','milestones','deadline','acceptance','comments'] as $key)$out[$key]=cc_text($fields,$key,$key==='title'?190:10000,false);
 if(strlen(json_encode($out,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR))>60000)crm_fail(422,'Документ слишком большой.');return $out;
}
function cc_snapshot_checksum(array $doc,array $fields,array $files):string{
 return hash('sha256',json_encode(['project_id'=>(int)$doc['project_id'],'kind'=>$doc['kind'],'stage_id'=>$doc['stage_id']===null?null:(int)$doc['stage_id'],'fields'=>$fields,'files'=>array_map(fn($f)=>['id'=>(int)$f['id'],'checksum'=>$f['checksum']],$files)],JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
}
function cc_save_revision(array $a,array $doc,array $d,?array $old=null):array{
 $fields=cc_fields($d);$project=cc_project($a,(int)$doc['project_id']);$fields['project_title']=$project['title'];$fields['customer_name']=crm_record('customers',(int)$project['customer_id'])['name'];$ids=$d['file_ids']??[];if(!is_array($ids))crm_fail(422,'Проверьте вложения.');$files=cc_files_for($a,(int)$doc['project_id'],$ids);usort($files,fn($x,$y)=>$x['id']<=>$y['id']);
 $hash=cc_snapshot_checksum($doc,$fields,$files);$body=json_encode($fields,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR);
 if($old){if($old['status']!=='draft')crm_fail(409,'Отправленная версия неизменяема. Создайте новую редакцию.');crm_version($d,$old);crm_query('UPDATE nd_cc_revisions SET body=?,checksum=?,version=version+1 WHERE id=?',[$body,$hash,$old['id']]);$id=(int)$old['id'];crm_query('DELETE FROM nd_cc_revision_files WHERE revision_id=?',[$id]);}
 else{crm_query('INSERT INTO nd_cc_revisions(document_id,revision_number,body,checksum) VALUES (?,?,?,?)',[$doc['id'],$doc['head_revision'],$body,$hash]);$id=(int)db()->lastInsertId();}
 foreach($files as $f)crm_query('INSERT INTO nd_cc_revision_files VALUES (?,?)',[$id,$f['id']]);cc_event($a,(int)$doc['project_id'],$old?'draft_saved':'revision_created');return ['ok'=>true,'id'=>$id,'revision'=>cc_revision($a,$id)];
}
function cc_create_document(array $a,int $project,array $d):array{
 cc_owner($a);return cc_mutation($a,'document-create/'.$project,$d,fn()=>cc_create_document_effect($a,$project,$d));
}
/** Validated effect shared with the transactional AI approval gateway. */
function cc_create_document_effect(array $a,int $project,array $d):array{cc_owner($a);cc_project($a,$project,true,true);$kind=$d['kind']??'';
 if(!in_array($kind,['specification','description','plan','deliverable','final','milestone'],true))crm_fail(422,'Выберите тип документа.');$title=cc_text($d,'title',190);$stage=$d['stage_id']??null;
 if($stage!==null){cc_id($stage);if(!crm_query('SELECT id FROM nd_project_stages WHERE id=? AND project_id=?',[$stage,$project])->fetchColumn())crm_fail(422,'Этап не принадлежит проекту.');}
 if($kind==='milestone'&&$stage===null)crm_fail(422,'Для согласования этапа выберите этап.');
 crm_query('INSERT INTO nd_cc_documents(project_id,stage_id,kind,title) VALUES (?,?,?,?)',[$project,$stage,$kind,$title]);$id=(int)db()->lastInsertId();$doc=cc_document($a,$id);$fields=$d['fields']??[];if(!is_array($fields))crm_fail(422,'Проверьте разделы.');$fields['title']=$fields['title']??$title;$d['fields']=$fields;return cc_save_revision($a,$doc,$d);
}
function cc_new_revision(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'revision-create/'.$id,$d,function()use($a,$id,$d){$doc=cc_document($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$doc);if($doc['archived_at']!==null)crm_fail(409,'Сначала восстановите документ.');
 $prev=crm_query('SELECT * FROM nd_cc_revisions WHERE document_id=? AND revision_number=? FOR UPDATE',[$id,$doc['head_revision']])->fetch();if($prev['status']==='draft')crm_fail(409,'Сначала завершите работу с текущим черновиком.');
 crm_query("UPDATE nd_cc_approvals a JOIN nd_cc_revisions r ON a.revision_id=r.id SET a.status='withdrawn',a.version=a.version+1 WHERE r.document_id=? AND a.status='pending'",[$id]);
 crm_query('UPDATE nd_cc_documents SET head_revision=head_revision+1,version=version+1 WHERE id=?',[$id]);$doc['head_revision']++;$doc['version']++;
 if(!isset($d['fields']))$d['fields']=json_decode($prev['body'],true);if(!isset($d['file_ids']))$d['file_ids']=array_map(fn($r)=>(int)$r['file_id'],crm_query('SELECT file_id FROM nd_cc_revision_files WHERE revision_id=?',[$prev['id']])->fetchAll());
 return cc_save_revision($a,$doc,$d);});
}
function cc_update_revision(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'revision-update/'.$id,$d,function()use($a,$id,$d){$r=cc_revision($a,$id);$doc=cc_document($a,(int)$r['document_id'],true);$r=cc_revision($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);if((int)$r['revision_number']!==(int)$doc['head_revision']||$doc['archived_at']!==null)crm_fail(409,'Эта редакция уже не текущая.');return cc_save_revision($a,$doc,$d,$r);});
}
function cc_ready(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'revision-ready/'.$id,$d,function()use($a,$id,$d){$r=cc_revision($a,$id);$doc=cc_document($a,(int)$r['document_id'],true);$r=cc_revision($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$r);
 if($r['status']!=='draft'||(int)$r['revision_number']!==(int)$doc['head_revision']||$doc['archived_at']!==null)crm_fail(409,'Подготовить можно только текущий черновик.');
 if($r['fields']['title']===''||mb_strlen($r['fields']['acceptance'])<5)crm_fail(422,'Заполните название и понятные критерии приёмки.');
 crm_query("UPDATE nd_cc_revisions SET status='ready',version=version+1 WHERE id=?",[$id]);cc_event($a,(int)$doc['project_id'],'document_ready');return ['ok'=>true,'id'=>$id,'revision'=>cc_revision($a,$id)];});
}
function cc_document_lists(array $a,int $project):array{
 cc_project($a,$project);$where=$a['type']==='customer'?" AND r.status IN ('sent','approved','changes_requested','finalized')":'';
 $rows=crm_query('SELECT d.id,d.kind,d.title,d.project_id,d.archived_at,d.head_revision,d.version,r.id AS revision_id,r.revision_number,r.status,r.sent_at,r.archived_at AS revision_archived_at FROM nd_cc_documents d JOIN nd_cc_revisions r ON r.document_id=d.id WHERE d.project_id=?'.$where.' ORDER BY d.id DESC,r.revision_number DESC LIMIT 25 OFFSET '.((cc_page()-1)*25),[$project])->fetchAll();
 return ['ok'=>true,'items'=>$rows,'page'=>cc_page(),'page_size'=>25];
}
function cc_archive_document(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'document-archive/'.$id,$d,function()use($a,$id,$d){$doc=cc_document($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$doc);if(!isset($d['archived'])||!is_bool($d['archived']))crm_fail(422,'Выберите архивное состояние.');
 crm_query('UPDATE nd_cc_documents SET archived_at=?,version=version+1 WHERE id=?',[$d['archived']?gmdate('Y-m-d H:i:s'):null,$id]);if($d['archived'])crm_query("UPDATE nd_cc_approvals a JOIN nd_cc_revisions r ON r.id=a.revision_id SET a.status='withdrawn',a.version=a.version+1 WHERE r.document_id=? AND a.status='pending'",[$id]);cc_event($a,(int)$doc['project_id'],'document_archived');return ['ok'=>true,'id'=>$id];});
}

function cc_archive_revision(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'revision-archive/'.$id,$d,function()use($a,$id,$d){$r=cc_revision($a,$id);$doc=cc_document($a,(int)$r['document_id'],true);$r=cc_revision($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$r);
 if((int)$r['revision_number']===(int)$doc['head_revision'])crm_fail(409,'Архивировать отдельно можно только прежнюю редакцию.');
 crm_query('UPDATE nd_cc_revisions SET archived_at=UTC_TIMESTAMP(),version=version+1 WHERE id=?',[$id]);cc_event($a,(int)$doc['project_id'],'old_revision_archived');return ['ok'=>true,'id'=>$id];});
}
