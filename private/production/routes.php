<?php
declare(strict_types=1);
require_once __DIR__.'/registry.php';require_once __DIR__.'/contracts.php';require_once __DIR__.'/core.php';require_once __DIR__.'/plans.php';require_once __DIR__.'/artifacts.php';require_once __DIR__.'/qa.php';require_once __DIR__.'/engine.php';require_once __DIR__.'/packages.php';require_once __DIR__.'/costs.php';require_once __DIR__.'/read.php';
function prod_dispatch(array $a,string $route,string $method):never{
 prod_gate();if($a['type']==='customer'&&$method==='GET'&&preg_match('~^projects/([1-9][0-9]*)$~D',$route,$m))json_response(prod_customer($a,(int)$m[1]));ai_owner($a);
 if($method==='GET'){
  if($route==='settings')json_response(['ok'=>true,'stage9_available'=>cat_binding_installed(),'sandbox_available'=>false,'live_execution_available'=>false,'execution_enabled'=>(config()['production_execution_enabled']??false)===true,'scheduler_verified'=>false,'concurrency'=>1]);
  if($route==='overview')json_response(['ok'=>true,'states'=>crm_query('SELECT state,COUNT(*) AS count FROM nd_prod_runs GROUP BY state')->fetchAll(),'step_states'=>crm_query('SELECT state,COUNT(*) AS count FROM nd_prod_steps GROUP BY state')->fetchAll(),'qa_rejected'=>(int)crm_query("SELECT COUNT(*) FROM nd_prod_qa_reports WHERE verdict='FAIL'")->fetchColumn(),'awaiting_plan'=>(int)crm_query("SELECT COUNT(*) FROM nd_prod_plans WHERE state='AWAITING_OWNER_APPROVAL'")->fetchColumn(),'awaiting_package'=>(int)crm_query("SELECT COUNT(*) FROM nd_prod_packages WHERE state='DRAFT'")->fetchColumn()]);
  if($route==='qa')json_response(['ok'=>true,'items'=>crm_query('SELECT id,run_id,verdict,bundle_hash,created_at FROM nd_prod_qa_reports ORDER BY id DESC LIMIT 50')->fetchAll()]);
  if($route==='packages')json_response(['ok'=>true,'items'=>crm_query('SELECT id,run_id,state,file_id,manifest_hash FROM nd_prod_packages ORDER BY id DESC LIMIT 50')->fetchAll()]);
  if($route==='events')json_response(['ok'=>true,'items'=>crm_query('SELECT * FROM nd_prod_events ORDER BY id DESC LIMIT 100')->fetchAll()]);
  if($route==='costs'){$rows=crm_query('SELECT id FROM nd_prod_runs ORDER BY id DESC LIMIT 25')->fetchAll();json_response(['ok'=>true,'items'=>array_map(fn($r)=>prod_cost_report((int)$r['id']),$rows)]);}
  if($route==='plans')json_response(['ok'=>true,'items'=>crm_query('SELECT id,project_id,order_id,service_type,revision_number,state,checksum,version,spec_revision_id FROM nd_prod_plans ORDER BY id DESC LIMIT 50')->fetchAll()]);
  if($route==='runs')json_response(['ok'=>true,'items'=>crm_query('SELECT r.*,p.project_id,p.order_id,p.service_type FROM nd_prod_runs r JOIN nd_prod_plans p ON p.id=r.plan_id ORDER BY r.id DESC LIMIT 50')->fetchAll()]);
  if(preg_match('~^plans/([1-9][0-9]*)$~D',$route,$m))json_response(['ok'=>true,'record'=>prod_plan((int)$m[1])]);
  if(preg_match('~^runs/([1-9][0-9]*)$~D',$route,$m))json_response(prod_detail((int)$m[1]));
  if($route==='rates')json_response(['ok'=>true,'rates'=>crm_query('SELECT * FROM nd_cost_rates ORDER BY id DESC LIMIT 100')->fetchAll(),'scopes'=>crm_query('SELECT * FROM nd_prod_rate_scopes ORDER BY id DESC LIMIT 100')->fetchAll(),'services'=>prod_services()]);
 }
 if($method==='POST'){
  $d=input();
  if($route==='plans')json_response(crm_idempotent('production:plan-create',$d,fn()=>prod_create_plan_effect(cc_id($d['project_id']??null),cc_id($d['spec_revision_id']??null),prod_plan_contract($d['plan']??null))));
  if(preg_match('~^plans/([1-9][0-9]*)/(validate|approve|reject|start|revise)$~D',$route,$m)){
   $id=(int)$m[1];if($m[2]==='start')json_response(prod_start($id,$d));if($m[2]==='revise'){$p=prod_plan($id);json_response(crm_idempotent('production:plan-revise:'.$id,$d,fn()=>prod_create_plan_effect((int)$p['project_id'],(int)$p['spec_revision_id'],prod_plan_contract($d['plan']??null))));}json_response(prod_plan_action($id,$m[2],$d));
  }
  if(preg_match('~^runs/([1-9][0-9]*)/(pause|resume|revision|package|expense|finish)$~D',$route,$m)){
   $id=(int)$m[1];json_response(match($m[2]){'revision'=>prod_revision($id,$d),'package'=>prod_package($id,$d),'expense'=>prod_expense($id,$d),'finish'=>prod_finish($id,$d),default=>crm_idempotent('production:'.$m[2].':'.$id,$d,function()use($id,$m,$d){$r=prod_run($id,true);crm_version($d,$r);$p=prod_plan((int)$r['plan_id']);prod_current_source($p,true);if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите изменение выполнения.');if($m[2]==='resume'){foreach(crm_query("SELECT s.*,t.state AS ai_state FROM nd_prod_steps s LEFT JOIN nd_ai_tasks t ON t.id=s.ai_task_id WHERE s.run_id=? AND s.state='NEEDS_HUMAN' FOR UPDATE",[$id])->fetchAll() as $step){if(!in_array($step['ai_state'],['QUEUED','RUNNING'],true))crm_fail(409,'Сначала выполните разрешённый повтор ИИ-задания или создайте новую редакцию плана.');crm_query("UPDATE nd_prod_steps SET state='QUEUED',last_error=NULL WHERE id=?",[$step['id']]);}}prod_run_state($r,$m[2]==='pause'?'PAUSED':'EXECUTING',$m[2]);return ['ok'=>true,'id'=>$id,'remote_cancellation_supported'=>false];})});
  }
  if(preg_match('~^packages/([1-9][0-9]*)/(approve|deliver)$~D',$route,$m))json_response(prod_package_action((int)$m[1],$m[2],$d));
  if($route==='rates/scope')json_response(crm_idempotent('production:rate-scope',$d,function()use($d){$rate=cc_id($d['rate_id']??null);if(!crm_query('SELECT 1 FROM nd_cost_rates WHERE id=?',[$rate])->fetchColumn()||!in_array($d['service_type']??'',prod_services(),true)||!is_bool($d['active']??null))crm_fail(422,'Проверьте ставку и вид услуги.');$date=cc_text($d,'verified_at',19);$dt=DateTimeImmutable::createFromFormat('!Y-m-d H:i:s',$date,new DateTimeZone('UTC'));if(!$dt||$dt->format('Y-m-d H:i:s')!==$date||$date>gmdate('Y-m-d H:i:s'))crm_fail(422,'Проверьте дату проверки ставки UTC.');crm_query('INSERT INTO nd_prod_rate_scopes(rate_id,service_type,active,verified_at,source) VALUES (?,?,?,?,?)',[$rate,$d['service_type'],$d['active']?1:0,$date,cc_text($d,'source',500)]);return ['ok'=>true,'id'=>(int)db()->lastInsertId()];}));
 }
 crm_fail(404,'Раздел производства не найден.');
}
