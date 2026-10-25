<?php
/** Bounded CLI only. No deployment, migrations or live inference. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/ai/routes.php';
try{
 if(count($argv)>2||isset($argv[1])&&$argv[1]!=='cleanup')throw new RuntimeException('invalid_arguments');ai_gate();
 if(($argv[1]??'')==='cleanup'){
  $n=crm_atomic(function(){ $rows=crm_query('SELECT id,state FROM nd_ai_tasks WHERE expires_at<=UTC_TIMESTAMP() AND input_json IS NOT NULL ORDER BY id LIMIT 100 FOR UPDATE')->fetchAll();foreach($rows as $r){if(!in_array($r['state'],['APPLIED','REJECTED','CANCELLED'],true))ai_transition((int)$r['id'],$r['state'],'CANCELLED','retention_expired');crm_query('UPDATE nd_ai_tasks SET input_json=NULL WHERE id=?',[$r['id']]);crm_query('UPDATE nd_ai_artifacts SET body=NULL WHERE task_id=?',[$r['id']]);crm_query('UPDATE nd_ai_context_refs SET context_json=NULL WHERE task_id=?',[$r['id']]);crm_query("UPDATE nd_ai_approvals SET proposal_json='{}',state=CASE WHEN state IN ('pending','approved') THEN 'expired' ELSE state END WHERE task_id=?",[$r['id']]);}return count($rows);});echo ai_json(['ok'=>true,'payloads_cleared'=>$n]).PHP_EOL;exit;
 }
 // Recover worker loss conservatively: no implicit second inference for an unknown result.
 crm_atomic(function(){foreach(crm_query("SELECT id FROM nd_ai_tasks WHERE state='RUNNING' AND lease_until<UTC_TIMESTAMP() FOR UPDATE")->fetchAll() as $r){ai_transition((int)$r['id'],'RUNNING','NEEDS_HUMAN','worker_interrupted');crm_query("UPDATE nd_ai_tasks SET last_error='worker_interrupted' WHERE id=?",[$r['id']]);crm_query("UPDATE nd_ai_attempts SET state='unknown',error_category='worker_interrupted',finished_at=UTC_TIMESTAMP() WHERE task_id=? AND state='running'",[$r['id']]);}});
 $priced=pricing_automatic_projects();$queued=ai_trigger_rules(false);$run=0;foreach(crm_query("SELECT id FROM nd_ai_tasks WHERE state='QUEUED' AND agent_id NOT LIKE 'production_%' AND next_attempt<=UTC_TIMESTAMP() ORDER BY next_attempt,id LIMIT 5")->fetchAll() as $t){ai_run((int)$t['id']);$run++;}echo ai_json(['ok'=>true,'pricing_requests'=>$priced,'rules_queued'=>$queued,'tasks_processed'=>$run,'scheduler_verified'=>false]).PHP_EOL;
}catch(Throwable $e){fwrite(STDERR,"{\"error\":\"ai_worker_unavailable\"}\n");exit(1);}
