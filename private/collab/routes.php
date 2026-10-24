<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/files.php';require_once __DIR__.'/messages.php';require_once __DIR__.'/documents.php';require_once __DIR__.'/approvals.php';
function cc_dispatch(bool $customer,string $route,string $method):never{
 try{
  $a=cc_actor($customer,$method!=='GET');
  if($method==='POST'&&$route==='upload'){json_response(cc_upload($a));}
  if($method==='GET'){
   if(preg_match('~^projects/([1-9][0-9]*)/(documents|approvals)$~D',$route,$m))json_response($m[2]==='documents'?cc_document_lists($a,(int)$m[1]):cc_approvals_list($a,(int)$m[1]));
   if(preg_match('~^revisions/([1-9][0-9]*)$~D',$route,$m))json_response(['ok'=>true,'revision'=>cc_revision($a,(int)$m[1])]);
   if(preg_match('~^projects/([1-9][0-9]*)/context$~D',$route,$m)){$p=cc_project($a,(int)$m[1]);json_response(['ok'=>true,'project'=>['id'=>$p['id'],'title'=>$p['title'],'status'=>$p['status'],'due_on'=>$p['due_on'],'archived_at'=>$p['archived_at'],'customer_name'=>crm_record('customers',(int)$p['customer_id'])['name']],'stages'=>crm_query('SELECT id,title,status,position FROM nd_project_stages WHERE project_id=? ORDER BY position',[$p['id']])->fetchAll()]);}
   if($route==='threads')json_response(cc_threads($a));
   if(preg_match('~^projects/([1-9][0-9]*)/messages$~D',$route,$m))json_response(cc_messages($a,(int)$m[1]));
   if(preg_match('~^projects/([1-9][0-9]*)/files$~D',$route,$m)){cc_project($a,(int)$m[1]);$rows=crm_query('SELECT * FROM nd_cc_files WHERE project_id=?'.($a['type']==='customer'?" AND visibility='customer' AND archived_at IS NULL":'').' ORDER BY id DESC LIMIT 25 OFFSET '.((cc_page()-1)*25),[(int)$m[1]])->fetchAll();json_response(['ok'=>true,'items'=>array_map('cc_public_file',$rows),'page'=>cc_page(),'page_size'=>25]);}
  }elseif($method==='POST'){
   $d=input();
   if(preg_match('~^projects/([1-9][0-9]*)/documents$~D',$route,$m))json_response(cc_create_document($a,(int)$m[1],$d));
   if(preg_match('~^documents/([1-9][0-9]*)/(revise|archive)$~D',$route,$m))json_response($m[2]==='revise'?cc_new_revision($a,(int)$m[1],$d):cc_archive_document($a,(int)$m[1],$d));
   if(preg_match('~^revisions/([1-9][0-9]*)/(save|ready|submit|finalize|archive)$~D',$route,$m))json_response(match($m[2]){'save'=>cc_update_revision($a,(int)$m[1],$d),'ready'=>cc_ready($a,(int)$m[1],$d),'submit'=>cc_submit($a,(int)$m[1],$d),'finalize'=>cc_finalize($a,(int)$m[1],$d),'archive'=>cc_archive_revision($a,(int)$m[1],$d)});
   if(preg_match('~^approvals/([1-9][0-9]*)/(decide|withdraw)$~D',$route,$m))json_response($m[2]==='decide'?cc_decide($a,(int)$m[1],$d):cc_withdraw($a,(int)$m[1],$d));
   if(preg_match('~^projects/([1-9][0-9]*)/(messages|read)$~D',$route,$m))json_response($m[2]==='messages'?cc_send($a,(int)$m[1],$d):cc_read($a,(int)$m[1],$d));
   if(preg_match('~^files/([1-9][0-9]*)$~D',$route,$m))json_response(cc_file_update($a,(int)$m[1],$d));
  }
  crm_fail(404,'Раздел не найден.');
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'collaboration_error');}catch(CustomerFailure $e){fail($e->status,$e->getMessage(),$e->errorCode);}
}
