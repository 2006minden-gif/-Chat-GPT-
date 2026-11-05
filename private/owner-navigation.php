<?php
declare(strict_types=1);
/** One directory of owner screens. Links never grant access or create scoped customer URLs. */
function owner_navigation_groups():array{return [
 'Заказы и клиенты'=>[
 ['Заказы от обращения до приёмки','/order-workflow.php'],['Заявки и уведомления MAX','/studio.php'],['Корзина заявок','/studio.php#trash'],['Обзор CRM','/workspace.php#dashboard'],['Все заявки CRM','/workspace.php#leads'],['Клиенты','/workspace.php#customers'],['Сделки','/workspace.php#deals'],['Заказы','/workspace.php#orders'],['Проекты','/workspace.php#projects'],['Задачи','/workspace.php#tasks'],['Сроки и загрузка','/planning.php'],['Поддержка и архив','/support.php?mode=owner']],
 'Документы и общение'=>[
 ['Документы заказов','/documents.php?mode=owner#documents'],['Шаблоны и правовая проверка','/documents.php?mode=owner#templates'],['Реквизиты исполнителя','/contract-settings.php'],['Обмен до открытия кабинета','/prospect-owner.php'],['Сообщения','/collaboration.php?mode=owner#messages'],['Закрытые файлы','/collaboration.php?mode=owner#files'],['Согласования','/collaboration.php?mode=owner#approvals']],
 'Услуги и расчёты'=>[
 ['Редактор каталога услуг','/catalog-owner.php'],['Оценки и расчёты','/catalog-owner.php#quotes'],['Ставки и правила расчёта','/catalog-owner.php#rates']],
 'Оплата и настройки'=>[
 ['Оплата и чеки заказов','/finance.php?mode=owner'],['Оплата и QR','/payment-settings.php'],['Счета и платежи','/billing.php?mode=owner'],['Почта и доступ клиентов','/client-settings.php'],['Настройки CRM','/workspace.php#settings'],['Уведомления','/workspace.php#notifications'],['История действий','/workspace.php#activity']],
 'Публикации'=>[
 ['Редактор портфолио','/publication-owner.php?kind=portfolio'],['Редактор отзывов','/publication-owner.php?kind=review']],
 'Инструменты и помощь'=>[
 ['ИИ-центр','/ai.php?mode=owner'],['ИИ-производство','/production.php'],['Ручные задания','/handoff.php'],['Помощь владельцу','/help.php']],
 'Публичные страницы'=>[
 ['Главная сайта','/'],['Услуги','/catalog.php'],['Портфолио на сайте','/portfolio.php'],['Отзывы на сайте','/reviews.php'],['Политика конфиденциальности','/privacy.php'],['Согласие на обработку данных','/consent.php'],['Политика клиентского кабинета','/customer-privacy.php'],['Аналитика и выбор посетителя','/analytics.php'],['Карта сайта','/sitemap.php']]
];}
function owner_navigation(bool $expanded=false):void{
 static $rendered=false;if($rendered)return;$rendered=true;
 $esc=fn($s)=>htmlspecialchars($s,ENT_QUOTES,'UTF-8');
 $c=config();$gates=['/workspace.php'=>'crm_operations_enabled','/catalog-owner.php'=>'catalog_enabled','/collaboration.php'=>'client_collaboration_enabled','/billing.php'=>'billing_enabled','/ai.php'=>'ai_enabled','/production.php'=>'production_enabled','/handoff.php'=>'manual_handoff_enabled'];
 echo '<link rel="stylesheet" href="/owner-navigation.css?v=20261105"><script src="/owner-navigation.js?v=20261105" defer></script><section class="owner-directory product-navigation" data-owner-directory aria-label="Навигация владельца"><div class="owner-shortcuts"><a href="/studio.php">Мой кабинет</a><a href="/order-workflow.php">Все заказы</a><a href="/contract-settings.php">Реквизиты исполнителя</a><a href="/payment-settings.php">Оплата и QR</a><a href="/client-settings.php">Почта и доступ клиентов</a><a href="/help.php">Помощь</a></div><details'.($expanded?' open':'').'><summary>Все разделы кабинета и страницы сайта</summary><p class="owner-directory-note">Выберите раздел по задаче. Документы, оплата и приглашения конкретного клиента открываются из его заказа. Недоступный модуль может требовать настройки; меню не меняет права доступа.</p><label class="owner-directory-search">Найти раздел<input type="search" placeholder="Например: реквизиты, шаблоны, почта" autocomplete="off"></label><div class="owner-directory-groups">';
 foreach(owner_navigation_groups() as $title=>$items){echo '<details class="owner-directory-group"><summary>'.$esc($title).'</summary><ul>';foreach($items as [$text,$href]){$flag=$gates[parse_url($href,PHP_URL_PATH)]??null;if($flag&&($c[$flag]??false)!==true)echo '<li><span class="owner-directory-disabled">'.$esc($text).' — не включено</span></li>';else echo '<li><a href="'.$esc($href).'">'.$esc($text).'</a></li>';}echo '</ul></details>';}
 if(($c['catalog_enabled']??false)!==true)echo '<p>Каталог услуг пока не опубликован.</p>';
 echo '</div><p class="owner-directory-empty" hidden>Раздел не найден. Попробуйте другое слово или откройте «Помощь».</p></details></section>';
}
