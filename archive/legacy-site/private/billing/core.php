<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/collab/core.php';
function bill_gate():void{
 crm_gate();if((config()['billing_enabled']??false)!==true)crm_fail(503,'Финансы пока отключены владельцем.');
 if(crm_query("SELECT state FROM nd_schema_migrations WHERE version='008_billing_notifications'")->fetchColumn()!=='applied')crm_fail(503,'Финансы ещё не настроены.');
}
function bill_actor(bool $customer,bool $write=false):array{
 if($customer){require_once dirname(__DIR__).'/customer-auth.php';ca_gate();$s=ca_session($write);$a=ca_account((int)($s['account_id']??0));if(!ca_account_allowed($a)||!ca_current_consent($a))crm_fail(401,'Войдите и подтвердите актуальные документы.');$actor=['type'=>'customer','id'=>(int)$a['id'],'customer_id'=>(int)$a['customer_id']];}
 else{current_session($write);$actor=['type'=>'owner','id'=>1];}bill_gate();return $actor;
}
function bill_minor(mixed $v,int $precision=2):int{
 if(!is_string($v)||!preg_match('/^(0|[1-9][0-9]{0,7})(?:\.([0-9]{1,'.$precision.'}))?$/D',$v,$m))crm_fail(422,'Сумма или количество: используйте десятичное число с точкой без знака.');
 return (int)$m[1]*(10**$precision)+(int)str_pad($m[2]??'',$precision,'0');
}
function bill_decimal(int $minor):string{return intdiv($minor,100).'.'.str_pad((string)($minor%100),2,'0',STR_PAD_LEFT);}
function bill_text(array $d,string $key,int $max=500):string{return cc_text($d,$key,$max);}
function bill_key(array $d):string{$k=$d['request_key']??'';if(!is_string($k)||!preg_match('/^[a-f0-9]{64}$/D',$k))crm_fail(422,'Обновите форму перед отправкой.');return $k;}
function bill_invoice(array $a,int $id,bool $lock=false):array{
 $p=[$id];$sql='SELECT * FROM nd_invoices WHERE id=?';if($a['type']==='customer'){$sql.=" AND customer_id=? AND state<>'draft' AND sent_at IS NOT NULL";$p[]=$a['customer_id'];}
 if($lock){$visible=crm_query($sql,$p)->fetch();if(!$visible)crm_fail(404,'Запись не найдена.');crm_record('orders',(int)$visible['order_id'],true);}
 $r=crm_query($sql.($lock?' FOR UPDATE':''),$p)->fetch();if(!$r)crm_fail(404,'Запись не найдена.');return $r;
}
function bill_balance(array $i):array{
 $queries=[
  'paid'=>"SELECT t.amount_minor FROM nd_payment_transactions t JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?",
  'refund'=>"SELECT r.amount_minor FROM nd_refunds r JOIN nd_payment_attempts p ON p.id=r.attempt_id WHERE p.invoice_id=? AND r.state='succeeded'",
  'credits'=>"SELECT amount_minor FROM nd_invoice_adjustments WHERE invoice_id=?"
 ];
 if(db()->inTransaction()){
  // Locking reads see the winner of an order/invoice mutex even under REPEATABLE READ.
  $sums=[];foreach($queries as $key=>$sql){$rows=crm_query($sql.' FOR UPDATE',[$i['id']])->fetchAll();$sums[$key]=array_sum(array_map(fn($r)=>(int)$r['amount_minor'],$rows));}
 }else{
  // One consistent statement for public reads; never mix pre-payment and post-refund snapshots.
  $sums=crm_query("SELECT (SELECT COALESCE(SUM(t.amount_minor),0) FROM nd_payment_transactions t JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?) AS paid,(SELECT COALESCE(SUM(r.amount_minor),0) FROM nd_refunds r JOIN nd_payment_attempts p ON p.id=r.attempt_id WHERE p.invoice_id=? AND r.state='succeeded') AS refund,(SELECT COALESCE(SUM(amount_minor),0) FROM nd_invoice_adjustments WHERE invoice_id=?) AS credits",[$i['id'],$i['id'],$i['id']])->fetch();
 }
 $paid=(int)$sums['paid'];$refund=(int)$sums['refund'];$credits=(int)$sums['credits'];
 $net=$paid-$refund;$target=(int)$i['total_minor']-$credits;$balance=max(0,$target-$net);
 $status=$i['state'];if($status==='issued')$status=$refund>0&&$net===0?'refunded':($balance===0?'paid':($net>0?'partial':($i['due_on']<gmdate('Y-m-d')?'overdue':'issued')));
 return ['paid_minor'=>$paid,'refunded_minor'=>$refund,'credited_minor'=>$credits,'net_minor'=>$net,'outstanding_minor'=>$balance,'status'=>$status,'overdue'=>$i['state']==='issued'&&$balance>0&&$i['due_on']<gmdate('Y-m-d')];
}
function bill_public(array $a,array $i):array{
 $snapshot=$i['snapshot']?json_decode($i['snapshot'],true):null;$i['order_number']=$snapshot['order']['number']??crm_record('orders',(int)$i['order_id'])['number'];$i['customer_name']=$snapshot['customer']['name']??crm_record('customers',(int)$i['customer_id'])['name'];
 $i['balance']=bill_balance($i);$i['lines']=crm_query('SELECT description,quantity_milli,unit_minor,total_minor FROM nd_invoice_lines WHERE invoice_id=? ORDER BY position',[$i['id']])->fetchAll();
 $i['payments']=crm_query('SELECT id,amount_minor,currency,state,created_at,verified_at FROM nd_payment_attempts WHERE invoice_id=? ORDER BY id DESC',[$i['id']])->fetchAll();
 $i['refunds']=crm_query('SELECT r.id,r.attempt_id,r.amount_minor,r.reason,r.state,r.created_at,r.verified_at FROM nd_refunds r JOIN nd_payment_attempts p ON p.id=r.attempt_id WHERE p.invoice_id=? ORDER BY r.id DESC',[$i['id']])->fetchAll();
 $i['adjustments']=crm_query('SELECT id,amount_minor,reason,created_at FROM nd_invoice_adjustments WHERE invoice_id=?',[$i['id']])->fetchAll();
 $i['payment_available']=$i['state']==='issued'&&$i['balance']['outstanding_minor']>0&&$i['balance']['refunded_minor']===0&&bill_provider_ready();
 return $i;
}
function bill_mutation(array $a,string $route,array $d,callable $fn):array{return crm_idempotent('billing:'.$a['type'].':'.$a['id'].':'.$route,$d,$fn);}
function bill_audit(array $a,array $i,string $action):void{
 crm_query('INSERT INTO nd_activity_history(actor_admin_id,actor_customer_account_id,customer_id,order_id,action,summary) VALUES (?,?,?,?,?,?)',[$a['type']==='owner'?1:null,$a['type']==='customer'?$a['id']:null,$i['customer_id'],$i['order_id'],'billing_'.$action,'Изменение финансового документа']);
}
