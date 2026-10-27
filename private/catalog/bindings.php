<?php
declare(strict_types=1);
/** Narrow lifecycle equivalence. Never bypasses rate/policy freshness or changes price snapshots. */
function cat_binding_installed():bool{return crm_query("SELECT state FROM nd_schema_migrations WHERE version='013_service_ordering'")->fetchColumn()==='applied';}
function cat_scope_hash(array $s):string{return hash('sha256',json_encode($s,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE));}
function cat_quote_scope_matches(array $q,array $scope):bool{
 if(!cat_binding_installed())return false;$o=crm_query("SELECT o.*,r.head_revision,b.revision_number FROM nd_catalog_offers o JOIN nd_catalog_requests r ON r.id=o.request_id JOIN nd_catalog_briefs b ON b.id=o.brief_id WHERE o.quotation_id=? AND o.state IN ('AWAITING_ACCEPTANCE','ACCEPTED','CONFIRMED') ORDER BY o.id DESC LIMIT 1",[$q['id']])->fetch();
 if(!$o||(int)$o['head_revision']!==(int)$o['revision_number']||!hash_equals($o['quotation_hash'],$q['checksum'])||!hash_equals($o['pricing_scope_hash'],cat_scope_hash($q['calculation']['scope'])))return false;
 return (bool)crm_query('SELECT 1 FROM nd_catalog_scope_transitions WHERE offer_id=? AND from_hash=? AND to_hash=?',[$o['id'],$o['pricing_scope_hash'],cat_scope_hash($scope)])->fetchColumn();
}
function cat_stage9_evidence(int $order,int $spec,int $quote):?array{
 if(!cat_binding_installed())return null;
 $o=crm_query("SELECT o.*,r.order_id,r.project_id,r.head_revision,r.state AS request_state,r.service_version_id,b.revision_number,b.spec_revision_id,b.checksum AS brief_hash FROM nd_catalog_offers o JOIN nd_catalog_requests r ON r.id=o.request_id JOIN nd_catalog_briefs b ON b.id=o.brief_id WHERE r.order_id=? AND o.quotation_id=? AND o.state='CONFIRMED'",[$order,$quote])->fetch();
 if(!$o)return null;if($o['request_state']!=='CONFIRMED'||(int)$o['head_revision']!==(int)$o['revision_number']||(int)$o['spec_revision_id']!==$spec||!is_string($o['accepted_checksum'])||!hash_equals($o['checksum'],$o['accepted_checksum'])||!hash_equals($o['checksum'],hash('sha256',$o['body'])))crm_fail(409,'Принятое предложение изменилось. Нужна проверка владельца.');
 foreach([$spec,(int)$o['proposal_revision_id']] as $rev){$d=crm_query("SELECT d.account_id,d.checksum,r.checksum AS revision_hash FROM nd_cc_decisions d JOIN nd_cc_approvals a ON a.id=d.approval_id JOIN nd_cc_revisions r ON r.id=a.revision_id WHERE r.id=? AND d.decision='approved' AND a.status='approved'",[$rev])->fetch();if(!$d||(int)$d['account_id']!==(int)$o['accepted_account_id']||!hash_equals($d['checksum'],$d['revision_hash']))crm_fail(409,'Нет точного клиентского согласования ТЗ и предложения.');}
 $v=crm_query('SELECT body,checksum FROM nd_catalog_service_versions WHERE id=?',[$o['service_version_id']])->fetch();if(!$v||!hash_equals($v['checksum'],hash('sha256',$v['body'])))crm_fail(409,'Редакция услуги повреждена.');$category=json_decode($v['body'],true)['category'];$map=['website'=>'website','landing'=>'website','webapp'=>'application','ai_agent'=>'agent_spec','crm'=>'application','automation'=>'integration','integration'=>'integration'];if(!isset($map[$category]))crm_fail(409,'Вид услуги не поддерживает производство.');
 return ['adapter'=>'catalog_customer_acceptance','accepted'=>true,'spec_revision_id'=>$spec,'quotation_id'=>$quote,'service_type'=>$map[$category],'evidence_hash'=>hash('sha256',$o['checksum'].$o['accepted_checksum'].$o['brief_hash'].$o['accepted_at'])];
}
function cat_cc_guard(array $a,string $route,string $method):void{
 if($method==='GET'||!cat_binding_installed())return;$doc=null;$rev=null;
 if(preg_match('~^documents/([1-9][0-9]*)/~D',$route,$m))$doc=(int)$m[1];
 elseif(preg_match('~^revisions/([1-9][0-9]*)/~D',$route,$m))$rev=(int)$m[1];
 elseif(preg_match('~^approvals/([1-9][0-9]*)/~D',$route,$m)){$rev=crm_query('SELECT revision_id FROM nd_cc_approvals WHERE id=?',[(int)$m[1]])->fetchColumn();if(!$rev)return;$rev=(int)$rev;}
 if(!$doc&&!$rev)return;if($doc)cc_document($a,$doc);else cc_revision($a,$rev);$ids=$doc?crm_query('SELECT id FROM nd_cc_revisions WHERE document_id=?',[$doc])->fetchAll(PDO::FETCH_COLUMN):[$rev];
 foreach($ids as $id)if(crm_query('SELECT 1 FROM nd_catalog_briefs WHERE spec_revision_id=? UNION ALL SELECT 1 FROM nd_catalog_offers WHERE proposal_revision_id=? LIMIT 1',[$id,$id])->fetchColumn())crm_fail(409,'Документ связан с брифом и ценой. Используйте страницу заявки каталога для согласования или новой редакции.');
}
/** Mandatory owner time is controlled service data; a model cannot silently omit unknown costs. */
function cat_owner_labor_packages(int $project):array{
 if(!cat_binding_installed())return [];$v=crm_query('SELECT v.body,v.checksum,r.package_key FROM nd_catalog_requests r JOIN nd_catalog_service_versions v ON v.id=r.service_version_id WHERE r.project_id=?',[$project])->fetch();if(!$v)return [];if(!hash_equals($v['checksum'],hash('sha256',$v['body'])))crm_fail(409,'Модель услуги повреждена.');$body=json_decode($v['body'],true);$package=null;foreach($body['packages'] as $p)if($p['id']===$v['package_key'])$package=$p;if(!$package)crm_fail(409,'Пакет услуги больше не определён.');$out=[];
 foreach(['owner_review_hours'=>'Проверка результата владельцем','correction_hours'=>'Исправления владельцем'] as $field=>$label)$out[]=['name'=>$label,'development_hours'=>$package[$field],'testing_hours'=>'0','ai_input_tokens'=>'0','ai_output_tokens'=>'0','hosting_months'=>'0','tool_units'=>'0','external_units'=>'0','other_units'=>'0','risk'=>'medium','uncertain'=>true,'basis'=>'Отдельная модель времени владельца для точной редакции услуги; null — неизвестное, не ноль.'];return $out;
}
function cat_revision_request(int $revision):?int{if(!cat_binding_installed())return null;$id=crm_query('SELECT request_id FROM nd_catalog_briefs WHERE spec_revision_id=? UNION ALL SELECT request_id FROM nd_catalog_offers WHERE proposal_revision_id=? LIMIT 1',[$revision,$revision])->fetchColumn();return $id===false?null:(int)$id;}
