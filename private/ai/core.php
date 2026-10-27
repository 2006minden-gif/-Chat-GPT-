<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/billing/routes.php';require_once __DIR__.'/registry.php';
function ai_gate():void{
 crm_gate();if((config()['ai_enabled']??false)!==true||(config()['ai_data_processing_approved']??false)!==true)crm_fail(503,'ИИ-центр отключён владельцем.');
 if(crm_query("SELECT state FROM nd_schema_migrations WHERE version='009_ai_automation'")->fetchColumn()!=='applied')crm_fail(503,'ИИ-центр ещё не подготовлен.');
}
function ai_actor(bool $customer,bool $write=false):array{
 if(!$customer){current_session($write);$a=['type'=>'owner','id'=>'1'];}
 else{require_once dirname(__DIR__).'/customer-auth.php';ca_gate();$s=ca_session($write);$r=ca_account((int)($s['account_id']??0));if(!ca_account_allowed($r)||!ca_current_consent($r))crm_fail(401,'Войдите и подтвердите актуальные документы.');$a=['type'=>'customer','id'=>(string)$r['id'],'customer_id'=>(int)$r['customer_id']];}ai_gate();return $a;
}
function ai_owner(array $a):void{if($a['type']!=='owner')crm_fail(403,'Действие доступно только владельцу.');}
function ai_json(mixed $v):string{return json_encode($v,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);}
function ai_redact(string $s):string{
 $s=preg_replace('/[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}/iu','[email скрыт]',$s);
 $s=preg_replace('/(?<!\w)(?:\+?[0-9][\s()\-]*){10,15}(?!\w)/u','[телефон скрыт]',$s);
 $s=preg_replace('/\b(?:password|пароль|api[_ -]?key|token|secret|csrf|authorization)\s*[:=]\s*[^\s,;]+/iu','[секрет скрыт]',$s);
 return preg_replace('/\b[A-Za-z0-9_\-]{40,}\b/u','[идентификатор скрыт]',$s);
}
function ai_transition(int $id,string $from,string $to,string $category):void{
 $map=['CREATED'=>['VALIDATING'],'VALIDATING'=>['QUEUED','NEEDS_HUMAN'],'QUEUED'=>['RUNNING','CANCELLED','NEEDS_HUMAN'],'RUNNING'=>['COMPLETED','AWAITING_APPROVAL','QUEUED','FAILED','NEEDS_HUMAN','CANCELLED'],'COMPLETED'=>['CANCELLED'],'AWAITING_APPROVAL'=>['APPROVED','REJECTED','CANCELLED','NEEDS_HUMAN'],'APPROVED'=>['APPLYING','CANCELLED','NEEDS_HUMAN'],'APPLYING'=>['APPLIED'],'FAILED'=>['QUEUED','CANCELLED'],'NEEDS_HUMAN'=>['QUEUED','CANCELLED'],'REJECTED'=>[],'APPLIED'=>[],'CANCELLED'=>[]];
 if(!in_array($to,$map[$from]??[],true))crm_fail(409,'Этот переход ИИ-задания недоступен.');
 $q=crm_query('UPDATE nd_ai_tasks SET state=?,version=version+1 WHERE id=? AND state=?',[$to,$id,$from]);if($q->rowCount()!==1)crm_fail(409,'Состояние задания изменилось. Обновите данные.');
 crm_query('INSERT INTO nd_ai_events(task_id,from_state,to_state,category) VALUES (?,?,?,?)',[$id,$from,$to,$category]);
}
function ai_task(array $a,int $id,bool $lock=false):array{
 $p=[$id];$sql='SELECT * FROM nd_ai_tasks WHERE id=?';if($a['type']!=='owner'){$sql.=' AND actor_type=? AND actor_id=? AND expires_at>UTC_TIMESTAMP()';array_push($p,$a['type'],$a['id']);}
 $t=crm_query($sql.($lock?' FOR UPDATE':''),$p)->fetch();if(!$t)crm_fail(404,'Запись не найдена.');return $t;
}
function ai_scope(array $a,string $kind,int $id,bool $lock=false):array{
 if($kind==='project')return cc_project($a,$id,false,$lock);
 if($kind==='lead'){ai_owner($a);$q=crm_query('SELECT * FROM nd_leads WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$q)crm_fail(404,'Запись не найдена.');return $q;}
 if($kind==='revision'){if($a['type']!=='owner')crm_fail(403,'Доступ к внутренним документам запрещён.');return cc_revision(['type'=>'owner','id'=>1],$id,$lock);}
 crm_fail(422,'Неизвестный источник контекста.');
}
function ai_task_actor(array $t):array{
 $a=['type'=>$t['actor_type'],'id'=>$t['actor_id']];if($a['type']!=='owner'){$p=privacy_settings();if(!$p['enabled']||!is_string($t['policy_hash'])||!hash_equals($p['hash'],$t['policy_hash'])||$p['version']!==$t['policy_version'])crm_fail(401,'Подтвердите актуальные условия обработки обращения ИИ.');}if($t['customer_id'])$a['customer_id']=(int)$t['customer_id'];
 if($a['type']==='customer'){require_once dirname(__DIR__).'/customer-auth.php';$r=ca_account((int)$a['id']);if(!ca_account_allowed($r)||!ca_current_consent($r)||(int)$r['customer_id']!==$a['customer_id'])crm_fail(401,'Доступ клиента изменился.');}
 if($a['type']==='visitor'&&!crm_query('SELECT 1 FROM nd_ai_visitors WHERE token_hash=? AND expires>UTC_TIMESTAMP() AND consent_at IS NOT NULL',[$a['id']])->fetchColumn())crm_fail(401,'Срок обращения истёк.');return $a;
}
function ai_versions(array $t,bool $lock=false):array{
 $a=ai_task_actor($t);$out=[];
 foreach(['project'=>'project_id','lead'=>'lead_id','revision'=>'revision_id'] as $kind=>$field)if($t[$field]){$r=ai_scope($a,$kind,(int)$t[$field],$lock);if($kind==='project'&&($r['archived_at']!==null||$r['status']==='cancelled'||$r['customer_status']!=='active'))crm_fail(409,'Проект закрыт для ИИ-изменений.');$out[$kind]=['id'=>(int)$r['id'],'version'=>(int)$r['version']];}
 return $out;
}
