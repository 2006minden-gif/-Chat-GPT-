<?php
declare(strict_types=1);
ini_set('display_errors','0');
require_once __DIR__.'/core.php';require_once dirname(__DIR__).'/collab/routes.php';require_once __DIR__.'/context.php';require_once __DIR__.'/schema.php';require_once __DIR__.'/provider.php';require_once __DIR__.'/tasks.php';require_once __DIR__.'/approvals.php';require_once __DIR__.'/engine.php';require_once __DIR__.'/rules.php';require_once __DIR__.'/read.php';require_once __DIR__.'/public.php';
require_once dirname(__DIR__).'/pricing/routes.php';require_once dirname(__DIR__).'/pricing/automation.php';
require_once dirname(__DIR__).'/production/routes.php';
function ai_dispatch(bool $customer,string $route,string $method):never{
 try{
  $a=ai_actor($customer,$method!=='GET');rate('ai:'.$a['type'].':'.$a['id'],100);
  if(str_starts_with($route,'production/'))prod_dispatch($a,substr($route,11),$method);
  if(str_starts_with($route,'pricing/'))pricing_dispatch($a,substr($route,8),$method);
  if($method==='GET'){
   if($route==='tasks')json_response(ai_list_tasks($a));
   if(preg_match('~^tasks/([1-9][0-9]*)$~D',$route,$m))json_response(ai_task_detail($a,(int)$m[1]));
   if($route==='settings')json_response(['ok'=>true,'provider_status'=>ai_provider_status(),'live_available'=>false,'scheduler_verified'=>false,'periodic_authorized'=>(config()['ai_periodic_authorized']??false)===true,'policy_version'=>privacy_settings()['version'],'no_financial_actions'=>true]);
   ai_owner($a);
   if($route==='overview')json_response(ai_overview());if($route==='agents')json_response(ai_agents_list());if($route==='usage')json_response(ai_usage_report());
   if($route==='approvals')json_response(['ok'=>true,'items'=>crm_query('SELECT id,task_id,action,state,expires_at FROM nd_ai_approvals ORDER BY id DESC LIMIT 50')->fetchAll()]);
   if(preg_match('~^rules/([1-9][0-9]*)$~D',$route,$m)){$r=crm_query('SELECT * FROM nd_ai_rules WHERE id=?',[(int)$m[1]])->fetch();if(!$r)crm_fail(404,'Правило не найдено.');json_response(['ok'=>true,'record'=>$r,'runs'=>crm_query('SELECT event_key,task_id,outcome,created_at FROM nd_ai_rule_runs WHERE rule_id=? ORDER BY id DESC LIMIT 50',[$r['id']])->fetchAll()]);}
   if($route==='rules')json_response(['ok'=>true,'items'=>crm_query('SELECT * FROM nd_ai_rules ORDER BY id DESC LIMIT 50')->fetchAll()]);
   if($route==='history')json_response(['ok'=>true,'items'=>crm_query('SELECT * FROM nd_ai_events ORDER BY id DESC LIMIT 50')->fetchAll()]);
  }elseif($method==='POST'){
   $d=input();if($route==='tasks')json_response(ai_create($a,$d));
   if(preg_match('~^tasks/([1-9][0-9]*)/(run|cancel|retry|edit)$~D',$route,$m)){
    if($m[2]==='run'){$t=ai_task($a,(int)$m[1]);if(str_starts_with($t['agent_id'],'production_')&&$t['agent_id']!=='production_coordinator')prod_assert_scheduled($t);if($a['type']!=='owner'&&$t['agent_id']!=='consultant')crm_fail(403,'Запуск агента запрещён.');json_response(ai_run((int)$m[1]));}
    json_response($m[2]==='edit'?ai_edit_artifact($a,(int)$m[1],$d):ai_task_control($a,(int)$m[1],$m[2],$d));
   }
   ai_owner($a);if(preg_match('~^agents/([a-z_]+)$~D',$route,$m))json_response(ai_agent_update($m[1],$d));
   if(preg_match('~^approvals/([1-9][0-9]*)/(decide|apply)$~D',$route,$m))json_response($m[2]==='apply'?ai_apply($a,(int)$m[1],$d):ai_review($a,(int)$m[1],$d));
   if(preg_match('~^rules(?:/([1-9][0-9]*))?$~D',$route,$m))json_response(ai_rule_save($a,(int)($m[1]??0),$d));
   if(preg_match('~^rules/([1-9][0-9]*)/execute$~D',$route,$m))json_response(ai_manual_rule($a,(int)$m[1],$d));
   if(preg_match('~^rules/([1-9][0-9]*)/test$~D',$route,$m))json_response(ai_rule_test($a,(int)$m[1]));
   if($route==='rules/run'){if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите разовый запуск правил.');json_response(['ok'=>true,'queued'=>ai_trigger_rules(true),'scheduler_verified'=>false]);}
  }crm_fail(404,'Раздел не найден.');
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'ai_error');}catch(CustomerFailure $e){fail($e->status,$e->getMessage(),$e->errorCode);}
}
