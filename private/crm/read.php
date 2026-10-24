<?php
declare(strict_types=1);
function crm_list(string $kind,array $filters=[]):array{
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
 foreach($rows as &$r){
  if($kind==='projects'){$r['progress']=crm_progress((int)$r['id']);$r['customer_name']=crm_record('customers',(int)$r['customer_id'])['name'];$r['overdue_tasks']=(int)crm_query("SELECT COUNT(*) FROM nd_tasks JOIN nd_task_projects ON task_id=nd_tasks.id WHERE project_id=? AND due_at<UTC_TIMESTAMP() AND status NOT IN ('done','cancelled') AND archived_at IS NULL",[$r['id']])->fetchColumn();}
  if($kind==='customers'){$r['orders_count']=(int)crm_query('SELECT COUNT(*) FROM nd_orders WHERE customer_id=?',[$r['id']])->fetchColumn();$r['projects_count']=(int)crm_query("SELECT COUNT(*) FROM nd_projects WHERE customer_id=? AND archived_at IS NULL AND status NOT IN ('completed','cancelled')",[$r['id']])->fetchColumn();$r['leads_count']=(int)crm_query('SELECT COUNT(*) FROM nd_lead_customers WHERE customer_id=?',[$r['id']])->fetchColumn();}
 }unset($r);
 return ['ok'=>true,'items'=>$rows,'page'=>$page,'total'=>$total,'page_size'=>$limit];
}
function crm_detail(string $kind,int $id):array{
 if($kind==='leads'){$r=crm_query('SELECT * FROM nd_leads WHERE id=?',[$id])->fetch();if(!$r)crm_fail(404,'Заявка не найдена.');return ['ok'=>true,'record'=>$r];}
 $r=crm_record($kind,$id);$related=[];
 if($kind==='customers')foreach(['leads','deals','orders','projects','activity'] as $k)$related[$k]=crm_list($k,['customer_id'=>$id,'archived'=>'all']);
 if($kind==='projects'){
  $r['progress']=crm_progress($id);$related['stages']=crm_query('SELECT * FROM nd_project_stages WHERE project_id=? ORDER BY position,id',[$id])->fetchAll();$related['tasks']=crm_list('tasks',['project_id'=>$id,'archived'=>'all']);
  $related['members']=crm_query('SELECT m.employee_id,m.role,e.name FROM nd_project_members m JOIN nd_employees e ON e.id=m.employee_id WHERE project_id=?',[$id])->fetchAll();
 }
 if($kind==='employees'){$related['tasks']=crm_list('tasks',['assignee_employee_id'=>$id,'archived'=>'all']);$related['projects']=['items'=>crm_query('SELECT p.* FROM nd_projects p JOIN nd_project_members m ON m.project_id=p.id WHERE m.employee_id=?',[$id])->fetchAll()];}
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
 return ['ok'=>true,'kpi'=>$kpi,'recent_leads'=>crm_list('leads')['items'],'projects'=>crm_list('projects')['items'],'deadlines'=>crm_list('tasks',['due_soon'=>'true'])['items'],'activity'=>crm_list('activity')['items']];
}
