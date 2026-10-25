<?php
declare(strict_types=1);
require_once dirname(__DIR__).'/production/registry.php';
function ai_registry():array{
 $definitions=[
 'cost_estimator'=>['ИИ-оценщик затрат','Пакеты работ, трудозатраты и потребление ресурсов; цены рассчитывает только сервер.',['project'],['estimate_costs'],['work_packages'=>'packages','uncertainties'=>'list']],
 'dispatcher'=>['ИИ-диспетчер','Маршрутизация явного типа задачи без цепочек делегирования.',['none'],[],['selected_agent'=>'agent','clarification'=>'text']],
 'consultant'=>['ИИ-консультант','Уточнение запроса по одобренному каталогу услуг.',['none','project'],[],['answer'=>'text','questions'=>'list','service_category'=>'category','lead_summary'=>'text','escalate'=>'bool']],
 'lead_analyst'=>['ИИ-аналитик заявок','Рекомендации по существующей заявке, без смены статуса и слияния.',['lead'],[],['service_category'=>'category','requirements'=>'list','priority'=>'priority','next_action'=>'next','duplicate_candidates'=>'ids']],
 'proposal'=>['ИИ-менеджер предложений','Предварительное предложение и ответ клиенту; отправка только по точному согласованию.',['project'],['send_message'],['needs'=>'text','solution'=>'text','scope'=>'list','deliverables'=>'list','stages'=>'list','commercial_terms'=>'text','next_steps'=>'list','message'=>'text']],
 'specification'=>['ИИ-архитектор ТЗ','Структурированный черновик в системе версий Stage 6.',['project'],['save_spec_draft'],['title'=>'short','goal'=>'text','requirements'=>'text','functionality'=>'text','design'=>'text','constraints'=>'text','deliverables'=>'text','milestones'=>'text','acceptance'=>'text','questions'=>'list']],
 'planner'=>['ИИ-планировщик проектов','Предлагаемый план; фактические задачи только после согласования.',['project'],['create_tasks'],['milestones'=>'list','tasks'=>'tasks','dependencies'=>'list','relative_effort'=>'text','risks'=>'list']],
 'task_assistant'=>['ИИ-помощник по задачам','Рабочая сводка без назначения сотрудников и завершения задач.',['project'],[],['priorities'=>'list','blockers'=>'list','assignment_suggestions'=>'list','draft_descriptions'=>'list','missing_acceptance'=>'list']],
 'project_monitor'=>['ИИ-контролёр проектов','Проверенные сроки и прогресс отдельно от оценок ИИ.',['project'],['internal_alert'],['risk_interpretation'=>'text','suggested_actions'=>'list','estimated_risk'=>'risk']],
 'document_assistant'=>['ИИ-помощник по документам','Анализ доступной редакции, без чтения произвольных файлов.',['revision'],[],['summary'=>'text','changes'=>'list','missing_sections'=>'list','suggested_revisions'=>'list','acceptance_checklist'=>'list']],
 'business_analyst'=>['ИИ-бизнес-аналитик','Факты CRM и поступления отдельно от интерпретаций.',['none'],[],['interpretation'=>'text','demand_patterns'=>'list','process_improvements'=>'list','limitations'=>'list']]
 ];$definitions=array_merge($definitions,prod_agent_definitions());$out=[];
 foreach($definitions as $id=>[$name,$purpose,$targets,$actions,$schema])$out[$id]=['id'=>$id,'name'=>$name,'purpose'=>$purpose,'version'=>1,'targets'=>$targets,'roles'=>$id==='consultant'?['owner','customer','visitor']:['owner'],'read_capabilities'=>$targets,'proposed_actions'=>$actions,'execution_mode'=>in_array($id,['specification','project_monitor'],true)?'authorized_draft_or_internal_alert':'advisory_or_owner_approval','approval'=>'Финансы, обязательства и администрирование всегда запрещены. Внешняя отправка — только точное согласование владельца.','input_schema'=>['question'=>'string <=4000','target_id'=>'authorized integer or absent','intent'=>'explicit dispatcher route only'],'output_schema'=>$schema,'max_tokens'=>4096,'max_context_bytes'=>24000,'max_output_bytes'=>32000,'max_seconds'=>15,'max_attempts'=>3,'max_depth'=>1,'max_estimated_micro'=>1000000];
 return $out;
}
function ai_agent(string $id):array{$r=ai_registry()[$id]??null;if(!$r)crm_fail(422,'Неизвестный ИИ-агент.');return $r;}
function ai_enabled_agent(string $id):bool{return (bool)crm_query('SELECT enabled FROM nd_ai_agents WHERE agent_id=?',[$id])->fetchColumn();}
