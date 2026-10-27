<?php
declare(strict_types=1);
function prod_agent_definitions():array{return [
 'production_coordinator'=>['ИИ-координатор производства','Предлагает ограниченный DAG по принятому заказу; не одобряет план.',['project'],[],['plan'=>'production_plan']],
 'production_website'=>['ИИ-разработчик сайтов','HTML/CSS/JS как неисполненные артефакты; без развёртывания.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_application'=>['ИИ-разработчик приложений','Компоненты/API/тесты как черновики, без исполнения кода на сервере.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_agent'=>['ИИ-разработчик агентов','Схемы и инструкции, только документированные интеграции.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_design'=>['ИИ-дизайнер','Структура, спецификации компонентов и доступности; не customer-approved design.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_content'=>['ИИ-копирайтер','Текстовые черновики без выдуманных отзывов, наград и юридических гарантий.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_integration'=>['ИИ-интегратор','Mappings/contracts/config examples без реальных секретов и внешних действий.',['project'],[],['files'=>'production_files','notes'=>'text','limitations'=>'list','requirement_ids'=>'list','execution_status'=>'draft_status']],
 'production_qa'=>['ИИ-контролёр качества','Независимое advisory review; технический PASS требует backend evidence.',['project'],[],['findings'=>'production_findings','reviewed_hash'=>'text','limitations'=>'list']]
];}
