<?php
declare(strict_types=1);
final class CrmFailure extends RuntimeException {public function __construct(public int $status,string $message){parent::__construct($message);}}
function crm_fail(int $status,string $message):never{throw new CrmFailure($status,$message);}
function crm_gate():void{
 if((config()['crm_operations_enabled']??false)!==true||!privacy_settings()['enabled'])crm_fail(503,'Работа CRM отключена до одобрения документов и настройки владельцем.');
 db()->exec("SET time_zone='+00:00'");
 $q=db()->query("SELECT version,state FROM nd_schema_migrations WHERE version IN ('004_crm_foundation','005_customer_auth','006_crm_operations')");
 $rows=$q->fetchAll();if(count($rows)!==3||array_filter($rows,fn($r)=>$r['state']!=='applied'))crm_fail(503,'CRM ещё не подготовлена. Требуется проверенная установка схемы.');
}
function crm_query(string $sql,array $p=[]):PDOStatement{$q=db()->prepare($sql);$q->execute($p);return $q;}
function crm_models():array{return [
 'customers'=>['name','kind','email','phone','telegram','notes','status'],
 'deals'=>['title','customer_id','lead_id','owner_employee_id','estimated_amount','currency','status','due_on','loss_reason'],
 'orders'=>['title','customer_id','deal_id','total_amount','currency','status','due_on','notes'],
 'projects'=>['title','customer_id','order_id','manager_employee_id','description','status','starts_on','due_on'],
 'stages'=>['title','project_id','position','status','due_on'],
 'tasks'=>['title','description','assignee_employee_id','priority','status','due_at'],
 'employees'=>['name','email','position','status']
];}
function crm_table(string $kind):string {if(!isset(crm_models()[$kind]))crm_fail(404,'Раздел не найден.');return $kind==='stages'?'nd_project_stages':'nd_'.$kind;}
function crm_states():array{return ['customers'=>['active','archived'],'employees'=>['invited','active','suspended','archived'],'deals'=>['new','qualified','proposal','negotiation','won','lost'],'orders'=>['draft','confirmed','in_progress','completed','cancelled'],'projects'=>['planned','active','on_hold','completed','cancelled'],'stages'=>['planned','active','completed','cancelled'],'tasks'=>['todo','in_progress','blocked','done','cancelled']];}
function crm_record(string $kind,int $id,bool $lock=false):array {
 $r=crm_query('SELECT * FROM '.crm_table($kind).' WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');return $r;
}
function crm_version(array $d,array $row):void{if(!isset($d['version'])||!is_int($d['version'])||$d['version']!==(int)$row['version'])crm_fail(409,'Запись изменена. Ваш черновик сохранён. Загрузите актуальные данные перед повторным сохранением.');}
function crm_event(string $kind,int $id,string $action,array $row=[]):void {
 $field=['customers'=>'customer_id','deals'=>'deal_id','orders'=>'order_id','projects'=>'project_id','tasks'=>'task_id','employees'=>'employee_id','stages'=>'stage_id'][$kind];
 $context=[];
 foreach(['customer_id','project_id','lead_id'] as $f)if(isset($row[$f])&&$f!==$field)$context[$f]=$row[$f];
 if($kind==='tasks'){$link=crm_query('SELECT project_id FROM nd_task_projects WHERE task_id=?',[$id])->fetch();if($link)$context['project_id']=$link['project_id'];}
 if(isset($context['project_id'])&&!isset($context['customer_id']))$context['customer_id']=crm_record('projects',(int)$context['project_id'])['customer_id'];
 $columns=['actor_admin_id',$field,'action','summary',...array_keys($context)];
 crm_query('INSERT INTO nd_activity_history('.implode(',',$columns).') VALUES ('.implode(',',array_fill(0,count($columns),'?')).')',[1,$id,$action,'Изменение записи CRM',...array_values($context)]);
 $event=(string)db()->lastInsertId();
 if($kind==='projects'&&$action==='updated'&&($row['status']??'')==='completed'&&(config()['billing_enabled']??false)===true){require_once dirname(__DIR__).'/billing/hooks.php';bill_hook_event('activity:'.$event,'project_completed','projects',$id,(int)$row['customer_id']);}
 crm_notice('activity:'.$event,$kind,$id,'Обновлена запись: '.crm_labels()[$kind]);
}
function crm_labels():array{return ['customers'=>'Клиенты','deals'=>'Сделки','orders'=>'Заказы','projects'=>'Проекты','tasks'=>'Задачи','employees'=>'Сотрудники','stages'=>'Этапы','leads'=>'Заявки'];}
function crm_notice(string $key,string $kind,int $id,string $message):void{crm_query('INSERT INTO nd_crm_notifications(event_key,entity,record_id,message) VALUES (?,?,?,?) ON DUPLICATE KEY UPDATE event_key=VALUES(event_key)',[$key,$kind,$id,$message]);}
function crm_notifications():void{
 // Evaluated only during an authenticated owner's notification request. No cron assumed.
 foreach(crm_query("SELECT id FROM nd_leads ORDER BY id DESC LIMIT 100")->fetchAll() as $r)crm_notice('lead:'.$r['id'],'leads',(int)$r['id'],'Получена новая заявка');
 foreach(crm_query("SELECT id,due_at FROM nd_tasks WHERE archived_at IS NULL AND status NOT IN ('done','cancelled') AND due_at<UTC_TIMESTAMP() ORDER BY due_at LIMIT 100")->fetchAll() as $r)crm_notice('task:'.$r['id'].':'.$r['due_at'],'tasks',(int)$r['id'],'Просрочен срок задачи');
 foreach(crm_query("SELECT id,due_on FROM nd_projects WHERE archived_at IS NULL AND status IN ('planned','active','on_hold') AND due_on<=DATE_ADD(UTC_DATE(),INTERVAL 7 DAY) ORDER BY due_on LIMIT 100")->fetchAll() as $r)crm_notice('project:'.$r['id'].':'.$r['due_on'],'projects',(int)$r['id'],'Приближается срок проекта');
}
function crm_transition(string $kind,string $old,string $new):void{
 $maps=[
 'deals'=>['new'=>['qualified','lost'],'qualified'=>['proposal','negotiation','lost'],'proposal'=>['negotiation','won','lost'],'negotiation'=>['proposal','won','lost'],'won'=>[],'lost'=>['new']],
 'orders'=>['draft'=>['confirmed','cancelled'],'confirmed'=>['in_progress','cancelled'],'in_progress'=>['completed','cancelled'],'completed'=>[],'cancelled'=>['draft']],
 'projects'=>['planned'=>['active','cancelled'],'active'=>['on_hold','completed','cancelled'],'on_hold'=>['active','cancelled'],'completed'=>[],'cancelled'=>['planned']],
 'tasks'=>['todo'=>['in_progress','blocked','cancelled'],'in_progress'=>['blocked','done','cancelled'],'blocked'=>['todo','in_progress','cancelled'],'done'=>['todo'],'cancelled'=>['todo']],
 'stages'=>['planned'=>['active','cancelled'],'active'=>['completed','cancelled'],'completed'=>['active'],'cancelled'=>['planned']]
 ];
 if($old!==$new&&isset($maps[$kind])&&!in_array($new,$maps[$kind][$old]??[],true))crm_fail(422,'Этот переход статуса недоступен.');
}
function crm_field_label(string $field):string{return ['name'=>'Имя','title'=>'Название','email'=>'Email','phone'=>'Телефон','telegram'=>'Telegram','kind'=>'Тип клиента','notes'=>'Заметки','description'=>'Описание','status'=>'Статус','customer_id'=>'Клиент','lead_id'=>'Заявка','deal_id'=>'Сделка','order_id'=>'Заказ','project_id'=>'Проект','stage_id'=>'Этап','position'=>'Должность или порядок этапа','estimated_amount'=>'Ожидаемая сумма','total_amount'=>'Сумма заказа','currency'=>'Валюта','owner_employee_id'=>'Ответственный','manager_employee_id'=>'Менеджер','assignee_employee_id'=>'Исполнитель','priority'=>'Приоритет','due_on'=>'Срок','due_at'=>'Срок','starts_on'=>'Дата начала','loss_reason'=>'Причина отказа'][$field]??'Значение';}
function crm_values(string $kind,array $d,?array $old=null):array{
 $values=[];$fields=crm_models()[$kind];
 foreach($fields as $field){
  if(!array_key_exists($field,$d))continue;$v=$d[$field];
  if($v===null||$v===''){if(in_array($field,['email','phone','telegram','notes','description','position','due_on','due_at','starts_on','loss_reason','lead_id','owner_employee_id','manager_employee_id','assignee_employee_id','order_id','deal_id','estimated_amount'],true)){$values[$field]=null;continue;}}
  if(str_ends_with($field,'_id')||$field==='position'&&$kind==='stages'){
   if(!is_int($v)||$v<1||$v>2147483647)crm_fail(422,crm_field_label($field).': выберите существующую запись.');
  }else{
   if(!is_string($v)||!mb_check_encoding($v,'UTF-8')||mb_strlen($v)> (in_array($field,['description','notes'],true)?10000:($field==='loss_reason'?500:190)))crm_fail(422,crm_field_label($field).': проверьте длину и тип значения.');$v=trim($v);
  }
  if(in_array($field,['name','title','email','total_amount','currency'],true)&&$v==='')crm_fail(422,crm_field_label($field).': заполните значение.');
  if($field==='email'&&!filter_var($v,FILTER_VALIDATE_EMAIL))crm_fail(422,'Email: укажите корректный адрес.');
  if($field==='phone'&&(!preg_match('/^(?:\+7|8)[0-9]{10}$/D',preg_replace('/[\s()\-]/','',$v))))crm_fail(422,'Телефон: укажите номер РФ +7 или 8 и 10 цифр.');
  if($field==='telegram'&&!preg_match('/^@[A-Za-z][A-Za-z0-9_]{4,31}$/D',$v))crm_fail(422,'Telegram: укажите @username.');
  if(in_array($field,['total_amount','estimated_amount'],true)&&!preg_match('/^(?:0|[1-9][0-9]{0,12})(?:\.[0-9]{1,2})?$/D',$v))crm_fail(422,'Сумма: используйте положительное десятичное число с точкой, до двух знаков.');
  if($field==='currency'&&$v!=='RUB')crm_fail(422,'Поддерживается валюта RUB.');
  if($field==='kind'&&!in_array($v,['person','company'],true))crm_fail(422,'Выберите тип клиента.');
  if($field==='priority'&&!in_array($v,['low','normal','high','urgent'],true))crm_fail(422,'Выберите приоритет.');
  if($field==='status'&&!in_array($v,crm_states()[$kind],true))crm_fail(422,'Неизвестный статус.');
  if(in_array($field,['due_on','starts_on','due_at'],true)){$format=$field==='due_at'?'Y-m-d H:i:s':'Y-m-d';$dt=DateTimeImmutable::createFromFormat('!'.$format,$v,new DateTimeZone('UTC'));if(!$dt||$dt->format($format)!==$v)crm_fail(422,'Дата: укажите существующую дату (UTC).');}
  $values[$field]=$v;
 }
 $row=array_replace($old??[],$values);
 if(!$old){foreach($kind==='customers'||$kind==='employees'?['name']:($kind==='stages'?['title','project_id','position']:['title']) as $required)if(empty($row[$required]))crm_fail(422,crm_field_label($required).': обязательно.');}
 if($kind==='customers'&&empty($row['email'])&&empty($row['phone'])&&empty($row['telegram']))crm_fail(422,'Укажите email, телефон или Telegram клиента.');
 if($kind==='employees'&&empty($row['email']))crm_fail(422,'Email сотрудника обязателен.');
 if($old){foreach(['customer_id','project_id','deal_id','order_id','lead_id'] as $immutable)if(array_key_exists($immutable,$values)&&($values[$immutable]??null)!=($old[$immutable]??null))crm_fail(422,'Связь записи нельзя менять при редактировании.');if(isset($values['status']))crm_transition($kind,$old['status'],$values['status']);}
 elseif(isset($values['status'])&&$values['status']!==crm_states()[$kind][0])crm_fail(422,'Создайте запись в начальном статусе.');
 if(in_array($kind,['deals','orders','projects'],true)){
  if(empty($row['customer_id']))crm_fail(422,'Выберите клиента.');$customer=crm_record('customers',(int)$row['customer_id'],true);if($customer['status']!=='active')crm_fail(422,'Клиент архивирован.');
 }
 foreach(['owner_employee_id','manager_employee_id','assignee_employee_id'] as $f)if(!empty($row[$f])){if(crm_record('employees',(int)$row[$f],true)['status']!=='active')crm_fail(422,'Сотрудник не активен.');}
 foreach(['deal_id'=>'deals','order_id'=>'orders'] as $f=>$k)if(!empty($row[$f])){ $parent=crm_record($k,(int)$row[$f],true);if((int)$parent['customer_id']!==(int)$row['customer_id']||$parent['archived_at']!==null)crm_fail(422,'Связанный документ принадлежит другому клиенту или архивирован.');if($f==='deal_id'&&!$old)crm_fail(422,'Используйте явное создание заказа из успешной сделки.');}
 if($kind==='deals'&&!empty($row['lead_id'])&&!crm_query('SELECT 1 FROM nd_lead_customers WHERE lead_id=? AND customer_id=?',[$row['lead_id'],$row['customer_id']])->fetchColumn())crm_fail(422,'Заявка не связана с выбранным клиентом.');
 if($kind==='stages'){$project=crm_record('projects',(int)$row['project_id'],true);if($project['archived_at']!==null||in_array($project['status'],['completed','cancelled'],true))crm_fail(422,'Нельзя менять этапы завершённого, отменённого или архивного проекта.');}
 if(!empty($row['starts_on'])&&!empty($row['due_on'])&&$row['starts_on']>$row['due_on'])crm_fail(422,'Срок раньше даты начала.');
 if(isset($values['status'])){
  if(in_array($kind,['orders','projects','stages','tasks'],true))$values['completed_at']=in_array($values['status'],['completed','done'],true)?gmdate('Y-m-d H:i:s'):null;
  if($kind==='deals')$values['closed_at']=in_array($values['status'],['won','lost'],true)?gmdate('Y-m-d H:i:s'):null;
 }
 if($kind==='orders'&&($values['status']??'')==='confirmed')$values['confirmed_at']=gmdate('Y-m-d H:i:s');
 if($kind==='orders'&&!$old){if(!isset($row['total_amount']))crm_fail(422,'Укажите сумму заказа.');$values['number']='ND-'.strtoupper(bin2hex(random_bytes(8)));}
 return $values;
}
function crm_atomic(callable $fn):mixed{
 db()->beginTransaction();try{$out=$fn();db()->commit();return $out;}catch(Throwable $e){if(db()->inTransaction())db()->rollBack();throw $e;}
}
function crm_idempotent(string $route,array $d,callable $fn):array{
 $key=$d['request_key']??'';if(!is_string($key)||!preg_match('/^[a-f0-9]{64}$/D',$key))crm_fail(422,'Не удалось проверить повторную отправку. Откройте форму заново.');
 $hash=hash('sha256',$route.json_encode($d,JSON_THROW_ON_ERROR));
 return crm_atomic(function()use($key,$hash,$fn){
  crm_query('INSERT INTO nd_crm_requests(request_key,request_hash) VALUES (?,?) ON DUPLICATE KEY UPDATE request_key=VALUES(request_key)',[$key,$hash]);
  $r=crm_query('SELECT * FROM nd_crm_requests WHERE request_key=? FOR UPDATE',[$key])->fetch();if(!hash_equals($hash,$r['request_hash']))crm_fail(409,'Этот запрос уже использован с другими данными.');
  if($r['result']!==null)return json_decode($r['result'],true,512,JSON_THROW_ON_ERROR);
  $result=$fn();crm_query('UPDATE nd_crm_requests SET result=? WHERE request_key=?',[json_encode($result,JSON_THROW_ON_ERROR),$key]);return $result;
 });
}
function crm_insert(string $kind,array $data):array{
 $v=crm_values($kind,$data);$table=crm_table($kind);$cols=array_keys($v);
 crm_query('INSERT INTO '.$table.' ('.implode(',',$cols).') VALUES ('.implode(',',array_fill(0,count($cols),'?')).')',array_values($v));$id=(int)db()->lastInsertId();
 if($kind==='tasks'&&isset($data['stage_id'])&&!isset($data['project_id']))crm_fail(422,'Для этапа выберите проект.');
 if($kind==='tasks'&&isset($data['project_id']))crm_task_link($id,$data);
 if($kind==='stages')crm_query('UPDATE nd_projects SET version=version+1 WHERE id=?',[$v['project_id']]);
 $row=crm_record($kind,$id);crm_event($kind,$id,'created',$row);return ['ok'=>true,'record'=>$row];
}
function crm_task_link(int $id,array $d):void{
 $project=$d['project_id']??null;$stage=$d['stage_id']??null;
 if(!is_int($project)||$project<1)crm_fail(422,'Выберите проект.');$p=crm_record('projects',$project,true);if($p['archived_at']!==null)crm_fail(422,'Проект архивирован.');
 if($stage!==null&&(!is_int($stage)||!crm_query('SELECT 1 FROM nd_project_stages WHERE id=? AND project_id=?',[$stage,$project])->fetchColumn()))crm_fail(422,'Этап не принадлежит проекту.');
 crm_query('INSERT INTO nd_task_projects(task_id,project_id,stage_id) VALUES (?,?,?)',[$id,$project,$stage]);
}
function crm_progress(int $id):array{
 $r=crm_query("SELECT COUNT(*) AS total,SUM(status='completed') AS done FROM nd_project_stages WHERE project_id=?",[$id])->fetch();
 return ['total'=>(int)$r['total'],'completed'=>(int)$r['done'],'percent'=>(int)$r['total']?intdiv((int)$r['done']*100,(int)$r['total']):null];
}
