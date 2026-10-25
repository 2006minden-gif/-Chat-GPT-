<?php
declare(strict_types=1);
function ai_public_allowed():bool{return (config()['ai_enabled']??false)===true&&(config()['ai_public_enabled']??false)===true&&(config()['ai_data_processing_approved']??false)===true&&privacy_settings()['enabled'];}
function ai_visitor(bool $write=false):array{
 if(!ai_public_allowed())crm_fail(503,'Публичный ИИ-помощник отключён.');ai_gate();$raw=$_COOKIE['nd_ai_visitor']??'';$s=null;if(is_string($raw)&&preg_match('/^[a-f0-9]{64}$/D',$raw))$s=crm_query('SELECT * FROM nd_ai_visitors WHERE token_hash=? AND expires>UTC_TIMESTAMP()',[hash('sha256',$raw)])->fetch();
 if(!$s){if($write)crm_fail(401,'Откройте помощника заново.');$raw=bin2hex(random_bytes(32));$s=['token_hash'=>hash('sha256',$raw),'csrf'=>bin2hex(random_bytes(32))];crm_query('INSERT INTO nd_ai_visitors(token_hash,csrf,expires) VALUES (?,?,DATE_ADD(UTC_TIMESTAMP(),INTERVAL 1 DAY))',[$s['token_hash'],$s['csrf']]);setcookie('nd_ai_visitor',$raw,['expires'=>time()+86400,'path'=>'/','secure'=>parse_url(config()['app_url'],PHP_URL_SCHEME)==='https','httponly'=>true,'samesite'=>'Strict']);}
 if($write){same_origin();if(!hash_equals($s['csrf'],$_SERVER['HTTP_X_CSRF_TOKEN']??''))crm_fail(403,'Обновите помощника перед отправкой.');}return ['type'=>'visitor','id'=>$s['token_hash'],'csrf'=>$s['csrf']];
}
function ai_public_dispatch(string $route,string $method):never{
 if($route==='status'&&$method==='GET'){json_response(['ok'=>true,'enabled'=>ai_public_allowed()]);}
 if(!ai_public_allowed())crm_fail(503,'ИИ-помощник пока недоступен.');$a=ai_visitor($method!=='GET');rate('ai-public',40);
 if($method==='GET'&&$route==='session'){$p=privacy_settings();json_response(['ok'=>true,'csrf'=>$a['csrf'],'policy_version'=>$p['version'],'provider_status'=>ai_provider_status(),'catalog'=>ai_catalog(),'disclosure'=>'Я — ИИ-помощник НейроДело. Помогу уточнить задачу и подготовить заявку. Если понадобится, передам вопрос специалисту.']);}
 if($method==='GET'&&$route==='tasks')json_response(ai_list_tasks($a));
 if($method==='GET'&&preg_match('~^tasks/([1-9][0-9]*)$~D',$route,$m))json_response(ai_task_detail($a,(int)$m[1]));
 if($method==='POST'&&$route==='chat'){
  $d=input();$allowed=['question','request_key','consent','policy_version'];if(array_diff(array_keys($d),$allowed))crm_fail(403,'Публичный помощник не выполняет административные команды.');$d['agent']='consultant';$created=ai_create($a,$d);$p=privacy_settings();crm_query('UPDATE nd_ai_visitors SET consent_at=UTC_TIMESTAMP(),policy_version=?,policy_hash=? WHERE token_hash=?',[$p['version'],$p['hash'],$a['id']]);if(ai_task($a,$created['id'])['state']==='QUEUED')ai_run($created['id']);json_response(ai_task_detail($a,$created['id']));
 }
 if($method==='POST'&&$route==='clear'){
  crm_atomic(function()use($a){$tasks=crm_query('SELECT id,state FROM nd_ai_tasks WHERE actor_type=\'visitor\' AND actor_id=? FOR UPDATE',[$a['id']])->fetchAll();foreach($tasks as $t){if(in_array($t['state'],['QUEUED','RUNNING','NEEDS_HUMAN','FAILED','COMPLETED'],true))ai_transition((int)$t['id'],$t['state'],'CANCELLED','visitor_clear');crm_query('UPDATE nd_ai_tasks SET input_json=NULL,expires_at=UTC_TIMESTAMP() WHERE id=?',[$t['id']]);crm_query('UPDATE nd_ai_artifacts SET body=NULL WHERE task_id=?',[$t['id']]);crm_query('UPDATE nd_ai_context_refs SET context_json=NULL WHERE task_id=?',[$t['id']]);}});json_response(['ok'=>true]);
 }crm_fail(404,'Раздел не найден.');
}
