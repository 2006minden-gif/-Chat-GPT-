<?php
declare(strict_types=1);
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/catalog/core.php';require dirname(__DIR__).'/private/catalog/read.php';security_headers();header('Cache-Control: no-store');
try{if($_SERVER['REQUEST_METHOD']!=='GET')crm_fail(405,'Каталог доступен только для чтения.');rate('catalog:public',120);$route=$_GET['r']??'services';if(!is_string($route))crm_fail(404,'Услуга не найдена.');if($route==='services')json_response(cat_public_list());if(preg_match('~^services/([1-9][0-9]*)$~D',$route,$m))json_response(cat_public_detail((int)$m[1]));crm_fail(404,'Услуга не найдена.');}catch(CrmFailure $e){fail($e->status,$e->getMessage(),'catalog_error');}catch(Throwable $e){server_error($e);}
