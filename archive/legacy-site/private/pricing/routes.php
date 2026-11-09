<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/engine.php';
function pricing_date(array $d,string $field):string{$v=cc_text($d,$field,10);$dt=DateTimeImmutable::createFromFormat('!Y-m-d',$v,new DateTimeZone('UTC'));if(!$dt||$dt->format('Y-m-d')!==$v)crm_fail(422,'Укажите существующую дату ставки.');return $v;}
function pricing_dispatch(array $a,string $route,string $method):never{
 ai_owner($a);pricing_gate();
 if($method==='GET'){
  if($route==='insights')json_response(pricing_insights());
  if($route==='rates')json_response(['ok'=>true,'items'=>crm_query('SELECT * FROM nd_cost_rates ORDER BY id DESC LIMIT 100')->fetchAll(),'categories'=>pricing_categories(),'policy'=>crm_query('SELECT * FROM nd_pricing_policies ORDER BY id DESC LIMIT 1')->fetch()?:null]);
  if($route==='quotes')json_response(['ok'=>true,'items'=>crm_query('SELECT id,project_id,revision_number,state,checksum,created_at FROM nd_quotations ORDER BY id DESC LIMIT 50')->fetchAll()]);
  if(preg_match('~^quotes/([1-9][0-9]*)$~D',$route,$m)){$q=pricing_detail((int)$m[1]);$q['fresh']=pricing_fresh($q);$q['actuals']=crm_query('SELECT * FROM nd_project_actuals WHERE quotation_id=? ORDER BY id',[$q['id']])->fetchAll();json_response(['ok'=>true,'record'=>$q]);}
 }
 if($method==='POST'){
  $d=input();$result=crm_idempotent('pricing:'.$route,$d,function()use($a,$route,$d){
   if($route==='rates'){
    $cat=$d['category']??'';if(!is_string($cat)||!isset(pricing_categories()[$cat]))crm_fail(422,'Выберите категорию затрат.');$value=bill_minor($d['value']??null);if($cat==='payment_fee_percent'&&$value>5000||$cat!=='payment_fee_percent'&&$value>1000000000)crm_fail(422,'Ставка выходит за допустимые пределы.');if(!in_array($d['currency']??'', ['RUB','USD','EUR'],true))crm_fail(422,'Укажите валюту ставки RUB, USD или EUR.');$source=cc_text($d,'source',500);$date=pricing_date($d,'source_date');$from=pricing_date($d,'valid_from');$until=pricing_date($d,'valid_until');if($from>$until||$date>gmdate('Y-m-d'))crm_fail(422,'Проверьте срок действия и дату источника.');
    crm_query('INSERT INTO nd_cost_registry_keys(category) VALUES (?) ON DUPLICATE KEY UPDATE category=VALUES(category)',[$cat]);$n=(int)crm_query('SELECT revision_number FROM nd_cost_registry_keys WHERE category=? FOR UPDATE',[$cat])->fetchColumn()+1;crm_query('UPDATE nd_cost_registry_keys SET revision_number=? WHERE category=?',[$n,$cat]);crm_query('INSERT INTO nd_cost_rates(category,revision_number,value_scaled,currency,source,source_date,valid_from,valid_until) VALUES (?,?,?,?,?,?,?,?)',[$cat,$n,$value,$d['currency'],$source,$date,$from,$until]);return ['ok'=>true,'id'=>(int)db()->lastInsertId()];
   }
   if($route==='policy'){
    $bp=[];foreach(['contingency','margin','minimum','overhead','tax'] as $f){$bp[$f]=($d[$f]??null)===null?null:bill_minor($d[$f]);if($bp[$f]!==null&&$bp[$f]>9000)crm_fail(422,'Процент должен быть от 0 до 90.00.');}
    if(in_array(null,array_intersect_key($bp,array_flip(['contingency','margin','minimum','overhead'])),true))crm_fail(422,'Правила маржи, резерва и накладных обязательны.');$method=$d['tax_method']??'';if(!in_array($method,['unknown','none','included_percent'],true)||$method==='none'&&$bp['tax']!==0)crm_fail(422,'Отсутствие налога должно быть явно подтверждено нулевой ставкой.');if(($d['approved']??false)!==true)crm_fail(422,'Подтвердите проверку правил и налоговой трактовки.');
    $effort=isset($d['effort_factor'])?bill_minor($d['effort_factor']):10000;if($effort<1000||$effort>30000)crm_fail(422,'Поправка трудозатрат: от 10 до 300 процентов.');
    crm_query('INSERT INTO nd_pricing_policies(name,currency,contingency_bp,margin_bp,minimum_bp,overhead_bp,effort_factor_bp,tax_bp,tax_method,source,approved) VALUES (?,\'RUB\',?,?,?,?,?,?,?,?,1)',[cc_text($d,'name',190),$bp['contingency'],$bp['margin'],$bp['minimum'],$bp['overhead'],$effort,$bp['tax'],$method,cc_text($d,'source',500)]);return ['ok'=>true,'id'=>(int)db()->lastInsertId()];
   }
   if(preg_match('~^projects/([1-9][0-9]*)/estimate$~D',$route,$m)){$e=pricing_estimate((int)$m[1],pricing_packages($d['packages']??null),null,'owner');$q=pricing_quote($e);return ['ok'=>true,'id'=>(int)$q['id'],'record'=>$q];}
   if(preg_match('~^quotes/([1-9][0-9]*)/(recalculate|edit|approve|reject|actuals)$~D',$route,$m)){
    $q=pricing_detail((int)$m[1]);$p=cc_project(['type'=>'owner','id'=>1],(int)$q['project_id'],false,true);$q=pricing_detail((int)$m[1],true);if(!is_string($d['checksum']??null)||!hash_equals($q['checksum'],$d['checksum']))crm_fail(409,'Подтвердите точную редакцию расчёта.');
    if(in_array($m[2],['edit','recalculate'],true)){$e=crm_query('SELECT * FROM nd_project_estimates WHERE id=?',[$q['estimate_id']])->fetch();$next=pricing_quote($e,$m[2]==='edit'?cc_text($d,'price',20):null,(int)$q['id']);return ['ok'=>true,'id'=>(int)$next['id'],'record'=>$next];}
    if($m[2]==='actuals'){
     if($q['state']!=='APPROVED'||$p['status']!=='completed'||($d['confirm']??false)!==true)crm_fail(409,'Фактические затраты фиксируются владельцем после завершения проекта.');$cost=bill_minor($d['actual_cost']??null);$dev=bill_minor($d['development_hours']??null,3);$test=bill_minor($d['testing_hours']??null,3);if($dev>1000000000||$test>1000000000)crm_fail(422,'Фактические часы выходят за допустимый предел.');crm_query('INSERT INTO nd_project_actuals(quotation_id,owner_id,actual_cost_minor,development_milli,testing_milli,source) VALUES (?,1,?,?,?,?)',[$q['id'],$cost,$dev,$test,cc_text($d,'source',1000)]);return ['ok'=>true,'id'=>(int)db()->lastInsertId(),'estimated_cost_minor'=>$q['calculation']['cost_pool_minor'],'actual_cost_minor'=>$cost,'cost_delta_minor'=>$cost-(int)$q['calculation']['cost_pool_minor']-(int)$q['calculation']['tax_minor']-(int)$q['calculation']['payment_fee_minor'],'contribution_after_actual_minor'=>(int)$q['calculation']['selling_minor']-$cost];
    }
    if(($d['confirm']??false)!==true||!in_array($q['state'],['DRAFT','NEEDS_COST_REVIEW'],true))crm_fail(409,'Расчёт уже рассмотрен или не подтверждён.');$approve=$m[2]==='approve';if($approve&&($q['state']!=='DRAFT'||!pricing_fresh($q)||$q['calculation']['profitability']!=='ACCEPTABLE'))crm_fail(409,'NEEDS_COST_REVIEW: нужны полные действующие затраты и допустимая доходность.');
    if($approve&&$q['calculation']['warnings']&&($d['accept_estimates']??false)!==true)crm_fail(422,'Подтвердите понимание оценок и рисков.');$reason=cc_text($d,'reason',1000);$state=$approve?'APPROVED':'REJECTED';crm_query('INSERT INTO nd_pricing_decisions(quotation_id,owner_id,decision,quotation_hash,reason,accepted_estimates) VALUES (?,1,?,?,?,?)',[$q['id'],$state,$q['checksum'],$reason,($d['accept_estimates']??false)?1:0]);crm_query('UPDATE nd_quotations SET state=? WHERE id=?',[$state,$q['id']]);return ['ok'=>true,'id'=>(int)$q['id'],'state'=>$state];
   }
   crm_fail(404,'Раздел расчётов не найден.');
  });json_response($result);
 }crm_fail(404,'Раздел расчётов не найден.');
}
