<?php
declare(strict_types=1);
function cc_acceptance_target(array $a,array $doc,bool $lock=true):?int{
 $p=cc_project($a,(int)$doc['project_id'],true,$lock);
 if($doc['kind']==='milestone'){$stage=crm_query('SELECT * FROM nd_project_stages WHERE id=? AND project_id=?'.($lock?' FOR UPDATE':''),[$doc['stage_id'],$doc['project_id']])->fetch();if(!$stage||$stage['status']!=='completed')crm_fail(409,'Этап ещё не завершён. Сначала выполните критерии приёмки.');return (int)$stage['version'];}
 if($doc['kind']==='final'){$progress=crm_progress((int)$p['id']);if(!$progress['total']||$progress['percent']!==100)crm_fail(409,'Сначала завершите все этапы проекта.');return (int)$p['version'];}
 return null;
}
function cc_submit(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'submit/'.$id,$d,function()use($a,$id,$d){$r=cc_revision($a,$id);$doc=cc_document($a,(int)$r['document_id'],true);$r=cc_revision($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$r);
 if($r['status']!=='ready'||(int)$r['revision_number']!==(int)$doc['head_revision']||$doc['archived_at']!==null)crm_fail(409,'Отправить можно только подготовленную текущую версию.');
 if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите отправку клиенту точной версии документа.');
 $ids=array_map(fn($row)=>(int)$row['file_id'],crm_query('SELECT file_id FROM nd_cc_revision_files WHERE revision_id=? ORDER BY file_id',[$id])->fetchAll());$files=cc_files_for($a,(int)$doc['project_id'],$ids,true);
 if(!hash_equals($r['checksum'],cc_snapshot_checksum($doc,$r['fields'],$files)))crm_fail(409,'Снимок документа изменился. Требуется проверка владельцем.');
 if($doc['kind']==='deliverable'&&!$files)crm_fail(422,'Прикрепите результат работы и явно откройте доступ клиенту.');
 $target=cc_acceptance_target($a,$doc);$due=$d['due_on']??null;if($due!==null){if(!is_string($due))crm_fail(422,'Проверьте срок согласования.');$date=DateTimeImmutable::createFromFormat('!Y-m-d',$due);if(!$date||$date->format('Y-m-d')!==$due)crm_fail(422,'Проверьте срок согласования.');}
 crm_query("UPDATE nd_cc_revisions SET status='sent',sent_at=UTC_TIMESTAMP(),version=version+1 WHERE id=?",[$id]);
 crm_query('INSERT INTO nd_cc_approvals(revision_id,checksum,target_version,due_on) VALUES (?,?,?,?)',[$id,$r['checksum'],$target,$due]);$aid=(int)db()->lastInsertId();cc_event($a,(int)$doc['project_id'],'submitted',['document_kind'=>$doc['kind']]);return ['ok'=>true,'id'=>$aid,'revision'=>cc_revision($a,$id)];});
}
function cc_approval(array $a,int $id,bool $lock=false):array{
 $r=crm_query('SELECT * FROM nd_cc_approvals WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');$rev=cc_revision($a,(int)$r['revision_id'],$lock);$r['revision']=$rev;return $r;
}
function cc_decide(array $a,int $id,array $d):array{
 if($a['type']!=='customer')crm_fail(403,'Решение принимает клиент.');
 return cc_mutation($a,'decide/'.$id,$d,function()use($a,$id,$d){
  $approval=cc_approval($a,$id);$doc=cc_document($a,(int)$approval['revision']['document_id'],true);cc_project($a,(int)$doc['project_id'],true,true);
  $approval=cc_approval($a,$id,true);crm_version($d,$approval);$r=$approval['revision'];
  if($approval['status']!=='pending'||$r['status']!=='sent'||(int)$r['revision_number']!==(int)$doc['head_revision']||$doc['archived_at']!==null)crm_fail(409,'Эта версия больше не ожидает решения. Откройте актуальную редакцию.');
  $checksum=$d['checksum']??'';if(!is_string($checksum)||!hash_equals($approval['checksum'],$checksum)||!hash_equals($r['checksum'],$checksum))crm_fail(409,'Версия изменилась. Откройте её заново.');
  $ids=array_map(fn($f)=>(int)$f['file_id'],crm_query('SELECT file_id FROM nd_cc_revision_files WHERE revision_id=? ORDER BY file_id',[$r['id']])->fetchAll());$files=cc_files_for($a,(int)$doc['project_id'],$ids,true);
  if(!hash_equals(cc_snapshot_checksum($doc,$r['fields'],$files),$checksum))crm_fail(409,'Контрольная сумма версии не подтверждена.');
  $target=cc_acceptance_target($a,$doc);if($target!==null&&$target!==(int)$approval['target_version'])crm_fail(409,'Состояние проекта или этапа изменилось. Требуется новая редакция.');
  $account=ca_account($a['id'],true);if(!ca_account_allowed($account)||!ca_current_consent($account)||(int)$account['customer_id']!==$a['customer_id'])crm_fail(401,'Доступ к кабинету изменился. Войдите заново.');
  $decision=$d['decision']??'';if(!in_array($decision,['approved','changes_requested'],true)||($d['confirm']??false)!==true)crm_fail(422,'Подтвердите решение по этой версии.');
  $feedback=cc_text($d,'feedback',5000,false);if($decision==='changes_requested'&&(mb_strlen($feedback)<5||!preg_match('/[\p{L}\p{N}]/u',$feedback)))crm_fail(422,'Опишите необходимые изменения: минимум 5 символов.');
  crm_query('INSERT INTO nd_cc_decisions(approval_id,account_id,decision,feedback,checksum) VALUES (?,?,?,?,?)',[$id,$a['id'],$decision,$feedback,$checksum]);
  crm_query('UPDATE nd_cc_approvals SET status=?,version=version+1 WHERE id=?',[$decision,$id]);crm_query('UPDATE nd_cc_revisions SET status=?,version=version+1 WHERE id=?',[$decision,$r['id']]);cc_event($a,(int)$doc['project_id'],'decision_recorded',['decision'=>$decision]);return ['ok'=>true,'id'=>$id,'status'=>$decision,'checksum'=>$checksum];
 });
}
function cc_withdraw(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'withdraw/'.$id,$d,function()use($a,$id,$d){$approval=cc_approval($a,$id);$doc=cc_document($a,(int)$approval['revision']['document_id'],true);cc_project($a,(int)$doc['project_id'],true,true);$approval=cc_approval($a,$id,true);crm_version($d,$approval);
 if($approval['status']!=='pending')crm_fail(409,'Отозвать можно только запрос без принятого решения.');crm_query("UPDATE nd_cc_approvals SET status='withdrawn',version=version+1 WHERE id=?",[$id]);cc_event($a,(int)$doc['project_id'],'review_withdrawn');return ['ok'=>true,'id'=>$id];});
}
function cc_finalize(array $a,int $id,array $d):array{
 cc_owner($a);return cc_mutation($a,'finalize/'.$id,$d,function()use($a,$id,$d){$r=cc_revision($a,$id);$doc=cc_document($a,(int)$r['document_id'],true);$r=cc_revision($a,$id,true);cc_project($a,(int)$doc['project_id'],true,true);crm_version($d,$r);
 if($r['status']!=='approved'||(int)$r['revision_number']!==(int)$doc['head_revision'])crm_fail(409,'Завершить можно только текущую согласованную редакцию.');crm_query("UPDATE nd_cc_revisions SET status='finalized',version=version+1 WHERE id=?",[$id]);cc_event($a,(int)$doc['project_id'],'document_finalized');return ['ok'=>true,'id'=>$id,'revision'=>cc_revision($a,$id)];});
}
function cc_approvals_list(array $a,int $project):array{
 cc_project($a,$project);$rows=crm_query("SELECT a.id,a.revision_id,a.status,a.version,a.checksum,a.due_on,a.created_at,d.title,d.kind,r.revision_number FROM nd_cc_approvals a JOIN nd_cc_revisions r ON r.id=a.revision_id JOIN nd_cc_documents d ON d.id=r.document_id WHERE d.project_id=? ORDER BY a.id DESC LIMIT 25 OFFSET ".((cc_page()-1)*25),[$project])->fetchAll();return ['ok'=>true,'items'=>$rows,'page'=>cc_page(),'page_size'=>25];
}
