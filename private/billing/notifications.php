<?php
declare(strict_types=1);
function bill_templates():array{return [
 'support_expiring'=>'Приближается согласованный срок рабочего доступа','support_expired'=>'Рабочий доступ завершён; приватный архив сохранён','support_hold'=>'Прекращение доступа удержано до решения обязательств',
 'workflow_updated'=>'По заказу изменился следующий шаг','document_approved'=>'Документ согласован','new_request'=>'Получена новая заявка','new_message'=>'Новый комментарий по проекту','invoice_issued'=>'Новый счёт','invoice_adjusted'=>'Корректировка счёта','payment_pending'=>'Платёж обрабатывается','payment_confirmed'=>'Оплата подтверждена','payment_failed'=>'Оплата не прошла','payment_overdue'=>'Напоминание об оплате','refund_completed'=>'Возврат оформлен','awaiting_approval'=>'Документ ожидает согласования','changes_requested'=>'Запрошена доработка','new_deliverable'=>'Результат работы готов','project_completed'=>'Проект завершён','task_soon'=>'Приближается срок задачи','task_overdue'=>'Просрочен срок задачи'
];}
function bill_emit(string $key,string $template,string $entity,int $id,?int $customer,bool $essential=true):void{
 $title=bill_templates()[$template]??null;if($title===null)throw new LogicException('unknown_notification_template');
 $recipients=[['owner',1]];if($customer!==null)foreach(crm_query("SELECT a.id FROM nd_customer_accounts a JOIN nd_customers c ON c.id=a.customer_id WHERE a.customer_id=? AND a.status='active' AND c.status='active'",[$customer])->fetchAll() as $r)$recipients[]=['customer',(int)$r['id']];
 foreach($recipients as [$type,$rid])foreach(['in_app','email'] as $channel){
  $state=$channel==='in_app'?'delivered':((config()['billing_email_enabled']??false)===true?'pending':'disabled');
  if($channel==='email'&&!$essential&&$type==='customer'&&!(bool)crm_query('SELECT optional_email FROM nd_notification_preferences WHERE account_id=?',[$rid])->fetchColumn())$state='skipped';
  crm_query('INSERT INTO nd_notification_outbox(event_key,recipient_type,recipient_id,channel,template,entity,record_id,title,essential,state,delivered_at) VALUES (?,?,?,?,?,?,?,?,?,?,?) ON DUPLICATE KEY UPDATE event_key=VALUES(event_key)',[$key,$type,$rid,$channel,$template,$entity,$id,$title,$essential?1:0,$state,$channel==='in_app'?gmdate('Y-m-d H:i:s'):null]);
 }
 // Keep existing CRM owner inbox in use; the outbox adds per-account delivery tracking.
 crm_notice('billing:'.$key,$entity,$id,$title);
}
function bill_bridge_events():int{
 $count=0;
 foreach(crm_query("SELECT l.id FROM nd_leads l WHERE NOT EXISTS (SELECT 1 FROM nd_notification_outbox n WHERE n.event_key=CONCAT('lead:',l.id)) ORDER BY l.id LIMIT 100")->fetchAll() as $r){crm_atomic(fn()=>bill_emit('lead:'.$r['id'],'new_request','leads',(int)$r['id'],null));$count++;}
 foreach(crm_query("SELECT * FROM nd_invoices WHERE state='issued' AND due_on<UTC_DATE() ORDER BY id")->fetchAll() as $i)if(bill_balance($i)['outstanding_minor']>0){crm_atomic(fn()=>bill_emit('invoice:'.$i['id'].':overdue','payment_overdue','invoices',(int)$i['id'],(int)$i['customer_id']));$count++;}
 foreach(crm_query("SELECT id,due_at FROM nd_tasks WHERE archived_at IS NULL AND status NOT IN ('done','cancelled') AND due_at<=DATE_ADD(UTC_TIMESTAMP(),INTERVAL 1 DAY) ORDER BY id")->fetchAll() as $t){$over=$t['due_at']<gmdate('Y-m-d H:i:s');crm_atomic(fn()=>bill_emit('task:'.$t['id'].':'.$t['due_at'].':'.($over?'overdue':'soon'),$over?'task_overdue':'task_soon','tasks',(int)$t['id'],null));$count++;}
 return $count;
}
function bill_email_message(array $n,string $recipient):string{
 $title=bill_templates()[$n['template']]??'Уведомление НейроДело';$text=$title."\r\n\r\nПодробности доступны после входа в кабинет НейроДело.\r\n";
 $lifecycle=str_starts_with($n['event_key'],'lc-');$page=$lifecycle?($n['entity']==='invoices'?'finance.php':'orders.php'):'billing.php';$url=rtrim(config()['app_url'],'/').'/'.$page.($n['recipient_type']==='owner'?'?mode=owner':'').($lifecycle?'#'.(int)$n['record_id']:'#notifications');
 $text.=$url."\r\n\r\nЭто уведомление о работе сервиса, не рекламная рассылка.\r\n";$esc=fn($s)=>htmlspecialchars($s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');
 $html='<!doctype html><html lang="ru"><body><main><h1>НейроДело</h1><h2>'.$esc($title).'</h2><p>Подробности доступны после входа в кабинет.</p><p><a href="'.$esc($url).'">Открыть кабинет</a></p><p>Это уведомление о работе сервиса, не рекламная рассылка.</p></main></body></html>';
 $boundary='nd_'.bin2hex(random_bytes(16));$from=config()['customer_mail']['from']??'';
 return 'From: '.$from."\r\nTo: ".$recipient."\r\nSubject: =?UTF-8?B?".base64_encode($title)."?=\r\nMessage-ID: <nd-notice-".$n['id']."@neurodelo.pro>\r\nMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=\"".$boundary."\"\r\n\r\n--".$boundary."\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($text)).'--'.$boundary."\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($html)).'--'.$boundary."--\r\n";
}
function bill_deliver_one():bool{
 crm_query("UPDATE nd_notification_outbox SET state='failed',last_error='worker_interrupted' WHERE state='processing' AND lease_until<UTC_TIMESTAMP() AND attempts>=5");
 $n=crm_atomic(function(){
  // Bounded lease recovers interrupted workers; no SKIP LOCKED (MySQL 5.7).
  $r=crm_query("SELECT * FROM nd_notification_outbox WHERE channel='email' AND ((state='pending' AND next_attempt<=UTC_TIMESTAMP()) OR (state='processing' AND lease_until<UTC_TIMESTAMP())) AND attempts<5 ORDER BY id LIMIT 1 FOR UPDATE")->fetch();if(!$r)return null;
  $token=bin2hex(random_bytes(32));crm_query("UPDATE nd_notification_outbox SET state='processing',attempts=attempts+1,lease_until=DATE_ADD(UTC_TIMESTAMP(),INTERVAL 120 SECOND),lease_token=? WHERE id=?",[$token,$r['id']]);$r['lease_token']=$token;$r['attempts']++;return $r;
 });if(!$n)return false;
 $ok=false;$category='transport_unavailable';$state=null;
 if((config()['billing_email_enabled']??false)!==true){$state='disabled';$category='email_disabled';}
 else{
  $recipient=config()['billing_owner_email']??'';
  if($n['recipient_type']==='customer'){
   require_once dirname(__DIR__).'/customer-auth.php';$account=ca_account((int)$n['recipient_id']);
   if(!$account||!ca_account_allowed($account)||!ca_current_consent($account)){$state='skipped';$category='recipient_unavailable';}
   else{$recipient=$account['email'];if(!$n['essential']&&!crm_query('SELECT optional_email FROM nd_notification_preferences WHERE account_id=?',[$n['recipient_id']])->fetchColumn()){$state='skipped';$category='preference_disabled';}}
  }
  if(!$state){require_once dirname(__DIR__).'/customer-mail.php';if(is_string($recipient)&&filter_var($recipient,FILTER_VALIDATE_EMAIL))$ok=customer_smtp_send($recipient,bill_email_message($n,$recipient));else $category='recipient_unavailable';}
 }
 $state??=$ok?'delivered':((int)$n['attempts']>=5?'failed':'pending');$delay=min(3600,60*(2**((int)$n['attempts']-1)));
 crm_query('UPDATE nd_notification_outbox SET state=?,last_error=?,delivered_at=?,next_attempt=DATE_ADD(UTC_TIMESTAMP(),INTERVAL '.$delay.' SECOND),lease_until=NULL,lease_token=NULL WHERE id=? AND lease_token=?',[$state,$ok?null:$category,$ok?gmdate('Y-m-d H:i:s'):null,$n['id'],$n['lease_token']]);
 return true;
}
