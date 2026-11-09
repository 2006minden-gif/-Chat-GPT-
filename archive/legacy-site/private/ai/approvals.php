<?php
declare(strict_types=1);
function ai_propose(array $t,int $artifact,array $output,array $versions):void{
 $action=$t['agent_id']==='proposal'?'send_message':($t['agent_id']==='planner'?'create_tasks':null);if(!$action)return;
 $quote=$t['agent_id']==='proposal'?pricing_require_approved((int)$t['project_id']):null;
 $payload=['quotation'=>$quote?['id'=>(int)$quote['id'],'checksum'=>$quote['checksum']]:null,'task_id'=>(int)$t['id'],'artifact_id'=>$artifact,'project_id'=>(int)$t['project_id'],'action'=>$action,'result'=>$action==='send_message'?['body'=>pricing_proposal_text($output,$quote)]:['tasks'=>$output['result']['tasks']]];$json=ai_json($payload);
 crm_query('INSERT INTO nd_ai_approvals(task_id,artifact_id,action,proposal_json,proposal_hash,versions_json,expires_at) VALUES (?,?,?,?,?,?,DATE_ADD(UTC_TIMESTAMP(),INTERVAL 24 HOUR))',[$t['id'],$artifact,$action,$json,hash('sha256',$json),ai_json($versions)]);
}
function ai_review(array $a,int $id,array $d):array{
 ai_owner($a);return crm_atomic(function()use($a,$id,$d){$p=crm_query('SELECT * FROM nd_ai_approvals WHERE id=?',[$id])->fetch();if(!$p)crm_fail(404,'Запись не найдена.');$t=ai_task($a,(int)$p['task_id'],true);$p=crm_query('SELECT * FROM nd_ai_approvals WHERE id=? FOR UPDATE',[$id])->fetch();crm_version($d,$p);
  if($p['state']!=='pending'||$t['state']!=='AWAITING_APPROVAL'||$p['expires_at']<=gmdate('Y-m-d H:i:s'))crm_fail(409,'Согласование больше недоступно или истекло.');if(($d['confirm']??false)!==true||!is_string($d['checksum']??null)||!hash_equals($p['proposal_hash'],$d['checksum']))crm_fail(409,'Подтвердите точную версию действия.');
  if(!in_array($d['decision']??'',['approved','rejected'],true))crm_fail(422,'Выберите решение.');
  if($d['decision']==='approved'&&$p['action']==='send_message'){$proposal=json_decode($p['proposal_json'],true);$quote=pricing_require_approved((int)$t['project_id']);if(($proposal['quotation']['id']??null)!==(int)$quote['id']||($proposal['quotation']['checksum']??null)!==$quote['checksum'])crm_fail(409,'NEEDS_COST_REVIEW: цена изменилась до согласования текста.');}
  if($d['decision']==='approved'&&ai_json(ai_target_versions($t,true))!==$p['versions_json'])crm_fail(409,'Исходные записи изменились. Подготовьте новое согласование.');
  crm_query('UPDATE nd_ai_approvals SET state=?,owner_id=1,decided_at=UTC_TIMESTAMP(),version=version+1 WHERE id=?',[$d['decision'],$id]);ai_transition((int)$t['id'],$t['state'],$d['decision']==='approved'?'APPROVED':'REJECTED','owner_decision');return ['ok'=>true,'id'=>$id];
 });
}
function ai_apply(array $a,int $id,array $d):array{
 ai_owner($a);return crm_atomic(function()use($a,$id,$d){$p=crm_query('SELECT * FROM nd_ai_approvals WHERE id=?',[$id])->fetch();if(!$p)crm_fail(404,'Запись не найдена.');$t=ai_task($a,(int)$p['task_id'],true);$p=crm_query('SELECT * FROM nd_ai_approvals WHERE id=? FOR UPDATE',[$id])->fetch();
  if(!is_string($d['checksum']??null)||!hash_equals($p['proposal_hash'],$d['checksum']))crm_fail(409,'Неверная версия согласованного действия.');
  if($p['state']==='applied')return ['ok'=>true,'id'=>$id,'already_applied'=>true];crm_version($d,$p);
  if(($d['confirm']??false)!==true||$p['state']!=='approved'||$t['state']!=='APPROVED'||(int)$p['owner_id']!==1||$p['expires_at']<=gmdate('Y-m-d H:i:s')||!is_string($d['checksum']??null)||!hash_equals($p['proposal_hash'],$d['checksum'])||!hash_equals($p['proposal_hash'],hash('sha256',$p['proposal_json'])))crm_fail(409,'Действие не имеет действующего точного согласования.');
  if(ai_json(ai_target_versions($t,true))!==$p['versions_json'])crm_fail(409,'Данные изменились после согласования. Применение отменено.');$proposal=json_decode($p['proposal_json'],true,512,JSON_THROW_ON_ERROR);if($p['action']==='send_message'){$quote=pricing_require_approved((int)$t['project_id']);if(($proposal['quotation']['id']??null)!==(int)$quote['id']||($proposal['quotation']['checksum']??null)!==$quote['checksum'])crm_fail(409,'NEEDS_COST_REVIEW: согласование цены изменилось.');}$artifact=crm_query('SELECT * FROM nd_ai_artifacts WHERE id=? FOR UPDATE',[$p['artifact_id']])->fetch();
  if(!$artifact['body']||!hash_equals($artifact['checksum'],hash('sha256',$artifact['body']))||(int)$proposal['project_id']!==(int)$t['project_id']||$proposal['action']!==$p['action']||(int)$proposal['task_id']!==(int)$t['id']||(int)$proposal['artifact_id']!==(int)$artifact['id'])crm_fail(409,'Контрольная сумма результата не подтверждена.');
  ai_transition((int)$t['id'],'APPROVED','APPLYING','exact_action_started');$owner=['type'=>'owner','id'=>1];
  if($p['action']==='send_message'){$result=cc_send_effect($owner,(int)$t['project_id'],['body'=>$proposal['result']['body'],'file_ids'=>[]]);$entity='messages';$effect=$result['id'];}
  elseif($p['action']==='create_tasks'){$effect=null;$entity='tasks';foreach($proposal['result']['tasks'] as $x){$r=crm_insert('tasks',['title'=>$x['title'],'description'=>'Черновик ИИ, проверенный владельцем. '.$x['description'],'project_id'=>(int)$t['project_id']]);$effect??=$r['record']['id'];}}
  else crm_fail(403,'Действие запрещено политикой ИИ.');
  crm_query("UPDATE nd_ai_approvals SET state='applied',version=version+1 WHERE id=?",[$id]);crm_query('UPDATE nd_ai_artifacts SET effect_entity=?,effect_id=? WHERE id=?',[$entity,$effect,$artifact['id']]);ai_transition((int)$t['id'],'APPLYING','APPLIED','exact_action_applied');return ['ok'=>true,'id'=>$id,'effect_entity'=>$entity,'effect_id'=>$effect];
 });
}
function ai_edit_artifact(array $a,int $id,array $d):array{
 ai_owner($a);return crm_atomic(function()use($a,$id,$d){$t=ai_task($a,$id,true);crm_version($d,$t);if($t['state']!=='AWAITING_APPROVAL')crm_fail(409,'Редактируется только результат, ожидающий согласования.');$old=crm_query('SELECT * FROM nd_ai_artifacts WHERE task_id=? ORDER BY revision_number DESC LIMIT 1 FOR UPDATE',[$id])->fetch();$ctx=crm_query('SELECT context_json FROM nd_ai_context_refs WHERE task_id=? ORDER BY id DESC LIMIT 1',[$id])->fetchColumn();if(!is_string($d['output']??null))crm_fail(422,'Ожидается структурированный JSON результата.');$o=ai_validate_output($t,$d['output'],json_decode($ctx,true));$raw=ai_json($o);$v=ai_target_versions($t,true);$oldVersions=crm_query('SELECT versions_json FROM nd_ai_context_refs WHERE task_id=? ORDER BY id DESC LIMIT 1',[$id])->fetchColumn();if(ai_json($v)!==$oldVersions)crm_fail(409,'Контекст изменился. Создайте новую задачу для проверки.');
  crm_query("UPDATE nd_ai_approvals SET state='superseded',version=version+1 WHERE task_id=? AND state='pending'",[$id]);crm_query("INSERT INTO nd_ai_artifacts(task_id,revision_number,body,checksum,provenance) VALUES (?,?,?,?,'owner')",[$id,(int)$old['revision_number']+1,$raw,hash('sha256',$raw)]);$aid=(int)db()->lastInsertId();ai_propose($t,$aid,$o,$v);crm_query('UPDATE nd_ai_tasks SET version=version+1 WHERE id=?',[$id]);return ['ok'=>true,'id'=>$id];
 });
}
