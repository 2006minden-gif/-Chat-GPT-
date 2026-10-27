<?php
declare(strict_types=1);
require_once __DIR__.'/closure.php';
/** Read-only owner projection of existing authoritative models; no duplicate task store. */
function lc_owner_dashboard():array{
 $a=['type'=>'owner','id'=>1];$queries=[
 'qualification'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='ACTIVE' AND commercial_state='INQUIRY'",
 'brief_estimate'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='ACTIVE' AND commercial_state IN ('QUALIFIED','BRIEF_READY')",
 'document_review'=>"SELECT COUNT(*) FROM nd_lc_document_bindings WHERE state IN ('OWNER_REVIEW','CLIENT_RESPONSE','SIGNED_COPY_SUBMITTED')",
 'missing_materials'=>"SELECT COUNT(*) FROM nd_lc_obligations WHERE kind='MATERIAL' AND required=1 AND state NOT IN ('VERIFIED','NOT_APPLICABLE')",
 'payment_claims'=>"SELECT COUNT(*) FROM nd_lc_payment_claims WHERE state='REPORTED'",
 'receipt_tasks'=>"SELECT COUNT(*) FROM nd_lc_receipt_tasks WHERE state<>'TRANSMISSION_RECORDED'",
 'overdue_receipts'=>"SELECT COUNT(*) FROM nd_lc_receipt_tasks WHERE state IN ('MISSING','OWNER_RECORDED') AND due_at<UTC_TIMESTAMP()",
 'active_work'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='ACTIVE' AND delivery_state='IN_PRODUCTION'",
 'acceptance'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='ACTIVE' AND (delivery_state='CLIENT_REVIEW' OR acceptance_state='REVIEW')",
 'feedback'=>"SELECT COUNT(*) FROM nd_lc_feedback WHERE state='OPEN'",
 'changes'=>"SELECT COUNT(*) FROM nd_lc_scope_changes WHERE applied_at IS NULL AND COALESCE(owner_decision,'')<>'REJECT' AND COALESCE(client_decision,'')<>'REJECT'",
 'handover'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='ACTIVE' AND acceptance_state='ACCEPTED' AND delivery_state<>'HANDED_OVER'",
 'closed_support'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state='CLOSED' AND support_start<=UTC_DATE() AND (support_end IS NULL OR support_end>=UTC_DATE())",
 'exceptions'=>"SELECT COUNT(*) FROM nd_lc_order_flow WHERE case_state IN ('PAUSED','DISPUTED','CANCELLED','DECLINED')"
 ];$counts=[];foreach($queries as $key=>$sql)$counts[$key]=(int)crm_query($sql)->fetchColumn();$actions=[];
 $rows=crm_query("SELECT f.order_id,o.title,o.due_on FROM nd_lc_order_flow f JOIN nd_orders o ON o.id=f.order_id WHERE f.case_state<>'CLOSED' ORDER BY CASE WHEN o.due_on<UTC_DATE() THEN 0 ELSE 1 END,o.due_on IS NULL,o.due_on,f.order_id LIMIT 20")->fetchAll();
 foreach($rows as $r){$f=lc_flow_detail($a,(int)$r['order_id']);$actions[]=['order_id'=>(int)$r['order_id'],'title'=>$r['title'],'due_on'=>$r['due_on'],'overdue'=>$r['due_on']!==null&&$r['due_on']<gmdate('Y-m-d'),'next_action'=>$f['next_action']];}
 return ['counts'=>$counts,'actions'=>$actions,'actions_limit'=>20,'more_url'=>'/orders.php?mode=owner'];
}
