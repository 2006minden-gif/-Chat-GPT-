<?php
declare(strict_types=1);
function ai_create(array $a,array $d):array{
 foreach(array_keys($d) as $k)if(!in_array($k,['agent','intent','question','project_id','lead_id','revision_id','request_key','consent','policy_version'],true))crm_fail(422,'Неподдерживаемые параметры ИИ-запроса.');
 $agent=$d['agent']??'';if(!is_string($agent))crm_fail(422,'Выберите агента.');$ambiguous=false;
 if($agent==='dispatcher'){$intent=$d['intent']??'';$map=['consultation'=>'consultant','lead_analysis'=>'lead_analyst','proposal'=>'proposal','specification'=>'specification','plan'=>'planner','tasks'=>'task_assistant','monitor'=>'project_monitor','document_review'=>'document_assistant','business_report'=>'business_analyst'];if(!is_string($intent)||!isset($map[$intent]))$ambiguous=true;else $agent=$map[$intent];}
 if($a['type']!=='owner'){$policy=privacy_settings();if(!$policy['enabled']||($d['consent']??false)!==true||($d['policy_version']??null)!==$policy['version'])crm_fail(422,'Подтвердите обработку обращения ИИ по актуальной политике.');}
 $def=ai_agent($agent);if(!in_array($a['type'],$def['roles'],true))crm_fail(403,'Агент недоступен в вашем кабинете.');if(!ai_enabled_agent($agent))crm_fail(503,'Этот ИИ-агент выключен владельцем.');$question=cc_text($d,'question',4000);
 if($a['type']==='visitor'&&$agent!=='consultant')crm_fail(403,'Публичный помощник не имеет доступа к CRM.');
 return crm_idempotent('ai:create:'.$a['type'].':'.$a['id'],$d,function()use($a,$d,$agent,$def,$question,$ambiguous){
  $ids=['project_id'=>null,'lead_id'=>null,'revision_id'=>null];$target='none';$cid=$a['customer_id']??null;
  foreach(['project_id'=>'project','lead_id'=>'lead','revision_id'=>'revision'] as $f=>$kind)if(isset($d[$f])){if($target!=='none')crm_fail(422,'Выберите один основной источник контекста.');if($a['type']==='visitor')crm_fail(403,'Публичный помощник не читает CRM.');$id=cc_id($d[$f]);$r=ai_scope($a,$kind,$id,true);if($kind==='project'&&($r['archived_at']!==null||$r['status']==='cancelled'))crm_fail(409,'Проект недоступен для ИИ-заданий.');$ids[$f]=$id;$target=$kind;if($kind==='project')$cid=(int)$r['customer_id'];}
  if(!in_array($target,$def['targets'],true))crm_fail(422,'Для этого агента выберите подходящий источник.');
  $cap=$a['type']==='owner'?min(100,max(1,(int)(config()['ai_owner_daily_tasks']??30))):min(10,max(1,(int)(config()['ai_customer_daily_tasks']??5)));
  // Actor/day task reservation serializes simultaneous creates, independently of provider budgets.
  $bucket='tasks:'.$a['type'].':'.$a['id'].':'.gmdate('Y-m-d');crm_query('INSERT INTO nd_ai_budgets(bucket) VALUES (?) ON DUPLICATE KEY UPDATE bucket=VALUES(bucket)',[$bucket]);$n=(int)crm_query('SELECT calls FROM nd_ai_budgets WHERE bucket=? FOR UPDATE',[$bucket])->fetchColumn();if($n>=$cap)crm_fail(429,'Достигнут дневной лимит ИИ-обращений.');crm_query('UPDATE nd_ai_budgets SET calls=calls+1 WHERE bucket=?',[$bucket]);
  $hash=hash('sha256',ai_json($d));$key=$d['request_key'];crm_query("INSERT INTO nd_ai_tasks(agent_id,actor_type,actor_id,customer_id,project_id,lead_id,revision_id,input_json,state,request_key,request_hash,expires_at) VALUES (?,?,?,?,?,?,?,?,'CREATED',?,?,DATE_ADD(UTC_TIMESTAMP(),INTERVAL 30 DAY))",[$agent,$a['type'],$a['id'],$cid,$ids['project_id'],$ids['lead_id'],$ids['revision_id'],ai_json(['question'=>ai_redact($question)]),$key,$hash]);$id=(int)db()->lastInsertId();if($a['type']!=='owner'){$policy=privacy_settings();crm_query('UPDATE nd_ai_tasks SET consent_at=UTC_TIMESTAMP(),policy_version=?,policy_hash=? WHERE id=?',[$policy['version'],$policy['hash'],$id]);}ai_transition($id,'CREATED','VALIDATING','request_validated');ai_transition($id,'VALIDATING',$ambiguous?'NEEDS_HUMAN':'QUEUED',$ambiguous?'ambiguous_intent':'queued');return ['ok'=>true,'id'=>$id,'state'=>$ambiguous?'NEEDS_HUMAN':'QUEUED'];
 });
}
function ai_task_control(array $a,int $id,string $action,array $d):array{
 return crm_atomic(function()use($a,$id,$action,$d){$t=ai_task($a,$id,true);crm_version($d,$t);
  if($action==='cancel'){
   if(in_array($t['state'],['APPLIED','REJECTED','CANCELLED'],true))crm_fail(409,'Завершённое действие отменить нельзя.');ai_transition($id,$t['state'],'CANCELLED','cancelled_by_actor');crm_query("UPDATE nd_ai_approvals SET state='superseded',version=version+1 WHERE task_id=? AND state IN ('pending','approved')",[$id]);
  }elseif($action==='retry'){
   ai_owner($a);if(!in_array($t['state'],['FAILED','NEEDS_HUMAN'],true)||$t['attempts']>=$t['max_attempts']||$t['expires_at']<=gmdate('Y-m-d H:i:s'))crm_fail(409,'Повтор недоступен. Проверьте причину и лимиты.');if(in_array($t['last_error'],['invalid_output','model_refusal','source_changed','agent_disabled'],true))crm_fail(409,'Нужна новая проверенная задача, а не автоматический повтор.');ai_transition($id,$t['state'],'QUEUED','explicit_retry');crm_query('UPDATE nd_ai_tasks SET next_attempt=UTC_TIMESTAMP() WHERE id=?',[$id]);
  }else crm_fail(404,'Действие не найдено.');return ['ok'=>true,'id'=>$id];
 });
}
function ai_task_detail(array $a,int $id):array{
 $t=ai_task($a,$id);$out=$t;unset($out['request_key'],$out['request_hash'],$out['lease_token'],$out['actor_id']);
 $out['events']=crm_query('SELECT from_state,to_state,category,created_at FROM nd_ai_events WHERE task_id=? ORDER BY id',[$id])->fetchAll();
 $out['artifacts']=crm_query('SELECT id,revision_number,body,checksum,provenance,effect_entity,effect_id,created_at FROM nd_ai_artifacts WHERE task_id=? ORDER BY revision_number',[$id])->fetchAll();foreach($out['artifacts'] as &$r){$r['output']=$r['body']?json_decode($r['body'],true):null;unset($r['body']);}unset($r);
 $out['approvals']=$a['type']==='owner'?crm_query('SELECT * FROM nd_ai_approvals WHERE task_id=? ORDER BY id',[$id])->fetchAll():[];
 if($a['type']==='owner'){$refs=crm_query('SELECT context_json,versions_json,context_hash FROM nd_ai_context_refs WHERE task_id=? ORDER BY id DESC LIMIT 1',[$id])->fetch();$out['context']=$refs&&$refs['context_json']?json_decode($refs['context_json'],true):null;}
 else{$out['question']=$t['input_json']?(json_decode($t['input_json'],true)['question']??''):'';unset($out['input_json']);$out['facts']=[];if($out['artifacts']){$refs=crm_query('SELECT context_json FROM nd_ai_context_refs WHERE task_id=? ORDER BY id DESC LIMIT 1',[$id])->fetchColumn();if($refs)$out['facts']=json_decode($refs,true)['facts'];}}
 return ['ok'=>true,'record'=>$out];
}
