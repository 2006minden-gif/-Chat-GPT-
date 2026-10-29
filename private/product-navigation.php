<?php
declare(strict_types=1);
/** Shared contextual navigation; feature flags hide unavailable modules, not authorization. */
function product_navigation(bool $owner):void{
 $c=config();$links=$owner?['Обзор'=>'/workspace.php#dashboard','Заявки'=>'/workspace.php#leads','Клиенты'=>'/workspace.php#customers','Сделки'=>'/workspace.php#deals','Заказы'=>'/workspace.php#orders','Проекты'=>'/workspace.php#projects','Задачи'=>'/workspace.php#tasks','Настройки'=>'/workspace.php#settings']:['Обзор'=>'/portal.php','Мои заказы'=>'/portal.php#orders','Мои проекты'=>'/portal.php#projects','Профиль'=>'/customer.php'];$mode=$owner?'?mode=owner':'';if(($c['catalog_enabled']??false)===true){if($owner||(($c['catalog_requests_enabled']??false)===true&&($c['catalog_privacy_approved']??false)===true))$links[$owner?'Каталог услуг и брифы':'Мои брифы и заявки']=$owner?'/catalog-owner.php':'/ordering.php';$links['Услуги']='/catalog.php';}
 if(($c['client_collaboration_enabled']??false)===true){foreach(['messages'=>'Сообщения','files'=>'Файлы','documents'=>'Документы','approvals'=>'Согласования'] as $route=>$title)$links[$title]='/collaboration.php'.$mode.'#'.$route;}
 if(($c['lifecycle_documents_enabled']??false)===true)$links['Договорные документы']='/documents.php'.$mode;
 if($owner)$links['От обращения до приёмки']='/order-workflow.php';
 if($owner)$links['Документы до кабинета']='/prospect-owner.php';
 if($owner)$links['Реквизиты и PDF']='/contract-settings.php';
 if($owner)$links['Настройка клиентского кабинета']='/client-settings.php';
 if(($c['order_lifecycle_enabled']??false)===true)$links['Рабочий цикл заказов']='/orders.php'.$mode;
 if(($c['lifecycle_finance_enabled']??false)===true)$links['Оплата и чеки']='/finance.php'.$mode;
 if(($c['billing_enabled']??false)===true)$links[$owner?'Финансы':'Счета и оплата']='/billing.php'.$mode;
 if(($c['ai_enabled']??false)===true)$links[$owner?'ИИ-центр':'ИИ-помощник']='/ai.php'.$mode;
 if($owner&&($c['production_enabled']??false)===true)$links['ИИ-производство']='/production.php';
 if($owner&&($c['manual_handoff_enabled']??false)===true)$links['Ручные задания']='/handoff.php';
 echo '<details class="product-navigation"><summary>Разделы '.($owner?'CRM':'кабинета').'</summary><nav class="tabs" aria-label="'.($owner?'Единая навигация CRM':'Единая навигация кабинета').'">';foreach($links as $title=>$href)echo '<a href="'.htmlspecialchars($href,ENT_QUOTES,'UTF-8').'">'.htmlspecialchars($title,ENT_QUOTES,'UTF-8').'</a>';echo '</nav>';if(($c['catalog_enabled']??false)!==true){if($owner)echo '<p>Каталог услуг пока не опубликован.</p>';else echo '<p>Список заявок до создания заказа пока недоступен в кабинете.</p>';}echo '</details>';
}
