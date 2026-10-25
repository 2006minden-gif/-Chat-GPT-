<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/catalog/bindings.php';
function prod_gate():void{
 ai_gate();if((config()['client_collaboration_enabled']??false)!==true||(config()['production_enabled']??false)!==true||crm_query("SELECT state FROM nd_schema_migrations WHERE version='011_ai_production'")->fetchColumn()!=='applied')crm_fail(503,'ИИ-производство пока отключено или не установлено.');
}
function prod_stage9_evidence(int $order,int $spec,int $quote):array{
 require_once dirname(__DIR__).'/catalog/bindings.php';$actual=cat_stage9_evidence($order,$spec,$quote);if($actual!==null)return $actual;
 $c=config();$proof=$c['production_test_acceptances'][(string)$order]??null;
 if(($c['production_test_mode']??false)===true&&in_array(parse_url($c['app_url'],PHP_URL_HOST),['127.0.0.1','localhost','::1'],true)&&is_array($proof)&&($proof['spec_revision_id']??null)===$spec&&($proof['quotation_id']??null)===$quote&&in_array($proof['service_type']??'',prod_services(),true))return ['adapter'=>'stage9_mock_only','accepted'=>true,'spec_revision_id'=>$spec,'quotation_id'=>$quote,'service_type'=>$proof['service_type'],'evidence_hash'=>hash('sha256',ai_json($proof))];
 crm_fail(409,'STAGE9_ACCEPTANCE_UNAVAILABLE: нет проверенного источника принятой клиентом оферты.');
}
function prod_source(int $project,int $spec,bool $lock=false):array{
 $owner=['type'=>'owner','id'=>1];$p=cc_project($owner,$project,true,$lock);if(!$p['order_id'])crm_fail(409,'Проект не связан с подтверждённым заказом.');$o=crm_record('orders',(int)$p['order_id'],$lock);if(!in_array($o['status'],['confirmed','in_progress'],true)||$o['archived_at']!==null||(int)$o['customer_id']!==(int)$p['customer_id'])crm_fail(409,'Заказ не подтверждён, отменён или недоступен.');
 $r=cc_revision($owner,$spec,$lock);if((int)$r['document']['project_id']!==$project||$r['document']['kind']!=='specification'||!in_array($r['status'],['approved','finalized'],true)||($r['decision']['decision']??'')!=='approved'||(int)$r['revision_number']!==(int)$r['document']['head_revision'])crm_fail(409,'Требуется точная текущая редакция принятого клиентом ТЗ.');
 $q=pricing_require_approved($project);if(bill_minor($o['total_amount'])!==(int)$q['calculation']['selling_minor'])crm_fail(409,'NEEDS_COST_REVIEW: цена заказа не совпадает с одобренной офертой.');$upstream=prod_stage9_evidence((int)$o['id'],$spec,(int)$q['id']);$rates=[];
 foreach($q['calculation']['rates'] as $category=>$rate){$scope=crm_query('SELECT * FROM nd_prod_rate_scopes WHERE rate_id=? AND service_type=? ORDER BY id DESC LIMIT 1'.($lock?' FOR UPDATE':''),[$rate['id'],$upstream['service_type']])->fetch();if(!$scope||!$scope['active'])crm_fail(409,'NEEDS_COST_REVIEW: применимость или проверка ставки для услуги не подтверждена.');$rates[$category]=['rate_id'=>(int)$rate['id'],'scope_id'=>(int)$scope['id'],'unit'=>$category,'verified_at'=>$scope['verified_at']];}
 $lines=array_values(array_filter(array_map('trim',preg_split('/\R/u',$r['fields']['acceptance']??''))));if(!count($lines)||count($lines)>20)crm_fail(409,'В ТЗ нужны 1–20 отдельных критериев приёмки.');$requirements=[];foreach($lines as $i=>$line)$requirements['R'.($i+1)]=$line;
 return ['project_id'=>$project,'customer_id'=>(int)$p['customer_id'],'order_id'=>(int)$o['id'],'project_version'=>(int)$p['version'],'order_version'=>(int)$o['version'],'spec_revision_id'=>$spec,'spec_checksum'=>$r['checksum'],'quotation_id'=>(int)$q['id'],'quotation_hash'=>$q['checksum'],'service_type'=>$upstream['service_type'],'upstream'=>$upstream,'rates'=>$rates,'requirements'=>$requirements];
}
function prod_plan(int $id,bool $lock=false):array{$p=crm_query('SELECT * FROM nd_prod_plans WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$p)crm_fail(404,'Запись не найдена.');return $p;}
function prod_run(int $id,bool $lock=false):array{$r=crm_query('SELECT * FROM nd_prod_runs WHERE id=?'.($lock?' FOR UPDATE':''),[$id])->fetch();if(!$r)crm_fail(404,'Запись не найдена.');return $r;}
function prod_current_source(array $plan,bool $lock=false):array{
 $s=prod_source((int)$plan['project_id'],(int)$plan['spec_revision_id'],$lock);if(!hash_equals($plan['source_hash'],hash('sha256',ai_json($s))))crm_fail(409,'Исходные условия, цена или ТЗ изменились. Нужен новый план и согласование.');
 $latest=(int)crm_query('SELECT id FROM nd_prod_plans WHERE project_id=? ORDER BY revision_number DESC LIMIT 1'.($lock?' FOR UPDATE':''),[$plan['project_id']])->fetchColumn();if($latest!==(int)$plan['id'])crm_fail(409,'Этот план заменён новой редакцией.');return $s;
}
function prod_event(int $plan,?int $run,string $category):void{crm_query('INSERT INTO nd_prod_events(plan_id,run_id,category) VALUES (?,?,?)',[$plan,$run,$category]);}
function prod_issue(array $run,string $category):void{
 crm_query("UPDATE nd_prod_runs SET state='NEEDS_HUMAN',last_error=?,version=version+1 WHERE id=?",[$category,$run['id']]);$p=prod_plan((int)$run['plan_id']);prod_event((int)$p['id'],(int)$run['id'],$category);crm_notice('production:'.$run['id'].':'.$category,'projects',(int)$p['project_id'],'ИИ-производство требует решения владельца. Успешные черновики сохранены.');
}
function prod_run_state(array $r,string $to,string $event):void{
 $map=['EXECUTING'=>['PAUSED','NEEDS_HUMAN','QA_REJECTED','READY','CANCELLED'],'PAUSED'=>['EXECUTING','CANCELLED','NEEDS_HUMAN'],'QA_REJECTED'=>['EXECUTING','NEEDS_HUMAN','PAUSED'],'READY'=>['DELIVERED','EXECUTING','PAUSED','NEEDS_HUMAN'],'DELIVERED'=>['COMPLETED','NEEDS_HUMAN'],'NEEDS_HUMAN'=>['EXECUTING','PAUSED','CANCELLED'],'CANCELLED'=>[],'COMPLETED'=>[]];
 if(!in_array($to,$map[$r['state']]??[],true))crm_fail(409,'Этот переход производства недоступен.');crm_query('UPDATE nd_prod_runs SET state=?,version=version+1 WHERE id=?',[$to,$r['id']]);prod_event((int)$r['plan_id'],(int)$r['id'],$event);
}
