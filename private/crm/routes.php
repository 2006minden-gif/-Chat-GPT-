<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/read.php';require_once __DIR__.'/write.php';
function crm_dispatch(string $route,string $method):never{
 try{
  if(str_starts_with($route,'catalog/')){require_once dirname(__DIR__).'/catalog/routes.php';cat_dispatch(false,substr($route,8),$method);}
  if(str_starts_with($route,'collab/')){require_once dirname(__DIR__).'/collab/routes.php';cc_dispatch(false,substr($route,7),$method);}
  if(str_starts_with($route,'billing/')){require_once dirname(__DIR__).'/billing/routes.php';bill_dispatch(false,substr($route,8),$method);}
  if(str_starts_with($route,'ai/')){require_once dirname(__DIR__).'/ai/routes.php';ai_dispatch(false,substr($route,3),$method);}
  current_session($method!=='GET');crm_gate();
  if((config()['single_owner_mode']??false)===true&&(str_starts_with($route,'employees')||str_ends_with($route,'/members')))crm_fail(404,'Раздел не найден.');
  if($method==='GET'){
   if($route==='dashboard')json_response(crm_dashboard($_GET));
   if($route==='settings')json_response(['ok'=>true,'owner'=>'Владелец','single_owner'=>(config()['single_owner_mode']??false)===true,'operations_enabled'=>true,'catalog_enabled'=>(config()['catalog_enabled']??false)===true,'manual_handoff_enabled'=>(config()['manual_handoff_enabled']??false)===true,'production_enabled'=>(config()['production_enabled']??false)===true,'ai_enabled'=>(config()['ai_enabled']??false)===true,'billing_enabled'=>(config()['billing_enabled']??false)===true,'collaboration_enabled'=>(config()['client_collaboration_enabled']??false)===true,'customer_access_enabled'=>(config()['customer_auth_enabled']??false)===true,'timezone'=>'UTC','registration_managed_separately'=>true,'models'=>crm_models(),'states'=>crm_states()]);
   if(preg_match('~^(customers|deals|orders|projects|stages|tasks|employees|leads|activity|notifications)(?:/([1-9][0-9]*))?$~D',$route,$m))json_response(isset($m[2])?crm_detail($m[1],(int)$m[2]):crm_list($m[1],$_GET));
  }else{
   $d=input();
   if($route==='notifications/sync'&&$method==='POST'){crm_notifications();json_response(['ok'=>true]);}
   if(preg_match('~^notifications/(all|[1-9][0-9]*)/read$~D',$route,$m)&&$method==='POST'){
    if($m[1]==='all')crm_query('UPDATE nd_crm_notifications SET read_at=COALESCE(read_at,UTC_TIMESTAMP())');else crm_query('UPDATE nd_crm_notifications SET read_at=COALESCE(read_at,UTC_TIMESTAMP()) WHERE id=?',[(int)$m[1]]);json_response(['ok'=>true]);
   }
   if(preg_match('~^(customers|deals|orders|projects|stages|tasks|employees)(?:/([1-9][0-9]*))?(?:/(archive|restore|link|convert|members|reorder))?$~D',$route,$m)&&in_array($method,['POST','PATCH'],true)){
    $id=(int)($m[2]??0);$action=$m[3]??'';
    if(($id===0&&($method!=='POST'||$action!==''))||($id>0&&$action===''&&$method!=='PATCH')||($action!==''&&$method!=='POST'))crm_fail(405,'Метод не разрешён.');
    json_response(crm_write($m[1],$id,$action,$d,$method));
   }
  }
  crm_fail(404,'Раздел не найден.');
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'crm_error');}catch(PDOException $e){if(db()->inTransaction())db()->rollBack();if($e->getCode()==='23000')fail(409,'Связанная запись изменилась или значение уже занято. Обновите данные.','crm_conflict');throw $e;}
}
