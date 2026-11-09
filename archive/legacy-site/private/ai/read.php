<?php
declare(strict_types=1);
function ai_list_tasks(array $a):array{
 $where=['1=1'];$p=[];if($a['type']!=='owner'){$where[]='actor_type=? AND actor_id=? AND expires_at>UTC_TIMESTAMP()';array_push($p,$a['type'],$a['id']);}
 foreach(['agent'=>'agent_id','state'=>'state','project_id'=>'project_id','customer_id'=>'customer_id'] as $q=>$field)if(isset($_GET[$q])&&$_GET[$q]!==''){if(!is_string($_GET[$q])||strlen($_GET[$q])>64)crm_fail(422,'Проверьте фильтр.');$where[]=$field.'=?';$p[]=$_GET[$q];}
 $rows=crm_query('SELECT id,agent_id,state,project_id,customer_id,last_error,attempts,version,created_at,expires_at FROM nd_ai_tasks WHERE '.implode(' AND ',$where).' ORDER BY id DESC LIMIT 25 OFFSET '.((cc_page()-1)*25),$p)->fetchAll();return ['ok'=>true,'items'=>$rows,'page'=>cc_page(),'page_size'=>25];
}
function ai_overview():array{
 $counts=crm_query('SELECT state,COUNT(*) AS count FROM nd_ai_tasks GROUP BY state')->fetchAll();return ['ok'=>true,'states'=>$counts,'provider_status'=>ai_provider_status(),'scheduler_verified'=>false,'periodic_authorized'=>(config()['ai_periodic_authorized']??false)===true,'recent'=>crm_query('SELECT id,agent_id,state,created_at FROM nd_ai_tasks ORDER BY id DESC LIMIT 10')->fetchAll()];
}
function ai_agents_list():array{
 $items=[];foreach(ai_registry() as $id=>$def){$row=crm_query('SELECT enabled,version FROM nd_ai_agents WHERE agent_id=?',[$id])->fetch();$counts=crm_query("SELECT COUNT(*) AS tasks,SUM(state='FAILED') AS errors,MAX(created_at) AS last_execution FROM nd_ai_tasks WHERE agent_id=?",[$id])->fetch();$items[]=array_merge($def,['enabled'=>$row?(bool)$row['enabled']:false,'config_version'=>$row?(int)$row['version']:0,'counts'=>$counts]);}return ['ok'=>true,'items'=>$items];
}
function ai_agent_update(string $id,array $d):array{
 ai_agent($id);if(array_diff(array_keys($d),['enabled','version'])||!is_bool($d['enabled']??null)||!is_int($d['version']??null))crm_fail(422,'Можно менять только доступность агента. Права определяются сервером.');
 return crm_atomic(function()use($id,$d){crm_query('INSERT INTO nd_ai_agents(agent_id,enabled,version) VALUES (?,0,0) ON DUPLICATE KEY UPDATE agent_id=VALUES(agent_id)',[$id]);$row=crm_query('SELECT * FROM nd_ai_agents WHERE agent_id=? FOR UPDATE',[$id])->fetch();crm_version($d,$row);crm_query('UPDATE nd_ai_agents SET enabled=?,version=version+1 WHERE agent_id=?',[$d['enabled']?1:0,$id]);return ['ok'=>true,'id'=>$id];});
}
function ai_usage_report():array{
 foreach(['from','to'] as $f)if(isset($_GET[$f])&&(!is_string($_GET[$f])||!preg_match('/^\d{4}-\d{2}-\d{2}$/D',$_GET[$f])))crm_fail(422,'Проверьте даты отчёта.');$from=$_GET['from']??gmdate('Y-m-01');$to=$_GET['to']??gmdate('Y-m-d');
 $rows=crm_query('SELECT agent_id,currency,model,COUNT(*) AS calls,SUM(reserved_tokens) AS reserved_tokens,SUM(input_tokens) AS input_tokens,SUM(output_tokens) AS output_tokens,SUM(estimated_micro) AS estimated_micro,SUM(actual_micro) AS actual_micro,COUNT(actual_micro) AS actual_cost_reports FROM nd_ai_usage WHERE DATE(created_at)>=? AND DATE(created_at)<=? GROUP BY agent_id,currency,model ORDER BY agent_id,currency,model',[$from,$to])->fetchAll();return ['ok'=>true,'items'=>$rows,'meaning'=>'Оценка по настроенной ставке, не счёт провайдера. Резервы после неизвестного результата не возвращаются. Неизвестные usage/cost — NULL; валюты не объединяются.'];
}
