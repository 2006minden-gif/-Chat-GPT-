<?php
declare(strict_types=1);
function ai_rule_save(array $a,int $id,array $d):array{
 ai_owner($a);return crm_idempotent('ai:rule:'.$id,$d,function()use($id,$d){foreach(array_keys($d) as $k)if(!in_array($k,['name','trigger','agent','mode','enabled','max_runs','version','request_key'],true))crm_fail(422,'Правило не поддерживает произвольный код или URL.');
  $name=cc_text($d,'name',190);$trigger=$d['trigger']??'';$agent=$d['agent']??'';$mode=$d['mode']??'';$allowed=['new_lead'=>['lead_analyst','advisory'],'project_deadline'=>['project_monitor','internal_alert']];
  if($trigger==='manual'){$def=ai_agent(is_string($agent)?$agent:'');if(!in_array($mode,['advisory','draft'],true)||$mode==='draft'&&$agent!=='specification'||$agent==='specification'&&$mode!=='draft')crm_fail(422,'Режим правила недоступен.');}
  elseif(($allowed[$trigger]??null)!==[$agent,$mode])crm_fail(422,'Недопустимое сочетание события, агента и разрешений.');
  if(!is_bool($d['enabled']??null)||!is_int($d['max_runs']??null)||$d['max_runs']<1||$d['max_runs']>100)crm_fail(422,'Укажите лимит от 1 до 100 запусков.');
  if($id){$r=crm_query('SELECT * FROM nd_ai_rules WHERE id=? FOR UPDATE',[$id])->fetch();if(!$r)crm_fail(404,'Правило не найдено.');crm_version($d,$r);crm_query('UPDATE nd_ai_rules SET name=?,trigger_type=?,agent_id=?,mode=?,enabled=?,max_runs=?,version=version+1 WHERE id=?',[$name,$trigger,$agent,$mode,$d['enabled']?1:0,$d['max_runs'],$id]);}
  else{crm_query('INSERT INTO nd_ai_rules(name,trigger_type,agent_id,mode,enabled,max_runs) VALUES (?,?,?,?,?,?)',[$name,$trigger,$agent,$mode,$d['enabled']?1:0,$d['max_runs']]);$id=(int)db()->lastInsertId();}return ['ok'=>true,'id'=>$id];
 });
}
function ai_rule_test(array $a,int $id):array{
 ai_owner($a);$r=crm_query('SELECT * FROM nd_ai_rules WHERE id=?',[$id])->fetch();if(!$r)crm_fail(404,'Правило не найдено.');return ['ok'=>true,'synthetic'=>true,'provider_called'=>false,'business_writes'=>false,'synthetic_deadline_test'=>['due_on'=>'2000-01-01','today'=>gmdate('Y-m-d'),'overdue'=>gmdate('Y-m-d')>'2000-01-01'],'result'=>['trigger'=>$r['trigger_type'],'agent'=>$r['agent_id'],'mode'=>$r['mode'],'example'=>'Тестовое событие будет обработано в пределах выбранного режима; отправки клиенту и финансовых действий нет.']];
}
function ai_trigger_rules(bool $explicitManual=false):int{
 if(!$explicitManual&&(config()['ai_periodic_authorized']??false)!==true)return 0;$count=0;
 foreach(crm_query("SELECT * FROM nd_ai_rules WHERE enabled=1 AND trigger_type<>'manual' AND (runs<max_runs OR EXISTS (SELECT 1 FROM nd_ai_rule_runs x WHERE x.rule_id=nd_ai_rules.id AND x.outcome='reserved')) ORDER BY id LIMIT 20")->fetchAll() as $rule){
  $events=$rule['trigger_type']==='new_lead'?crm_query("SELECT l.id FROM nd_leads l WHERE NOT EXISTS (SELECT 1 FROM nd_ai_rule_runs x WHERE x.rule_id=? AND x.event_key=CONCAT('new_lead:',l.id) AND x.outcome<>'reserved') ORDER BY l.id LIMIT 100",[$rule['id']])->fetchAll():crm_query("SELECT p.id FROM nd_projects p WHERE p.archived_at IS NULL AND p.status IN ('planned','active','on_hold') AND NOT EXISTS (SELECT 1 FROM nd_ai_rule_runs x WHERE x.rule_id=? AND x.event_key=CONCAT('project_deadline:',p.id,':',UTC_DATE()) AND x.outcome<>'reserved') ORDER BY p.id LIMIT 100",[$rule['id']])->fetchAll();
  foreach($events as $event){$id=(int)$event['id'];$eventKey=$rule['trigger_type'].':'.$id.($rule['trigger_type']==='project_deadline'?':'.gmdate('Y-m-d'):'');
   if(crm_query("SELECT 1 FROM nd_ai_rule_runs WHERE rule_id=? AND event_key=? AND outcome<>'reserved'",[$rule['id'],$eventKey])->fetchColumn())continue;
   // Durable reservation consumes the rule limit before creating the idempotent task.
   $reserved=crm_atomic(function()use($rule,$eventKey){
    $r=crm_query('SELECT * FROM nd_ai_rules WHERE id=? FOR UPDATE',[$rule['id']])->fetch();$old=crm_query('SELECT * FROM nd_ai_rule_runs WHERE rule_id=? AND event_key=? FOR UPDATE',[$rule['id'],$eventKey])->fetch();if($old)return $old['outcome']==='reserved';if(!$r['enabled']||(int)$r['runs']>=(int)$r['max_runs'])return false;
    crm_query("INSERT INTO nd_ai_rule_runs(rule_id,event_key,outcome) VALUES (?,?,'reserved')",[$rule['id'],$eventKey]);crm_query('UPDATE nd_ai_rules SET runs=runs+1 WHERE id=?',[$rule['id']]);return true;
   });if(!$reserved)continue;
   $key=hash('sha256','ai-rule:'.$rule['id'].':'.$eventKey);$d=['agent'=>$rule['agent_id'],'question'=>$rule['trigger_type']==='new_lead'?'Подготовьте краткий анализ заявки без изменения её статуса.':'Проверьте сроки и фактический прогресс без изменения обязательств.','request_key'=>$key,($rule['trigger_type']==='new_lead'?'lead_id':'project_id')=>$id];
   try{$task=ai_create(['type'=>'owner','id'=>'1'],$d);crm_query("UPDATE nd_ai_rule_runs SET task_id=?,outcome='queued' WHERE rule_id=? AND event_key=?",[$task['id'],$rule['id'],$eventKey]);crm_query('UPDATE nd_ai_rules SET last_error=NULL WHERE id=?',[$rule['id']]);$count++;}
   catch(Throwable $e){crm_query("UPDATE nd_ai_rule_runs SET outcome='failed' WHERE rule_id=? AND event_key=?",[$rule['id'],$eventKey]);crm_query("UPDATE nd_ai_rules SET last_error='rule_execution_unavailable' WHERE id=?",[$rule['id']]);break;}

  }
 }return $count;
}
function ai_manual_rule(array $a,int $id,array $d):array{
 ai_owner($a);$key=bill_key($d);$rule=crm_query('SELECT * FROM nd_ai_rules WHERE id=?',[$id])->fetch();if(!$rule||$rule['trigger_type']!=='manual')crm_fail(404,'Ручное правило не найдено.');$event='manual:'.$key;
 crm_atomic(function()use($id,$event){$r=crm_query('SELECT * FROM nd_ai_rules WHERE id=? FOR UPDATE',[$id])->fetch();$old=crm_query('SELECT id FROM nd_ai_rule_runs WHERE rule_id=? AND event_key=?',[$id,$event])->fetchColumn();if($old)return;if(!$r['enabled']||(int)$r['runs']>=(int)$r['max_runs'])crm_fail(409,'Правило отключено или лимит запусков исчерпан.');crm_query("INSERT INTO nd_ai_rule_runs(rule_id,event_key,outcome) VALUES (?,?,'reserved')",[$id,$event]);crm_query('UPDATE nd_ai_rules SET runs=runs+1 WHERE id=?',[$id]);});
 $input=['agent'=>$rule['agent_id'],'question'=>cc_text($d,'question',4000),'request_key'=>hash('sha256','manual-rule:'.$id.':'.$key)];foreach(['project_id','lead_id','revision_id'] as $f)if(isset($d[$f]))$input[$f]=cc_id($d[$f]);
 $result=ai_create($a,$input);crm_query("UPDATE nd_ai_rule_runs SET task_id=?,outcome='queued' WHERE rule_id=? AND event_key=?",[$result['id'],$id,$event]);return $result;
}
