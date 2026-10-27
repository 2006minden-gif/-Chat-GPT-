<?php
declare(strict_types=1);
function crm_enrich(string $kind,array $row):array{
 if($kind==='leads')$row['created_at']=gmdate('Y-m-d H:i:s',(int)$row['created']);
 if($kind==='tasks'){$link=crm_query('SELECT tp.project_id,tp.stage_id,p.title AS project_name,s.title AS stage_name FROM nd_task_projects tp JOIN nd_projects p ON p.id=tp.project_id LEFT JOIN nd_project_stages s ON s.id=tp.stage_id WHERE tp.task_id=?',[$row['id']])->fetch();if($link)$row=array_replace($row,$link);}
 if((config()['single_owner_mode']??false)!==true)foreach(['owner_employee_id','manager_employee_id','assignee_employee_id'] as $f)if(!empty($row[$f])){$row['responsible_name']=crm_record('employees',(int)$row[$f])['name'];break;}
 return $row;
}
function crm_list(string $kind,array $filters=[]):array{
 foreach($filters as $value)if((!is_string($value)&&!is_int($value))||strlen((string)$value)>500)crm_fail(422,'Проверьте параметры фильтра.');
 $table=$kind==='leads'?'nd_leads':($kind==='activity'?'nd_activity_history':($kind==='notifications'?'nd_crm_notifications':crm_table($kind)));
 $where=[];$p=[];$active=array_key_exists($kind,crm_models())&&$kind!=='stages';
 if($active&&($filters['archived']??'')!=='all'){
  if(in_array($kind,['customers','employees'],true)){$where[]='t.status'.(($filters['archived']??'')==='true'?"='archived'":"<>'archived'");}
  else $where[]='t.archived_at IS '.(($filters['archived']??'')==='true'?'NOT NULL':'NULL');
 }
 $allowed=['status','customer_id','project_id','assignee_employee_id','priority','kind'];
 foreach($allowed as $f){if(!isset($filters[$f])||$filters[$f]==='')continue;
  if(($f==='project_id'&&$kind==='tasks')){$where[]='t.id IN (SELECT task_id FROM nd_task_projects WHERE project_id=?)';$p[]=$filters[$f];continue;}
  if($f==='customer_id'&&$kind==='leads'){$where[]='t.id IN (SELECT lead_id FROM nd_lead_customers WHERE customer_id=?)';$p[]=$filters[$f];continue;}
  if($kind==='activity'&&$f==='customer_id'||in_array($f,crm_models()[$kind]??[],true)||$kind==='leads'&&$f==='status'){$where[]='t.'.$f.'=?';$p[]=$filters[$f];}
 }
 if(($filters['active']??'')==='true'&&in_array($kind,['deals','orders','projects'],true))$where[]="t.status NOT IN ('won','lost','completed','cancelled')";
 $search=$filters['search']??'';if(!is_string($search)||strlen($search)>300)crm_fail(422,'Слишком длинный поиск.');
 if($search!==''&&in_array($kind,array_merge(array_keys(crm_models()),['leads']),true)){$f=in_array($kind,['customers','employees','leads'],true)?'name':'title';$where[]='t.'.$f.' LIKE ?';$p[]='%'.$search.'%';}
 if($kind==='notifications'&&($filters['unread']??'')==='true')$where[]='t.read_at IS NULL';
 if(($filters['overdue']??'')==='true'&&$kind==='tasks')$where[]="t.due_at<UTC_TIMESTAMP() AND t.status NOT IN ('done','cancelled')";
 if(($filters['due_soon']??'')==='true'&&$kind==='tasks')$where[]="t.due_at<=DATE_ADD(UTC_TIMESTAMP(), INTERVAL 7 DAY) AND t.status NOT IN ('done','cancelled')";
 $w=$where?' WHERE '.implode(' AND ',$where):'';
 $page=filter_var($filters['page']??1,FILTER_VALIDATE_INT);if(!$page||$page<1||$page>100000)crm_fail(422,'Некорректная страница.');$limit=25;$offset=($page-1)*$limit;
 $total=(int)crm_query('SELECT COUNT(*) FROM '.$table.' t'.$w,$p)->fetchColumn();
 $rows=crm_query('SELECT t.* FROM '.$table.' t'.$w.' ORDER BY t.id DESC LIMIT '.$limit.' OFFSET '.$offset,$p)->fetchAll();
 foreach($rows as &$r){$r=crm_enrich($kind,$r);
  if(in_array($kind,['deals','orders','projects'],true))$r['customer_name']=crm_record('customers',(int)$r['customer_id'])['name'];
  if($kind==='projects'){$r['progress']=crm_progress((int)$r['id']);$r['current_stage']=crm_query("SELECT title FROM nd_project_stages WHERE project_id=? AND status IN ('active','planned') ORDER BY status='active' DESC,position LIMIT 1",[$r['id']])->fetchColumn()?:null;$r['overdue_tasks']=(int)crm_query("SELECT COUNT(*) FROM nd_tasks JOIN nd_task_projects ON task_id=nd_tasks.id WHERE project_id=? AND due_at<UTC_TIMESTAMP() AND status NOT IN ('done','cancelled') AND archived_at IS NULL",[$r['id']])->fetchColumn();}
  if($kind==='customers'){$r['last_activity']=crm_query('SELECT MAX(created_at) FROM nd_activity_history WHERE customer_id=?',[$r['id']])->fetchColumn();$r['orders_count']=(int)crm_query('SELECT COUNT(*) FROM nd_orders WHERE customer_id=?',[$r['id']])->fetchColumn();$r['projects_count']=(int)crm_query("SELECT COUNT(*) FROM nd_projects WHERE customer_id=? AND archived_at IS NULL AND status NOT IN ('completed','cancelled')",[$r['id']])->fetchColumn();$r['leads_count']=(int)crm_query('SELECT COUNT(*) FROM nd_lead_customers WHERE customer_id=?',[$r['id']])->fetchColumn();}
 }unset($r);
 return ['ok'=>true,'items'=>$rows,'page'=>$page,'total'=>$total,'page_size'=>$limit];
}
function crm_detail(string $kind,int $id):array{
 if($kind==='leads'){$r=crm_query('SELECT * FROM nd_leads WHERE id=?',[$id])->fetch();if(!$r)crm_fail(404,'Заявка не найдена.');return ['ok'=>true,'record'=>crm_enrich('leads',$r)];}
 $r=crm_enrich($kind,crm_record($kind,$id));if(isset($r['customer_id']))$r['customer_name']=crm_record('customers',(int)$r['customer_id'])['name'];$related=[];
 if($kind==='customers')foreach(['leads','deals','orders','projects','activity'] as $k)$related[$k]=crm_list($k,['customer_id'=>$id,'archived'=>'all']);
 if($kind==='projects'){
  $r['progress']=crm_progress($id);$related['stages']=crm_query('SELECT * FROM nd_project_stages WHERE project_id=? ORDER BY position,id',[$id])->fetchAll();$related['tasks']=crm_list('tasks',['project_id'=>$id,'archived'=>'all']);
  if((config()['single_owner_mode']??false)!==true)$related['members']=crm_query('SELECT m.employee_id,m.role,e.name FROM nd_project_members m JOIN nd_employees e ON e.id=m.employee_id WHERE project_id=?',[$id])->fetchAll();
 }
 if($kind==='employees'){$related['tasks']=crm_list('tasks',['assignee_employee_id'=>$id,'archived'=>'all']);$related['projects']=['items'=>crm_query('SELECT DISTINCT p.* FROM nd_projects p LEFT JOIN nd_project_members m ON m.project_id=p.id AND m.employee_id=? WHERE m.employee_id IS NOT NULL OR p.manager_employee_id=?',[$id,$id])->fetchAll()];}
 if($kind==='orders')$related['projects']= ['items'=>crm_query('SELECT * FROM nd_projects WHERE order_id=?',[$id])->fetchAll()];
 if($kind==='deals')$related['orders']=['items'=>crm_query('SELECT * FROM nd_orders WHERE deal_id=?',[$id])->fetchAll()];
 if($kind==='tasks')$related['project']=crm_query('SELECT project_id,stage_id FROM nd_task_projects WHERE task_id=?',[$id])->fetch()?:null;
 $f=['customers'=>'customer_id','deals'=>'deal_id','orders'=>'order_id','projects'=>'project_id','stages'=>'stage_id','tasks'=>'task_id','employees'=>'employee_id'][$kind];
 $related['history']=crm_query('SELECT id,action,summary,created_at,actor_admin_id FROM nd_activity_history WHERE '.$f.'=? ORDER BY id DESC LIMIT 100',[$id])->fetchAll();
 return ['ok'=>true,'record'=>$r,'related'=>$related];
}
function crm_dashboard(array $filter):array {
 $counts=[
 'leads'=>"SELECT COUNT(*) FROM nd_leads WHERE status='Новая'",
 'deals'=>"SELECT COUNT(*) FROM nd_deals WHERE archived_at IS NULL AND status NOT IN ('won','lost')",
 'orders'=>"SELECT COUNT(*) FROM nd_orders WHERE archived_at IS NULL AND status NOT IN ('completed','cancelled')",
 'projects'=>"SELECT COUNT(*) FROM nd_projects WHERE archived_at IS NULL AND status NOT IN ('completed','cancelled')",
 'overdue'=>"SELECT COUNT(*) FROM nd_tasks WHERE archived_at IS NULL AND due_at<UTC_TIMESTAMP() AND status NOT IN ('done','cancelled')",
 'completed'=>"SELECT COUNT(*) FROM nd_projects WHERE status='completed'"
 ];$kpi=[];foreach($counts as $k=>$sql)$kpi[$k]=(int)crm_query($sql)->fetchColumn();
 $result=['ok'=>true,'kpi'=>$kpi,'recent_leads'=>crm_list('leads')['items'],'projects'=>crm_list('projects')['items'],'deadlines'=>crm_list('tasks',['due_soon'=>'true'])['items'],'activity'=>crm_list('activity')['items']];
 if((config()['order_lifecycle_enabled']??false)===true&&crm_query("SELECT state FROM nd_schema_migrations WHERE version='016_order_lifecycle'")->fetchColumn()==='applied'){require_once dirname(__DIR__).'/lifecycle/dashboard.php';$result['lifecycle']=lc_owner_dashboard();}return $result;
}
