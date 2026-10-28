<?php
declare(strict_types=1);
require_once __DIR__.'/documents.php';require_once __DIR__.'/payments.php';require_once __DIR__.'/flow.php';require_once __DIR__.'/closure.php';require_once __DIR__.'/contract-routes.php';
function lc_dispatch(bool $customer,string $route,string $method):never{
 try{$a=cc_actor($customer,$method!=='GET');lc_gate();rate('lifecycle:'.$a['type'].':'.$a['id'],150);
 if(str_starts_with($route,'contracts/'))ct_dispatch($a,substr($route,10),$method);
 if(str_starts_with($route,'flow/'))lc_flow_dispatch($a,substr($route,5),$method);
 if(str_starts_with($route,'finance'))lc_finance_gate();
 if($method==='GET'){
  if($route==='finance')json_response(lc_finance_read($a));
  if($route==='settings')json_response(['ok'=>true,'kinds'=>lc_kinds(),'sections'=>lc_sections(),'fields'=>lc_input_labels(),'signature_method'=>'signed_copy_owner_verification','external_signature_enabled'=>false,'pdf'=>'Отдельные серверные PDF с встроенными кириллическими шрифтами для нового пакета.']);
  if($route==='templates'){cc_owner($a);json_response(['ok'=>true,'items'=>crm_query('SELECT id,kind,title,revision_number,state,checksum,version,approved_at FROM nd_lc_templates ORDER BY id DESC LIMIT 100')->fetchAll()]);}
  if(preg_match('~^templates/([1-9][0-9]*)$~D',$route,$m)){cc_owner($a);json_response(['ok'=>true,'record'=>lc_template((int)$m[1])]);}
  if(preg_match('~^documents/([1-9][0-9]*)/pdf$~D',$route,$m))ct_download(lc_binding($a,(int)$m[1]));
  if($route==='documents'){$params=[];$where='';if($customer){$where=" WHERE o.customer_id=? AND b.state<>'OWNER_REVIEW'";$params[]=$a['customer_id'];}json_response(['ok'=>true,'items'=>crm_query('SELECT b.id,b.order_id,b.revision_id,b.state,b.generated_hash,b.version,b.created_at,t.title,t.kind,t.revision_number FROM nd_lc_document_bindings b JOIN nd_orders o ON o.id=b.order_id JOIN nd_lc_templates t ON t.id=b.template_id'.$where.' ORDER BY b.id DESC LIMIT 100',$params)->fetchAll()]);}
  if(preg_match('~^documents/([1-9][0-9]*)$~D',$route,$m)){$b=lc_binding($a,(int)$m[1]);$b['pdf']=crm_query("SELECT state FROM nd_schema_migrations WHERE version='019_contract_details'")->fetchColumn()==='applied'?crm_query('SELECT checksum,size_bytes,owner_reviewed_at,countersigned_file_id,copy_released_at,payment_released_at FROM nd_lc_pdf_assets WHERE binding_id=?',[$b['id']])->fetch():false;$b['audit']=crm_query("SELECT actor_type,actor_id,action,prior_version,evidence_json,created_at FROM nd_lc_audit WHERE entity='document' AND record_id=? ORDER BY id",[$b['id']])->fetchAll();json_response(['ok'=>true,'record'=>$b]);}
 }
 if($method==='POST'){$d=input();$result=lc_mutation($a,'lifecycle/'.$route,$d,function()use($a,$route,$d){
  if(preg_match('~^finance/agreements/([1-9][0-9]*)/activate$~D',$route,$m))return lc_schedule_activate($a,(int)$m[1],$d);
  if(preg_match('~^finance/invoices/([1-9][0-9]*)/(claim|verify)$~D',$route,$m))return $m[2]==='claim'?lc_payment_claim($a,(int)$m[1],$d):lc_verify_bank($a,(int)$m[1],$d);
  if(preg_match('~^finance/claims/([1-9][0-9]*)/(link|reject)$~D',$route,$m))return lc_claim_decide($a,(int)$m[1],$m[2],$d);
  if(preg_match('~^finance/receipts/([1-9][0-9]*)/(issue|correct|transmit)$~D',$route,$m))return lc_receipt_record($a,(int)$m[1],$m[2],$d);
  if(preg_match('~^finance/payments/([1-9][0-9]*)/refund$~D',$route,$m))return lc_refund_record($a,(int)$m[1],$d);
  if($route==='templates/initial'){cc_owner($a);$ids=[];foreach(array_diff_key(lc_kinds(),array_flip(['portfolio_permission','review_permission'])) as $kind=>$title){$row=crm_query('SELECT id FROM nd_lc_templates WHERE kind=? LIMIT 1',[$kind])->fetchColumn();if($row){$ids[]=(int)$row;continue;}$r=lc_template_create($a,['kind'=>$kind,'title'=>$title,'clauses'=>lc_initial_clauses()]);$id=$r['id'];crm_query("UPDATE nd_lc_templates SET state='NEEDS_LEGAL_REVIEW',version=version+1 WHERE id=?",[$id]);lc_audit($a,'template',$id,'NEEDS_LEGAL_REVIEW',1,['source'=>'review_draft_2026_10_27']);$ids[]=$id;}return ['ok'=>true,'id'=>$ids[0],'ids'=>$ids];}
  if($route==='templates')return lc_template_create($a,$d);
  if(preg_match('~^templates/([1-9][0-9]*)/(review|approve|retire)$~D',$route,$m))return lc_template_action($a,(int)$m[1],$m[2],$d);
  if($route==='documents')return lc_generate($a,$d);
  if(preg_match('~^documents/([1-9][0-9]*)/(send|response|signed-copy|verify|reject)$~D',$route,$m))return lc_document_action($a,(int)$m[1],$m[2],$d);
  crm_fail(404,'Действие не найдено.');});json_response($result);
 }crm_fail(404,'Раздел не найден.');
 }catch(PDOException $e){if($e->getCode()==='23000')fail(409,'Запись уже существует или связана с другим действием. Обновите данные.','lifecycle_conflict');throw $e;}catch(CrmFailure $e){fail($e->status,$e->getMessage(),'lifecycle_error');}
}
