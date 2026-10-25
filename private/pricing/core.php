<?php
declare(strict_types=1);
function pricing_gate():void{
 if((config()['ai_pricing_enabled']??false)!==true||crm_query("SELECT state FROM nd_schema_migrations WHERE version='010_project_pricing'")->fetchColumn()!=='applied')crm_fail(409,'NEEDS_COST_REVIEW: модуль расчёта цены ещё не подготовлен.');
}
function pricing_categories():array{return ['labor_hour'=>'Час работы владельца','ai_input_1000'=>'1000 входных токенов','ai_output_1000'=>'1000 выходных токенов','hosting_month'=>'Месяц инфраструктуры','tool_unit'=>'Единица платного инструмента','external_unit'=>'Единица внешней услуги','other_unit'=>'Прочие расходы на единицу','payment_fee_percent'=>'Комиссия оплаты, процент'];}
function pricing_scope(int $project,bool $lock=false):array{
 $p=cc_project(['type'=>'owner','id'=>1],$project,false,$lock);if($p['archived_at']!==null||$p['status']==='cancelled')crm_fail(409,'Проект закрыт для новых расчётов.');$scope=['project'=>['id'=>$project,'version'=>(int)$p['version']],'order'=>null,'specifications'=>[],'requirements_present'=>mb_strlen(trim($p['description']??''))>=20];
 if($p['order_id']){$o=crm_record('orders',(int)$p['order_id'],$lock);$scope['order']=['id'=>(int)$o['id'],'version'=>(int)$o['version'],'amount'=>$o['total_amount'],'currency'=>$o['currency']];}
 foreach(crm_query("SELECT d.id,d.head_revision,r.checksum,r.body,r.status FROM nd_cc_documents d JOIN nd_cc_revisions r ON r.document_id=d.id AND r.revision_number=d.head_revision WHERE d.project_id=? AND d.kind='specification' AND d.archived_at IS NULL ORDER BY d.id".($lock?' FOR UPDATE':''),[$project])->fetchAll() as $r){$body=json_decode($r['body'],true);if(in_array($r['status'],['approved','finalized'],true)&&mb_strlen(trim($body['requirements']??''))>=20)$scope['requirements_present']=true;unset($r['body']);$scope['specifications'][]=$r;}
 return $scope;
}
function pricing_packages(mixed $packages):array{
 if(!is_array($packages)||!array_is_list($packages)||count($packages)<1||count($packages)>20)crm_fail(422,'Нужно от 1 до 20 пакетов работ.');$keys=['name','development_hours','testing_hours','ai_input_tokens','ai_output_tokens','hosting_months','tool_units','external_units','other_units','risk','uncertain','basis'];
 foreach($packages as $p){if(!is_array($p)||count($p)!==count($keys)||array_diff(array_keys($p),$keys))crm_fail(422,'Оценка содержит неподдерживаемые поля.');cc_text($p,'name',190);cc_text($p,'basis',1000);if(!in_array($p['risk'],['low','medium','high'],true)||!is_bool($p['uncertain']))crm_fail(422,'Укажите риск и неопределённость оценки.');foreach(array_slice($keys,1,8) as $f){if($p[$f]===null)continue;$n=bill_minor($p[$f],3);if($n>1000000000)crm_fail(422,'Слишком большая оценка затрат.');}}
 return $packages;
}
function pricing_rate(string $category):?array{
 $r=crm_query("SELECT * FROM nd_cost_rates WHERE category=? AND valid_from<=UTC_DATE() AND valid_until>=UTC_DATE() ORDER BY revision_number DESC LIMIT 1".(db()->inTransaction()?' FOR UPDATE':''),[$category])->fetch();return $r?:null;
}
function pricing_estimate(int $project,array $packages,?int $artifact,string $provenance):array{
 pricing_gate();$packages=pricing_packages($packages);$scope=pricing_scope($project,true);$n=(int)crm_query('SELECT COALESCE(MAX(revision_number),0) FROM nd_project_estimates WHERE project_id=?',[$project])->fetchColumn()+1;
 crm_query('INSERT INTO nd_project_estimates(project_id,revision_number,artifact_id,packages_json,scope_json,scope_hash,provenance) VALUES (?,?,?,?,?,?,?)',[$project,$n,$artifact,ai_json($packages),ai_json($scope),hash('sha256',ai_json($scope)),$provenance]);return crm_query('SELECT * FROM nd_project_estimates WHERE id=?',[(int)db()->lastInsertId()])->fetch();
}
function pricing_ceil(int $n,int $d):int{if($n<0||$d<1||$n>PHP_INT_MAX-$d)crm_fail(422,'Расчёт выходит за допустимые границы.');return intdiv($n+$d-1,$d);}
