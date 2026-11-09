<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/crm/core.php';
function cc_actor(bool $customer,bool $write=false):array{
 if($customer){require_once dirname(__DIR__).'/customer-auth.php';ca_gate();$s=ca_session($write);$a=ca_account((int)($s['account_id']??0));if(!ca_account_allowed($a)||!ca_current_consent($a))crm_fail(401,'Войдите в кабинет и подтвердите актуальные документы.');$actor=['type'=>'customer','id'=>(int)$a['id'],'customer_id'=>(int)$a['customer_id']];}
 else{current_session($write);$actor=['type'=>'owner','id'=>1];}
 crm_gate();if((config()['client_collaboration_enabled']??false)!==true)crm_fail(503,'Совместная работа пока отключена владельцем.');
 if(crm_query("SELECT state FROM nd_schema_migrations WHERE version='007_client_collaboration'")->fetchColumn()!=='applied')crm_fail(503,'Совместная работа ещё не настроена.');
 return $actor;
}
function cc_project(array $a,int $id,bool $write=false,bool $lock=false):array{
 $params=[$id];$sql='SELECT p.*,c.status AS customer_status FROM nd_projects p JOIN nd_customers c ON c.id=p.customer_id WHERE p.id=?';
 if($a['type']==='customer'){$sql.=" AND p.customer_id=? AND c.status='active'";$params[]=$a['customer_id'];}
 if($lock)$sql.=' FOR UPDATE';$p=crm_query($sql,$params)->fetch();if(!$p)crm_fail(404,'Запись не найдена.');
 if($a['type']==='customer'&&$p['order_id']&&!($a['document_archive']??false)){require_once dirname(__DIR__).'/support/core.php';sa_assert((int)$p['order_id']);}
 if($write&&($p['archived_at']!==null||$p['status']==='cancelled'||$p['customer_status']!=='active'))crm_fail(409,'Проект закрыт для изменений. История сохранена для чтения.');return $p;
}
function cc_owner(array $a):void{if($a['type']!=='owner')crm_fail(403,'Это действие доступно только владельцу.');}
function cc_id(mixed $v):int{if(!is_int($v)||$v<1||$v>2147483647)crm_fail(422,'Выберите существующую запись.');return $v;}
function cc_text(array $d,string $field,int $max,bool $required=true):string{
 $labels=['body'=>'Текст','title'=>'Название','feedback'=>'Комментарий','acceptance'=>'Критерии приёмки'];$v=$d[$field]??'';
 if(!is_string($v)||!mb_check_encoding($v,'UTF-8')||str_contains($v,"\0")||mb_strlen($v)>$max||($required&&trim($v)===''))crm_fail(422,($labels[$field]??'Поле').': проверьте заполнение и длину.');return trim($v);
}
function cc_event(array $a,int $project,string $action,array $context=[]):void{
 $p=cc_project($a,$project);$admin=$a['type']==='owner'?1:null;$customer=$a['type']==='customer'?$a['id']:null;
 crm_query('INSERT INTO nd_activity_history(actor_admin_id,actor_customer_account_id,project_id,customer_id,action,summary) VALUES (?,?,?,?,?,?)',[$admin,$customer,$project,$p['customer_id'],'cc_'.$action,'Событие совместной работы']);
 $eventId=(int)db()->lastInsertId();crm_notice('cc:'.$eventId,'projects',$project,'Новое событие совместной работы');
 if((config()['billing_enabled']??false)===true){require_once dirname(__DIR__).'/billing/hooks.php';bill_collaboration_event($eventId,$project,$action,(int)$p['customer_id'],$context);}
}
function cc_mutation(array $a,string $route,array $d,callable $fn):array{
 return crm_idempotent('cc:'.$a['type'].':'.$a['id'].':'.$route,$d,$fn);
}
function cc_page():int{$p=filter_var($_GET['page']??1,FILTER_VALIDATE_INT);if(!$p||$p<1||$p>100000)crm_fail(422,'Некорректная страница.');return (int)$p;}
function cc_files_for(array $a,int $project,array $ids,bool $publication=false):array{
 foreach($ids as $id)cc_id($id);
 if(count($ids)>10||count(array_unique($ids))!==count($ids))crm_fail(422,'Не более 10 разных вложений.');$out=[];
 foreach($ids as $id){cc_id($id);$f=cc_file($a,$id);if((int)$f['project_id']!==$project||$f['archived_at']!==null||($publication&&$f['visibility']!=='customer'))crm_fail(422,'Вложение недоступно для этого проекта или клиента.');cc_file_path($f);$out[]=$f;}
 return $out;
}
function cc_public_file(array $r):array{unset($r['storage_key']);return $r;}
