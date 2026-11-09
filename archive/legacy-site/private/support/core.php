<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/crm/core.php';
function sa_installed():bool{return (bool)crm_query("SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='nd_order_access_policies'")->fetchColumn()&&crm_query("SELECT state FROM nd_schema_migrations WHERE version='022_support_archive'")->fetchColumn()==='applied';}
function sa_today():string{return (new DateTimeImmutable('now',new DateTimeZone('Europe/Kaliningrad')))->format('Y-m-d');}
function sa_state(int $order):array{
 if(!sa_installed())return ['state'=>'UNCONFIGURED','archive_available'=>true];
 $p=crm_query('SELECT * FROM nd_order_access_policies WHERE order_id=?',[$order])->fetch();if(!$p)return ['state'=>'UNCONFIGURED','archive_available'=>true,'reason'=>'Срок доступа ещё не проверен владельцем.'];
 $f=crm_query('SELECT * FROM nd_lc_order_flow WHERE order_id=?',[$order])->fetch();$held=[];
 if(!$f||$f['delivery_state']!=='HANDED_OVER')$held[]='Передача не завершена.';
 if($f&&in_array($f['case_state'],['PAUSED','DISPUTED'],true))$held[]='Есть пауза или спор.';
 if($f&&((int)$f['agreement_binding_id']!==(int)$p['agreement_id']||$f['support_end']!==$p['expires_on']||!hash_equals($p['terms_hash'],hash('sha256',$f['support_terms']??''))))$held[]='Условия изменились; нужен повторный просмотр.';
 if(crm_query("SELECT r.id FROM nd_lc_feedback r JOIN nd_lc_milestone_versions v ON v.id=r.milestone_version_id WHERE v.order_id=? AND r.state='OPEN' LIMIT 1",[$order])->fetchColumn())$held[]='Есть нерешённые замечания.';
 if(crm_query("SELECT id FROM nd_lc_obligations WHERE order_id=? AND required=1 AND state NOT IN ('VERIFIED','NOT_APPLICABLE') LIMIT 1",[$order])->fetchColumn())$held[]='Обязательные пункты передачи не проверены.';
 $days=(int)(new DateTimeImmutable(sa_today()))->diff(new DateTimeImmutable($p['expires_on']))->format('%r%a');
 return ['state'=>$held?'HELD':($days<0?'EXPIRED':($days<=(int)$p['warning_days']?'EXPIRING':'ACTIVE')),'expires_on'=>$p['expires_on'],'days_remaining'=>$days,'holds'=>$held,'archive_available'=>true,'policy'=>$p];
}
function sa_assert(int $order):void{if(sa_state($order)['state']==='EXPIRED')crm_fail(403,'Срок рабочего доступа к этому заказу завершён. Документы доступны в приватном архиве. Другие заказы не затронуты.');}
function sa_save(array $a,array $d):array{
 cc_owner($a);$order=cc_id($d['order_id']??null);$f=lc_flow($a,$order,true);$old=crm_query('SELECT * FROM nd_order_access_policies WHERE order_id=? FOR UPDATE',[$order])->fetch();if($old)crm_version($d,$old);
 if(($d['confirm']??false)!==true||($d['access_expiry_agreed']??false)!==true)crm_fail(422,'Подтвердите, что подписанные условия прямо ограничивают рабочий доступ этой датой.');$reason=cc_text($d,'reason',4000);$b=$f['agreement_binding_id']?lc_binding($a,(int)$f['agreement_binding_id']):null;$in=$b?json_decode($b['input_snapshot'],true):null;
 if(!$b||$b['state']!=='AGREED'||!$f['support_start']||!$f['support_end']||($in['fields']['support_terms']??null)!==$f['support_terms'])crm_fail(409,'Сначала проверьте подписанный договор и зафиксируйте точные условия/даты поддержки.');
 $warning=$d['warning_days']??null;if(!is_int($warning)||$warning<0||$warning>30)crm_fail(422,'Период предупреждения: 0–30 дней.');
 if(($d['agreed_expiry_clause']??'')!==$f['support_terms'])crm_fail(409,'Укажите точную согласованную оговорку о сроке доступа и подтвердите её применимость.');
 crm_query('INSERT INTO nd_order_access_policies(order_id,agreement_id,terms_hash,expires_on,warning_days,reason) VALUES (?,?,?,?,?,?) ON DUPLICATE KEY UPDATE agreement_id=VALUES(agreement_id),terms_hash=VALUES(terms_hash),expires_on=VALUES(expires_on),warning_days=VALUES(warning_days),reason=VALUES(reason),version=version+1,reviewed_at=UTC_TIMESTAMP()',[$order,$b['id'],hash('sha256',$f['support_terms']),$f['support_end'],$warning,$reason]);lc_audit($a,'order',$order,'access_expiry_reviewed',(int)$f['version'],['expires_on'=>$f['support_end'],'reason'=>$reason]);return ['ok'=>true,'access'=>sa_state($order)];
}
function sa_retention(array $a,array $d):array{
 cc_owner($a);$order=cc_id($d['order_id']??null);lc_flow($a,$order,true);$p=crm_query('SELECT * FROM nd_order_access_policies WHERE order_id=? FOR UPDATE',[$order])->fetch();if(!$p)crm_fail(409,'Сначала проверьте условия поддержки/доступа.');crm_version($d,$p);if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите отдельное решение по хранению.');$policy=['category'=>cc_text($d,'category',190),'basis'=>cc_text($d,'basis',4000),'review_on'=>pricing_date($d,'review_on'),'hold_reason'=>cc_text($d,'hold_reason',4000,false),'action'=>'REVIEW_ONLY','reviewed_at'=>gmdate('c')];
 crm_query('UPDATE nd_order_access_policies SET retention_json=?,version=version+1 WHERE order_id=?',[json_encode($policy,JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR),$order]);lc_audit($a,'order',$order,'archive_retention_reviewed',null,$policy);return ['ok'=>true,'retention'=>$policy,'automatic_deletion'=>false];
}
function sa_pump():int{
 if(!sa_installed())return 0;$rows=crm_query('SELECT order_id FROM nd_order_access_policies ORDER BY order_id')->fetchAll(PDO::FETCH_COLUMN);$n=0;
 foreach($rows as $order){$s=sa_state((int)$order);if(in_array($s['state'],['EXPIRING','EXPIRED','HELD'],true)){$o=crm_record('orders',(int)$order);bill_emit('support:'.$order.':'.$s['expires_on'].':'.$s['state'],match($s['state']){'EXPIRING'=>'support_expiring','EXPIRED'=>'support_expired',default=>'support_hold'},'orders',(int)$order,(int)$o['customer_id']);$n++;}$p=isset($s['policy']['retention_json'])?json_decode($s['policy']['retention_json'],true):null;if($p&&$p['review_on']<=sa_today())crm_notice('retention:'.$order.':'.$p['review_on'],'orders',(int)$order,'Наступил срок проверки хранения архива. Автоматическое удаление не выполняется.');}return $n;
}
