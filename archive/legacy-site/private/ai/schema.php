<?php
declare(strict_types=1);
function ai_schema_value(mixed $v,string $type):void{
 if($type==='production_plan'){prod_plan_contract($v);return;}if($type==='production_files'){prod_files_contract($v);return;}if($type==='production_findings'){prod_findings_contract($v);return;}if($type==='draft_status'){if($v!=='DRAFT_ONLY')crm_fail(422,'Неподтверждённое выполнение кода.');return;}
 if($type==='packages'){pricing_packages($v);return;}
 $bad=static fn()=>crm_fail(422,'ИИ вернул результат, не соответствующий схеме.');
 if(in_array($type,['text','short'],true)){if(!is_string($v)||!mb_check_encoding($v,'UTF-8')||str_contains($v,"\0")||mb_strlen($v)>($type==='short'?190:5000))$bad();return;}
 if($type==='bool'){if(!is_bool($v))$bad();return;}
 if(in_array($type,['list','ids','tasks','observations'],true)){
  if(!is_array($v)||!array_is_list($v)||count($v)>20)$bad();foreach($v as $x){if($type==='ids'||$type==='observations'){if(!is_int($x)||$x<0)$bad();}elseif($type==='tasks'){if(!is_array($x)||array_diff(array_keys($x),['title','description','relative_effort'])||count($x)!==3)$bad();foreach($x as $s)ai_schema_value($s,'short');}else{ai_schema_value($x,'text');if(mb_strlen($x)>1000)$bad();}}return;
 }
 $enum=['agent'=>array_keys(ai_registry()),'category'=>['unknown','website','landing','ecommerce','portal','crm','ai_agent','automation','webapp'],'priority'=>['low','normal','high'],'next'=>['clarify','owner_review'],'risk'=>['low','medium','high','unknown']][$type]??[];
 if(!is_string($v)||!in_array($v,$enum,true))$bad();
}
function ai_validate_output(array $task,string $raw,array $context):array{
 if(strlen($raw)>ai_agent($task['agent_id'])['max_output_bytes'])crm_fail(422,'Ответ ИИ слишком большой.');$o=json_decode($raw,true);if(!is_array($o)||json_last_error()!==JSON_ERROR_NONE)crm_fail(422,'ИИ вернул некорректный JSON.');
 $keys=['agent','summary','observations','assumptions','missing_information','suggestions','result'];if(count($o)!==count($keys)||array_diff(array_keys($o),$keys)||($o['agent']??'')!==$task['agent_id'])crm_fail(422,'ИИ вернул неизвестные поля или другого агента.');
 ai_schema_value($o['summary'],'text');foreach(['assumptions','missing_information','suggestions'] as $f)ai_schema_value($o[$f],'list');ai_schema_value($o['observations'],'observations');foreach($o['observations'] as $i)if(!isset($context['facts'][$i]))crm_fail(422,'ИИ сослался на неподтверждённые данные.');
 $schema=ai_agent($task['agent_id'])['output_schema'];if(!is_array($o['result'])||count($schema)!==count($o['result'])||array_diff(array_keys($o['result']),array_keys($schema)))crm_fail(422,'ИИ предложил неподдерживаемую операцию.');foreach($schema as $f=>$type)ai_schema_value($o['result'][$f],$type);
 if($task['agent_id']==='lead_analyst'){$allowed=array_column(array_filter($context['facts'],fn($f)=>$f['source']==='possible_duplicate'),'id');foreach($o['result']['duplicate_candidates'] as $id)if(!in_array($id,$allowed,true))crm_fail(422,'Дубликаты не подтверждены доступным контекстом.');}
 if($task['agent_id']==='consultant'&&$o['result']['service_category']!=='unknown'&&!in_array($o['result']['service_category'],array_column($context['catalog'],'id'),true))crm_fail(422,'Услуга отсутствует в одобренном каталоге.');return $o;
}
