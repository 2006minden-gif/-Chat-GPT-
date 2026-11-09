<?php
declare(strict_types=1);
function prod_schedule_step(array $step):?int{
 $reservation=crm_atomic(function()use($step){$r=prod_run((int)$step['run_id'],true);if($r['state']!=='EXECUTING')return null;$p=prod_plan((int)$r['plan_id']);prod_current_source($p,true);$s=crm_query('SELECT * FROM nd_prod_steps WHERE id=? FOR UPDATE',[$step['id']])->fetch();if($s['ai_task_id'])return ['task_id'=>(int)$s['ai_task_id']];if(!in_array($s['state'],['WAITING_FOR_DEPENDENCY','QUEUED'],true))return null;
  if(crm_query("SELECT 1 FROM nd_prod_dependencies d JOIN nd_prod_steps x ON x.id=d.predecessor_id WHERE d.step_id=? AND x.state<>'COMPLETED'",[$s['id']])->fetchColumn())return null;
  $body=json_decode($p['body'],true);$currency=config()['ai_provider']['cost_currency']??null;if($currency!==$body['cost_currency']){prod_issue($r,'budget_currency_unknown');return null;}
  $estimate=ai_provider()->estimateCost(ai_agent($s['agent_id'])['max_context_bytes']+ai_agent($s['agent_id'])['max_tokens']+1024);if($estimate===null){prod_issue($r,'NEEDS_COST_REVIEW');return null;}
  // Reserve every bounded provider attempt before creating the task, including retries.
  $estimate*=max(1,(int)ai_agent($s['agent_id'])['max_attempts']);
  if($s['pending_key']===null){$spent=(int)crm_query('SELECT COALESCE(SUM(budget_total_micro),0) FROM nd_prod_steps WHERE run_id=?',[$r['id']])->fetchColumn()+(int)$r['planning_estimated_micro'];if($spent+$estimate>$body['budget_micro']){prod_issue($r,'budget_exhausted');return null;}$key=hash('sha256','production:'.$s['id'].':'.$s['revision_number']);crm_query("UPDATE nd_prod_steps SET pending_key=?,pending_micro=?,budget_total_micro=budget_total_micro+?,state='QUEUED',version=version+1 WHERE id=?",[$key,$estimate,$estimate,$s['id']]);}else $key=$s['pending_key'];
  return ['step_id'=>(int)$s['id'],'agent'=>$s['agent_id'],'project_id'=>(int)$p['project_id'],'key'=>$key,'revision'=>(int)$s['revision_number']];
 });if(!$reservation)return null;if(isset($reservation['task_id']))return $reservation['task_id'];
 $created=ai_create(['type'=>'owner','id'=>'1'],['agent'=>$reservation['agent'],'project_id'=>$reservation['project_id'],'question'=>'Выполните только назначенный шаг одобренного производственного плана. Код — неисполненный черновик, тесты нельзя объявлять выполненными без evidence.','request_key'=>$reservation['key']]);
 crm_atomic(function()use($reservation,$created){$s=crm_query('SELECT * FROM nd_prod_steps WHERE id=? FOR UPDATE',[$reservation['step_id']])->fetch();if((int)$s['revision_number']!==$reservation['revision']||$s['pending_key']!==$reservation['key'])crm_fail(409,'Шаг пересоздан во время планирования.');crm_query('INSERT INTO nd_prod_step_attempts(step_id,revision_number,ai_task_id) VALUES (?,?,?) ON DUPLICATE KEY UPDATE ai_task_id=VALUES(ai_task_id)',[$s['id'],$s['revision_number'],$created['id']]);crm_query("UPDATE nd_prod_steps SET ai_task_id=?,state='QUEUED',version=version+1 WHERE id=?",[$created['id'],$s['id']]);});return $created['id'];
}
function prod_tick(int $run,int $limit=5):array{
 prod_gate();if((config()['production_execution_enabled']??false)!==true)crm_fail(503,'Фоновое выполнение производства не разрешено владельцем.');$lock='nd_production_worker_'.substr(hash('sha256',config()['db_name']),0,32);if((int)crm_query('SELECT GET_LOCK(?,0)',[$lock])->fetchColumn()!==1)crm_fail(409,'Производство уже обрабатывается.');$done=0;
 try{
  for($i=0;$i<min(5,$limit);$i++){
   $r=prod_run($run);if($r['state']!=='EXECUTING')break;$p=prod_plan((int)$r['plan_id']);
   try{prod_current_source($p);$steps=crm_query("SELECT * FROM nd_prod_steps WHERE run_id=? AND state IN ('WAITING_FOR_DEPENDENCY','QUEUED','RUNNING') ORDER BY id",[$run])->fetchAll();$task=null;$selected=null;
    foreach($steps as $s){$tid=prod_schedule_step($s);if(!$tid)continue;$selected=$s;$task=ai_task(['type'=>'owner','id'=>'1'],$tid);break;}
    if(!$task)break;
    if($task['state']==='QUEUED'&&$task['next_attempt']<=gmdate('Y-m-d H:i:s')){prod_assert_scheduled($task);crm_query("UPDATE nd_prod_steps SET state='RUNNING',version=version+1 WHERE id=?",[$selected['id']]);ai_run((int)$task['id']);$done++;$task=ai_task(['type'=>'owner','id'=>'1'],(int)$task['id']);}
    if(in_array($task['state'],['FAILED','NEEDS_HUMAN','CANCELLED'],true)){crm_query("UPDATE nd_prod_steps SET state='NEEDS_HUMAN',last_error=?,version=version+1 WHERE id=?",[$task['last_error']??'task_unavailable',$selected['id']]);crm_atomic(fn()=>prod_issue(prod_run($run,true),'upstream_task_failed'));break;}
    if($task['state']==='QUEUED')break;
   }catch(CrmFailure|AiProviderFailure $e){crm_atomic(fn()=>prod_issue(prod_run($run,true),$e instanceof AiProviderFailure?$e->category:'source_or_capability_changed'));break;}
  }
  $current=prod_run($run);if($current['state']==='QA_REJECTED'&&(config()['production_auto_revisions_enabled']??false)===true){$report=crm_query('SELECT id FROM nd_prod_qa_reports WHERE run_id=? ORDER BY id DESC LIMIT 1',[$run])->fetchColumn();prod_revision($run,['version'=>(int)$current['version'],'reason'=>'Автоматическая ограниченная доработка по текущему QA-отчёту.','request_key'=>hash('sha256','production-auto-revision:'.$run.':'.$report)]);}
  return ['ok'=>true,'id'=>$run,'tasks_processed'=>$done,'state'=>prod_run($run)['state'],'scheduler_verified'=>false,'sandbox_available'=>false];
 }finally{crm_query('SELECT RELEASE_LOCK(?)',[$lock]);}
}
