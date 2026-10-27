<?php
declare(strict_types=1);
function bill_filters(array $a):array{
 $where=['1=1'];$p=[];if($a['type']==='customer'){$where[]="i.customer_id=? AND i.state<>'draft' AND i.sent_at IS NOT NULL";$p[]=$a['customer_id'];}
 foreach(['customer_id','order_id'] as $f)if(isset($_GET[$f])&&$_GET[$f]!==''){if(!is_string($_GET[$f])||!preg_match('/^[1-9][0-9]*$/D',$_GET[$f])||(int)$_GET[$f]>2147483647)crm_fail(422,'Проверьте фильтр.');$where[]='i.'.$f.'=?';$p[]=(int)$_GET[$f];}
 foreach(['from'=>'>=','to'=>'<='] as $f=>$op)if(isset($_GET[$f])&&$_GET[$f]!==''){$date=$_GET[$f];if(!is_string($date)||!preg_match('/^\d{4}-\d{2}-\d{2}$/D',$date))crm_fail(422,'Проверьте даты фильтра.');$dt=DateTimeImmutable::createFromFormat('!Y-m-d',$date,new DateTimeZone('UTC'));if(!$dt||$dt->format('Y-m-d')!==$date)crm_fail(422,'Укажите существующие даты фильтра.');$where[]='DATE(i.issued_at)'.$op.'?';$p[]=$date;}
 if(isset($_GET['currency'])&&$_GET['currency']!==''&&$_GET['currency']!=='RUB')crm_fail(422,'Поддерживается валюта RUB.');
 if(isset($_GET['service'])&&$_GET['service']!==''){$service=cc_text($_GET,'service',190);$where[]='o.title LIKE ?';$p[]='%'.$service.'%';}
 return [implode(' AND ',$where),$p];
}
function bill_list(array $a,bool $all=false):array{
 [$where,$p]=bill_filters($a);$page=cc_page();$rows=crm_query('SELECT i.*,c.name AS customer_name,o.title AS order_title,o.number AS order_number FROM nd_invoices i JOIN nd_customers c ON c.id=i.customer_id JOIN nd_orders o ON o.id=i.order_id WHERE '.$where.' ORDER BY i.id DESC'.' LIMIT 5001',$p)->fetchAll();
 if(count($rows)>5000)crm_fail(422,'Слишком большой отчёт. Уточните период или клиента.');
 foreach($rows as &$r){unset($r['snapshot']);$r['balance']=bill_balance($r);}unset($r);
 $status=$_GET['status']??'';if($status!==''){if(!in_array($status,['draft','issued','paid','partial','overdue','cancelled','refunded'],true))crm_fail(422,'Проверьте статус фильтра.');$rows=array_values(array_filter($rows,fn($r)=>$r['balance']['status']===$status));}
 if(!$all)$rows=array_slice($rows,($page-1)*25,25);
 return ['ok'=>true,'items'=>$rows,'page'=>$page,'page_size'=>25];
}
function bill_report(array $a):array{
 cc_owner($a);$items=bill_list($a,true)['items'];$total=['invoiced_minor'=>0,'confirmed_minor'=>0,'outstanding_minor'=>0,'refunded_minor'=>0,'net_received_minor'=>0,'overdue_minor'=>0];$months=[];$services=[];
 foreach($items as $i){if($i['state']!=='issued')continue;$b=$i['balance'];$total['invoiced_minor']+=(int)$i['total_minor']-$b['credited_minor'];$total['confirmed_minor']+=$b['paid_minor'];$total['outstanding_minor']+=$b['outstanding_minor'];$total['refunded_minor']+=$b['refunded_minor'];$total['net_received_minor']+=$b['net_minor'];if($b['overdue'])$total['overdue_minor']+=$b['outstanding_minor'];
  foreach(crm_query('SELECT t.amount_minor,t.settled_at FROM nd_payment_transactions t JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?',[$i['id']])->fetchAll() as $t){$month=substr($t['settled_at'],0,7);$months[$month]=($months[$month]??0)+(int)$t['amount_minor'];}
  $service=$i['order_title'];$services[$service]=($services[$service]??0)+$b['net_minor'];
 }
 ksort($months);return ['ok'=>true,'currency'=>'RUB','totals'=>$total,'by_month'=>$months,'by_service'=>$services,'items'=>$items,'meaning'=>'Поступления и возвраты по выбранным счетам; это не бухгалтерски признанная выручка. Фильтр периода относится к дате счёта.'];
}
function bill_notifications(array $a):array{
 $owner=$a['type']==='owner';$where=$owner?"recipient_type='owner' AND recipient_id=1":"recipient_type='customer' AND recipient_id=? AND channel='in_app'";
 $p=$owner?[]:[$a['id']];$rows=crm_query('SELECT id,channel,template,title,entity,record_id,state,attempts,last_error,read_at,created_at FROM nd_notification_outbox WHERE '.$where.' ORDER BY id DESC LIMIT 25 OFFSET '.((cc_page()-1)*25),$p)->fetchAll();return ['ok'=>true,'items'=>$rows,'page'=>cc_page(),'page_size'=>25,'email_enabled'=>(config()['billing_email_enabled']??false)===true,'scheduler_verified'=>false];
}
function bill_csv(array $a):never{
 cc_owner($a);$report=bill_report($a);header('Content-Type: text/csv; charset=UTF-8');header('Content-Disposition: attachment; filename="neurodelo-finances.csv"');$f=fopen('php://output','w');fwrite($f,"\xEF\xBB\xBF");
 $safe=fn($v)=>preg_match('/^[\s]*[=+@\-\t\r\n]/u',(string)$v)?"'".$v:(string)$v;
 fputcsv($f,['Счёт','Клиент','Заказ','Валюта','Выставлено','Поступило','Возвраты','Долг'],',','"','');foreach($report['items'] as $i)fputcsv($f,array_map($safe,[$i['number']??'Черновик',$i['customer_name'],$i['order_title'],$i['currency'],bill_decimal((int)$i['total_minor']),bill_decimal($i['balance']['paid_minor']),bill_decimal($i['balance']['refunded_minor']),bill_decimal($i['balance']['outstanding_minor'])]),',','"','');fclose($f);exit;
}
