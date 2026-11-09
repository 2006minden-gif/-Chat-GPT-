<?php
declare(strict_types=1);
function bill_lines(array $d):array{
 $lines=$d['lines']??null;if(!is_array($lines)||!array_is_list($lines)||!count($lines)||count($lines)>50)crm_fail(422,'Добавьте от 1 до 50 позиций.');$out=[];$total=0;
 foreach($lines as $l){if(!is_array($l))crm_fail(422,'Проверьте позиции счёта.');$name=bill_text($l,'description');$q=bill_minor($l['quantity']??null,3);$p=bill_minor($l['unit_price']??null);if($q<1||$q>1000000||$p<1)crm_fail(422,'Количество: до 1000, цена должна быть положительной.');$n=intdiv($q*$p+500,1000);if($n<1)crm_fail(422,'Сумма позиции слишком мала.');$total+=$n;if($total>9999999999)crm_fail(422,'Превышен допустимый размер счёта.');$out[]=['description'=>$name,'quantity_milli'=>$q,'unit_minor'=>$p,'total_minor'=>$n];}
 return [$out,$total];
}
function bill_save(array $a,int $id,array $d):array{
 cc_owner($a);return bill_mutation($a,'save:'.$id,$d,function()use($a,$id,$d){
  $old=$id?bill_invoice($a,$id,true):null;if($old){crm_version($d,$old);if($old['state']!=='draft')crm_fail(409,'Выставленный счёт неизменяем. Создайте корректировку.');}
  $oid=$old?(int)$old['order_id']:cc_id($d['order_id']??null);$order=crm_record('orders',$oid,true);$cid=cc_id($d['customer_id']??($old?(int)$old['customer_id']:null));
  if($cid!==(int)$order['customer_id']||$order['archived_at']!==null||$order['status']==='cancelled'||crm_record('customers',$cid,true)['status']!=='active')crm_fail(422,'Заказ недоступен или принадлежит другому клиенту.');
  if(($d['currency']??'RUB')!=='RUB'||$order['currency']!=='RUB')crm_fail(422,'Поддерживается только RUB, точность — две цифры.');
  $due=bill_text($d,'due_on',10);$dt=DateTimeImmutable::createFromFormat('!Y-m-d',$due,new DateTimeZone('UTC'));if(!$dt||$dt->format('Y-m-d')!==$due)crm_fail(422,'Укажите существующую дату оплаты.');
  [$lines,$total]=bill_lines($d);if($old){crm_query('UPDATE nd_invoices SET total_minor=?,due_on=?,version=version+1 WHERE id=?',[$total,$due,$id]);crm_query('DELETE FROM nd_invoice_lines WHERE invoice_id=?',[$id]);}
  else{$replacement=$d['replaces_id']??null;if($replacement!==null){$prior=bill_invoice($a,cc_id($replacement),true);if($prior['state']!=='cancelled'||(int)$prior['order_id']!==$oid)crm_fail(422,'Замена возможна только для отменённого счёта того же заказа.');}crm_query('INSERT INTO nd_invoices(customer_id,order_id,total_minor,due_on,replaces_id) VALUES (?,?,?,?,?)',[$cid,$oid,$total,$due,$replacement]);$id=(int)db()->lastInsertId();}
  foreach($lines as $n=>$l)crm_query('INSERT INTO nd_invoice_lines(invoice_id,position,description,quantity_milli,unit_minor,total_minor) VALUES (?,?,?,?,?,?)',[$id,$n,...array_values($l)]);
  $i=bill_invoice($a,$id);bill_audit($a,$i,'draft_saved');return ['ok'=>true,'id'=>$id,'record'=>bill_public($a,$i)];
 });
}
function bill_merchant():array{
 $m=config()['billing_merchant']??[];if(($m['approved']??false)!==true)crm_fail(503,'Реквизиты и условия выставления счетов ещё не одобрены владельцем.');
 $out=[];foreach(['legal_name','registration','address','tax_treatment','payment_instructions','retention_policy'] as $f)$out[$f]=bill_text($m,$f,2000);
 $prefix=$m['number_prefix']??'ND';if(!is_string($prefix)||!preg_match('/^[A-Z0-9-]{1,12}$/D',$prefix))crm_fail(503,'Проверьте формат нумерации.');$out['number_prefix']=$prefix;return $out;
}
function bill_action(array $a,int $id,string $action,array $d):array{
 cc_owner($a);return bill_mutation($a,$action.':'.$id,$d,function()use($a,$id,$action,$d){$i=bill_invoice($a,$id,true);crm_version($d,$i);if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите финансовое действие.');
  if($action==='issue'){
   if($i['state']!=='draft')crm_fail(409,'Счёт уже выставлен или отменён.');$merchant=bill_merchant();$customer=crm_record('customers',(int)$i['customer_id'],true);$order=crm_record('orders',(int)$i['order_id'],true);if($customer['status']!=='active'||$order['archived_at']!==null||$order['status']==='cancelled')crm_fail(409,'Клиент или заказ недоступен.');
   // Serialize all invoice issues for the order; do not invoice beyond agreed order value.
   $other=crm_query("SELECT * FROM nd_invoices WHERE order_id=? AND state='issued' FOR UPDATE",[$i['order_id']])->fetchAll();$committed=0;foreach($other as $v)$committed+=(int)$v['total_minor']-bill_balance($v)['credited_minor'];
   if($committed+(int)$i['total_minor']>bill_minor($order['total_amount']))crm_fail(422,'Сумма счетов превышает согласованную сумму заказа.');
   $year=(int)gmdate('Y');crm_query('INSERT INTO nd_billing_sequences(year,last_number) VALUES (?,0) ON DUPLICATE KEY UPDATE year=VALUES(year)',[$year]);$n=(int)crm_query('SELECT last_number FROM nd_billing_sequences WHERE year=? FOR UPDATE',[$year])->fetchColumn()+1;crm_query('UPDATE nd_billing_sequences SET last_number=? WHERE year=?',[$n,$year]);$number=$merchant['number_prefix'].'-'.$year.'-'.str_pad((string)$n,6,'0',STR_PAD_LEFT);
   $lines=crm_query('SELECT description,quantity_milli,unit_minor,total_minor FROM nd_invoice_lines WHERE invoice_id=? ORDER BY position',[$id])->fetchAll();$snapshot=json_encode(['number'=>$number,'issued_at'=>gmdate('Y-m-d H:i:s'),'due_on'=>$i['due_on'],'merchant'=>$merchant,'customer'=>['name'=>$customer['name'],'kind'=>$customer['kind']],'order'=>['id'=>$order['id'],'number'=>$order['number'],'title'=>$order['title']],'currency'=>$i['currency'],'total_minor'=>$i['total_minor'],'lines'=>$lines],JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
   crm_query("UPDATE nd_invoices SET state='issued',number=?,snapshot=?,snapshot_hash=?,issued_at=UTC_TIMESTAMP(),sent_at=UTC_TIMESTAMP(),version=version+1 WHERE id=?",[$number,$snapshot,hash('sha256',$snapshot),$id]);bill_emit('invoice:'.$id.':issued','invoice_issued','invoices',$id,(int)$i['customer_id']);
  }elseif($action==='cancel'){
   if($i['state']==='cancelled')crm_fail(409,'Счёт уже отменён.');$b=bill_balance($i);if($b['paid_minor']>0||crm_query("SELECT 1 FROM nd_payment_attempts WHERE invoice_id=? AND state IN ('creating','pending')",[$id])->fetchColumn())crm_fail(409,'Нельзя отменить счёт с платежами или незавершённой оплатой.');crm_query("UPDATE nd_invoices SET state='cancelled',version=version+1 WHERE id=?",[$id]);
  }elseif($action==='send'){
   if($i['state']!=='issued')crm_fail(409,'Сначала выставьте счёт.');crm_query('UPDATE nd_invoices SET sent_at=COALESCE(sent_at,UTC_TIMESTAMP()),version=version+1 WHERE id=?',[$id]);bill_emit('invoice:'.$id.':issued','invoice_issued','invoices',$id,(int)$i['customer_id']);
  }elseif($action==='adjust'){
   if($i['state']!=='issued')crm_fail(409,'Корректируется только выставленный счёт.');$amount=bill_minor($d['amount']??null);$reason=bill_text($d,'reason');$b=bill_balance($i);
   if($amount<1||$amount>$b['outstanding_minor']||crm_query("SELECT 1 FROM nd_payment_attempts WHERE invoice_id=? AND state IN ('creating','pending')",[$id])->fetchColumn())crm_fail(409,'Корректировка не может превышать долг или менять счёт во время оплаты.');
   crm_query('INSERT INTO nd_invoice_adjustments(invoice_id,amount_minor,reason,request_key) VALUES (?,?,?,?)',[$id,$amount,$reason,bill_key($d)]);crm_query('UPDATE nd_invoices SET version=version+1 WHERE id=?',[$id]);bill_emit('adjust:'.db()->lastInsertId(),'invoice_adjusted','invoices',$id,(int)$i['customer_id']);
  }else crm_fail(404,'Действие не найдено.');
  bill_audit($a,$i,$action);return ['ok'=>true,'id'=>$id,'record'=>bill_public($a,bill_invoice($a,$id))];
 });
}
