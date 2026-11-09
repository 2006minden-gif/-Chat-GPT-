<?php
declare(strict_types=1);
function prod_services():array{return ['website','application','agent_spec','design','content','integration'];}
function prod_producer_agents():array{return ['production_website','production_application','production_agent','production_design','production_content','production_integration'];}
function prod_exact(array $d,array $keys):void{if(count($d)!==count($keys)||array_diff(array_keys($d),$keys))crm_fail(422,'Неподдерживаемые поля производственного контракта.');}
function prod_path(mixed $path):string{
 if(!is_string($path)||!preg_match('/^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}\.(?:html|css|js|php|json|md|txt|example)$/D',$path)||str_contains($path,'..')||str_contains($path,'%')||preg_match('/^(?:config\.php|\.env|id_rsa)$/i',$path))crm_fail(422,'Небезопасное имя артефакта. Допустимы только простые имена файлов.');return $path;
}
function prod_plan_contract(mixed $p):array{
 if(!is_array($p))crm_fail(422,'Ожидается структурированный план.');prod_exact($p,['title','steps','requirements','budget_micro','cost_currency','max_revisions','limitations']);cc_text($p,'title',190);ai_schema_value($p['limitations'],'list');
 if(!is_int($p['budget_micro'])||$p['budget_micro']<1||$p['budget_micro']>1000000||!in_array($p['cost_currency'],['RUB','USD','EUR'],true)||!is_int($p['max_revisions'])||$p['max_revisions']<0||$p['max_revisions']>3)crm_fail(422,'Проверьте бюджет и предел доработок (0–3).');
 if(!is_array($p['steps'])||!array_is_list($p['steps'])||!count($p['steps'])||count($p['steps'])>12)crm_fail(422,'План: от 1 до 12 шагов.');$seen=[];
 foreach($p['steps'] as $s){if(!is_array($s))crm_fail(422,'Проверьте шаг плана.');prod_exact($s,['key','title','agent','depends_on','files','requirement_ids']);if(!is_string($s['key'])||!preg_match('/^[a-z][a-z0-9_]{0,30}$/D',$s['key'])||isset($seen[$s['key']])||!in_array($s['agent'],prod_producer_agents(),true))crm_fail(422,'Неверный шаг или исполнитель.');cc_text($s,'title',190);foreach(['depends_on','files','requirement_ids'] as $f){if(!is_array($s[$f])||!array_is_list($s[$f])||count($s[$f])>20||count(array_unique($s[$f],SORT_REGULAR))!==count($s[$f]))crm_fail(422,'Проверьте связи и файлы шага.');}foreach($s['depends_on'] as $dep)if(!is_string($dep)||!isset($seen[$dep]))crm_fail(422,'Зависимость должна указывать на предыдущий шаг; циклы запрещены.');foreach($s['files'] as $f)prod_path($f);$seen[$s['key']]=true;}
 if(!is_array($p['requirements'])||!array_is_list($p['requirements'])||!count($p['requirements'])||count($p['requirements'])>20)crm_fail(422,'Укажите требования принятого ТЗ.');$ids=[];
 foreach($p['requirements'] as $r){if(!is_array($r))crm_fail(422,'Проверьте требование.');prod_exact($r,['id','description','file','method','expected']);if(!is_string($r['id'])||!preg_match('/^R[1-9][0-9]?$/D',$r['id'])||isset($ids[$r['id']])||!in_array($r['method'],['exists','contains','runtime','browser'],true))crm_fail(422,'Проверьте ID и метод проверки.');$ids[$r['id']]=true;cc_text($r,'description',1000);cc_text($r,'expected',1000,$r['method']==='contains');prod_path($r['file']);}
 foreach($p['steps'] as $s)foreach($s['requirement_ids'] as $id)if(!is_string($id)||!isset($ids[$id]))crm_fail(422,'Шаг ссылается на неизвестное требование.');return $p;
}
function prod_files_contract(mixed $files):array{
 if(!is_array($files)||!array_is_list($files)||!count($files)||count($files)>10)crm_fail(422,'От 1 до 10 файлов в результате.');$seen=[];$bytes=0;
 foreach($files as $f){if(!is_array($f))crm_fail(422,'Неверный артефакт.');prod_exact($f,['path','content','kind']);$path=prod_path($f['path']);if(isset($seen[strtolower($path)]))crm_fail(422,'Повторяющееся имя файла.');$seen[strtolower($path)]=true;if(!is_string($f['content'])||!mb_check_encoding($f['content'],'UTF-8')||str_contains($f['content'],"\0")||strlen($f['content'])>12000||!in_array($f['kind'],['source','documentation','design','integration'],true))crm_fail(422,'Неверный тип или размер содержимого.');$bytes+=strlen($f['content']);}if($bytes>24000)crm_fail(422,'Артефакты слишком велики.');return $files;
}
function prod_findings_contract(mixed $v):array{
 if(!is_array($v)||!array_is_list($v)||count($v)>20)crm_fail(422,'Некорректный QA-отчёт.');foreach($v as $r){if(!is_array($r))crm_fail(422,'Некорректная QA-находка.');prod_exact($r,['requirement_id','description','result','severity','correction']);foreach(['requirement_id','description','correction'] as $f)cc_text($r,$f,$f==='requirement_id'?32:1000,false);if(!in_array($r['result'],['PASS','FAIL','NEEDS_REVISION','NOT_TESTED','BLOCKED'],true)||!in_array($r['severity'],['info','warning','critical'],true))crm_fail(422,'Некорректный вердикт QA.');}return $v;
}
