<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/bindings.php';require_once __DIR__.'/manage.php';require_once __DIR__.'/requests.php';require_once __DIR__.'/offers.php';require_once __DIR__.'/read.php';
function cat_dispatch(bool $customer,string $route,string $method):never{
 try{$a=cat_actor($customer,$method!=='GET');rate('catalog:'.$a['type'].':'.$a['id'],100);
 if($method==='GET'){
  if($route==='requests')json_response(cat_list_requests($a));
  if(preg_match('~^requests/([1-9][0-9]*)$~D',$route,$m))json_response(cat_detail($a,(int)$m[1]));
  if($a['type']==='owner'){
   if(in_array($route,['services','templates'],true)){$table=$route==='services'?'nd_catalog_services':'nd_catalog_templates';json_response(['ok'=>true,'items'=>crm_query('SELECT * FROM '.$table.' ORDER BY id DESC LIMIT 20 OFFSET '.((cc_page()-1)*20))->fetchAll(),'page'=>cc_page(),'page_size'=>20]);}
   if(preg_match('~^(services|templates)/([1-9][0-9]*)$~D',$route,$m))json_response(cat_owner_detail($m[1]==='services'?'service':'template',(int)$m[2]));
  }
 }elseif($method==='POST'){
  $d=input();
  if($route==='requests')json_response(cat_new($a,$d));
  if(preg_match('~^requests/([1-9][0-9]*)/(save|submit|revise|cancel|confirm|estimate|offer)$~D',$route,$m)){$id=(int)$m[1];$action=$m[2];
   if($action==='save')json_response(cat_save($a,$id,$d));if($action==='submit'){$r=cat_submit($a,$id,$d);$r['estimate']=cat_auto_estimate($id);json_response($r);}if($action==='revise')json_response(cat_revise($a,$id,$d));if($action==='cancel')json_response(cat_cancel($a,$id,$d));if($action==='confirm')json_response(cat_confirm($a,$id,$d));cc_owner($a);json_response($action==='estimate'?cat_estimate($id,$d):cat_prepare_offer($id,$d));}
  if(preg_match('~^offers/([1-9][0-9]*)/(publish|accept)$~D',$route,$m)){if($m[2]==='accept')json_response(cat_accept($a,(int)$m[1],$d));cc_owner($a);json_response(cat_publish((int)$m[1],$d));}
  cc_owner($a);if(preg_match('~^(services|templates)(?:/([1-9][0-9]*))?/(save|publish|unpublish|archive)$~D',$route,$m))json_response(cat_manage($m[1]==='services'?'service':'template',(int)($m[2]??0),$m[3],$d));
 }
 crm_fail(404,'Раздел каталога не найден.');
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'catalog_error');}
}
