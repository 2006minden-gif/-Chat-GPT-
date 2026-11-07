<?php
declare(strict_types=1);
/** Fixed, server-owned composition of existing owner screens. No frames or arbitrary includes. */
function wf_page(string $publicRoot):never{
 $order=filter_var($_GET['order']??null,FILTER_VALIDATE_INT);$stage=$_GET['stage']??'';
 $pages=['act'=>'documents.php','answers'=>'order-answers.php','qualify'=>'orders.php','brief'=>'collaboration.php','price'=>'catalog-owner.php','proposal'=>'documents.php','details'=>'prospect-owner.php','contract'=>'contract-settings.php','signatures'=>'documents.php','payment'=>'finance.php','settlement'=>'finance.php','access'=>'orders.php','production'=>'orders.php','acceptance'=>'orders.php','handover'=>'orders.php','support'=>'orders.php','archive'=>'support.php','planning'=>'planning.php','messages'=>'collaboration.php','files'=>'collaboration.php'];
 if(!$order||$order<1||!is_string($stage)||!isset($pages[$stage])){http_response_code(404);exit('Шаг заказа не найден.');}
 $_GET['mode']='owner';ob_start();require $publicRoot.'/'.$pages[$stage];$html=ob_get_clean();
 if(http_response_code()>=400){echo $html;exit;}
 $attrs=' data-workflow-stage="'.$stage.'" data-workflow-order="'.$order.'"';
 $html=preg_replace('~<body\b([^>]*)>~i','<body$1'.$attrs.'><script src="/workflow-shell.js?v=single-card-20261107"></script><section id="workflow-shell" class="workflow-shell" aria-label="Рабочее место заказа"><a href="/order-workflow.php">← Все обращения и заказы</a><p id="workflow-reference"></p><h1 id="workflow-title">Заказ</h1><details id="workflow-steps"><summary id="workflow-step-summary">Текущий шаг и все этапы заказа</summary><ol id="workflow-progress" aria-label="Этапы заказа"></ol></details><p id="workflow-status" role="status">Загружаем текущий шаг…</p><nav id="workflow-tools" aria-label="Документы и сообщения заказа"></nav></section>',$html,1);
 $html=str_replace('</head>','<link rel="stylesheet" href="/workflow-shell.css?v=single-card-20261107"></head>',$html);
 $html=str_replace('</body>','<section id="workflow-next" class="workflow-shell" aria-label="Следующее действие"></section></body>',$html);
 echo $html;exit;
}
