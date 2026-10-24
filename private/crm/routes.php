<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/read.php';require_once __DIR__.'/write.php';
function crm_dispatch(string $route,string $method):never{
 try{
  current_session($method!=='GET');crm_gate();
  if($method==='GET'){
   if($route==='dashboard')json_response(crm_dashboard($_GET));
   if($route==='settings')json_response(['ok'=>true,'owner'=>'Владелец','operations_enabled'=>true,'customer_access_enabled'=>(config()['customer_auth_enabled']??false)===true,'timezone'=>'UTC','registration_managed_separately'=>true,'models'=>crm_models(),'states'=>crm_states()]);
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
