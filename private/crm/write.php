<?php
declare(strict_types=1);
function crm_write(string $kind,int $id,string $action,array $d,string $method):array{
 if($method==='POST'&&$id===0)return crm_idempotent($kind,$d,fn()=>crm_insert($kind,$d));
 if($action==='convert'&&$kind==='deals')return crm_idempotent('convert/'.$id,$d,function()use($id,$d){
  $row=crm_record('deals',$id,true);crm_version($d,$row);if($row['status']!=='won'||$row['archived_at']!==null||($d['confirm']??false)!==true)crm_fail(422,'Подтвердите создание заказа из успешной сделки.');
  $q=crm_query('SELECT order_id FROM nd_crm_conversions WHERE deal_id=?',[$id]);$existing=$q->fetchColumn();
  if(!$existing)$existing=crm_query('SELECT id FROM nd_orders WHERE deal_id=? LIMIT 1',[$id])->fetchColumn();
  if($existing)return ['ok'=>true,'record'=>crm_record('orders',(int)$existing)];
  $order=crm_insert('orders',['title'=>$row['title'],'customer_id'=>(int)$row['customer_id'],'total_amount'=>$row['estimated_amount']??'0.00','currency'=>'RUB']);
  $orderId=(int)$order['record']['id'];crm_query('UPDATE nd_orders SET deal_id=? WHERE id=?',[$id,$orderId]);crm_query('INSERT INTO nd_crm_conversions VALUES (?,?)',[$id,$orderId]);$order['record']['deal_id']=$id;return $order;
 });
 return crm_atomic(function()use($kind,$id,$action,$d,$method){
  $old=crm_record($kind,$id,true);crm_version($d,$old);
  if($action==='link'&&$kind==='customers'){
   if($old['status']!=='active')crm_fail(422,'Клиент архивирован.');$lead=$d['lead_id']??null;
   if(!is_int($lead)||!crm_query('SELECT id FROM nd_leads WHERE id=? FOR UPDATE',[$lead])->fetch())crm_fail(404,'Заявка не найдена.');
   $existing=crm_query('SELECT customer_id FROM nd_lead_customers WHERE lead_id=?',[$lead])->fetchColumn();
   if($existing&&(int)$existing!==$id)crm_fail(409,'Заявка уже принадлежит другому клиенту.');
   if(!$existing)crm_query('INSERT INTO nd_lead_customers(lead_id,customer_id) VALUES (?,?)',[$lead,$id]);
   crm_query('UPDATE nd_customers SET version=version+1 WHERE id=?',[$id]);crm_event($kind,$id,'lead_linked');return ['ok'=>true,'record'=>crm_record($kind,$id)];
  }
  if($action==='members'&&$kind==='projects'){
   $employee=$d['employee_id']??null;if(!is_int($employee)||crm_record('employees',$employee,true)['status']!=='active'||$old['archived_at']!==null)crm_fail(422,'Выберите активного сотрудника и проект.');
   $role=$d['role']??'contributor';if(!in_array($role,['manager','contributor','observer'],true))crm_fail(422,'Неизвестная роль в проекте.');
   crm_query('INSERT INTO nd_project_members(project_id,employee_id,role) VALUES (?,?,?) ON DUPLICATE KEY UPDATE role=VALUES(role)',[$id,$employee,$role]);crm_query('UPDATE nd_projects SET version=version+1 WHERE id=?',[$id]);crm_event($kind,$id,'member_assigned',$old);return ['ok'=>true,'record'=>crm_record($kind,$id)];
  }
  if($action==='reorder'&&$kind==='projects'){
   $ids=$d['stage_ids']??null;if(!is_array($ids)||count($ids)>1000||array_filter($ids,fn($v)=>!is_int($v)||$v<1))crm_fail(422,'Некорректный порядок этапов.');
   $current=crm_query('SELECT id,position FROM nd_project_stages WHERE project_id=? FOR UPDATE',[$id])->fetchAll();$expected=array_map(fn($r)=>(int)$r['id'],$current);$sorted=$ids;sort($expected);sort($sorted);if($sorted!==$expected)crm_fail(409,'Список этапов изменился. Обновите проект.');
   $max=$current?max(array_column($current,'position')):0;if($max+count($ids)>4294967295)crm_fail(422,'Невозможно изменить порядок.');
   foreach($ids as $i=>$sid)crm_query('UPDATE nd_project_stages SET position=? WHERE id=?',[$max+$i+1,$sid]);
   foreach($ids as $i=>$sid)crm_query('UPDATE nd_project_stages SET position=?,version=version+1 WHERE id=?',[$i+1,$sid]);
   crm_query('UPDATE nd_projects SET version=version+1 WHERE id=?',[$id]);crm_event($kind,$id,'stages_reordered',$old);return ['ok'=>true,'record'=>crm_record($kind,$id)];
  }
  if(in_array($action,['archive','restore'],true)){
   $v=['archived_at'=>$action==='archive'?gmdate('Y-m-d H:i:s'):null];
   if(in_array($kind,['customers','employees'],true))$v['status']=$action==='archive'?'archived':($kind==='customers'?'active':'suspended');
   if($kind==='stages')crm_fail(422,'Для этапа используйте статус отмены.');
  }elseif($action===''&&$method==='PATCH'){
   if($old['archived_at']!==null)crm_fail(422,'Сначала восстановите запись.');
   $v=crm_values($kind,$d,$old);
   if($kind==='projects'&&($v['status']??'')==='completed'){
    $progress=crm_progress($id);if($progress['total']===0||$progress['percent']!==100)crm_fail(422,'Для завершения проекта завершите все этапы.');
   }
   if($kind==='tasks'&&(isset($d['project_id'])||isset($d['stage_id'])))crm_fail(422,'Привязка задачи задаётся при создании.');
  }else crm_fail(404,'Действие не найдено.');
  if(!$v)crm_fail(422,'Нет изменений для сохранения.');
  $assign=implode(',',array_map(fn($k)=>$k.'=?',array_keys($v)));crm_query('UPDATE '.crm_table($kind).' SET '.$assign.',version=version+1 WHERE id=? AND version=?',[...array_values($v),$id,$old['version']]);
  if($kind==='stages')crm_query('UPDATE nd_projects SET version=version+1 WHERE id=?',[$old['project_id']]);
  crm_event($kind,$id,$action?:'updated',array_replace($old,$v));return ['ok'=>true,'record'=>crm_record($kind,$id)];
 });
}
