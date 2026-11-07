<?php
declare(strict_types=1);
/** Owner preparation: one source of answers, one reviewed price, two private PDFs. */
function wf_preparation_lock(array $d):array{
 $a=['type'=>'owner','id'=>1];$o=crm_record('orders',cc_id($d['order_id']??null),true);$f=lc_flow($a,(int)$o['id'],true);lc_flow_active($f);crm_version($d,$f);
 if(($d['order_version']??null)!==(int)$o['version'])crm_fail(409,'Заказ изменился. Обновите карточку, сохранив введённые ответы.');
 if($f['agreement_binding_id']||$f['proposal_binding_id']||!in_array($f['commercial_state'],['INQUIRY','QUALIFIED','BRIEF_READY','PRICE_APPROVED'],true))crm_fail(409,'В этом заказе уже есть выданные коммерческие условия. Продолжите сохранённую версию или оформите изменение.');
 return [$a,$o,$f];
}
function wf_estimate_answers(array $d):array{$result=crm_idempotent('workflow/estimate-answers',$d,function()use($d){
 [$a,$o,$f]=wf_preparation_lock($d);
 $project=crm_record('projects',(int)$f['project_id'],true);if(($d['project_version']??null)!==(int)$project['version'])crm_fail(409,'Данные проекта изменились. Обновите карточку перед сохранением ответов.');
 if(crm_query("SELECT id FROM nd_lc_document_bindings WHERE order_id=? AND state<>'REJECTED' LIMIT 1",[$o['id']])->fetchColumn())crm_fail(409,'Сначала завершите проверку уже подготовленного договора и ТЗ.');
 $answers=$d['answers']??null;if(!is_array($answers))crm_fail(422,'Запишите ответы заказчика.');$body=[];
 foreach(['title'=>190,'goal'=>6000,'requirements'=>10000,'deliverables'=>6000,'constraints'=>6000,'deadline'=>1000,'acceptance'=>6000] as $key=>$limit)$body[$key]=cc_text($answers,$key,$limit);
 $r=cc_create_document_effect($a,(int)$f['project_id'],['kind'=>'specification','title'=>$body['title'],'fields'=>$body,'file_ids'=>[]]);
 crm_query("UPDATE nd_cc_revisions SET status='ready',version=version+1 WHERE id=?",[$r['id']]);
 crm_query('UPDATE nd_projects SET description=?,version=version+1 WHERE id=?',[$body['requirements'], $f['project_id']]);
 $e=pricing_estimate((int)$f['project_id'],pricing_packages($d['packages']??null),null,'owner');$q=pricing_quote($e,cc_text($d,'price',20));
 lc_flow_save($a,$f,'answers_prepared',['brief_revision_id'=>$r['id'],'quotation_id'=>(int)$q['id'],'commercial_state'=>'BRIEF_READY'],['answers_hash'=>$r['revision']['checksum'],'quotation_hash'=>$q['checksum'],'client_agreement_recorded'=>false]);
 return ['ok'=>true,'quotation_id'=>(int)$q['id'],'order_id'=>(int)$o['id']];
});return $result+['quotation'=>pricing_detail($result['quotation_id']),'records'=>wf_records($result['order_id'])];}
function wf_prepare_documents(array $d):array{return crm_idempotent('workflow/prepare-documents',$d,function()use($d){
 [$a,$o,$f]=wf_preparation_lock($d);if(crm_query("SELECT id FROM nd_lc_document_bindings WHERE order_id=? AND state<>'REJECTED' LIMIT 1",[$o['id']])->fetchColumn())crm_fail(409,'Договор и ТЗ уже подготовлены. Продолжите проверку сохранённых документов.');$qid=cc_id($d['quotation_id']??null);$q=pricing_detail($qid,true);
 if((int)$f['quotation_id']!==$qid||(int)$q['project_id']!==(int)$f['project_id']||!hash_equals($q['checksum'],(string)($d['quotation_hash']??''))||!pricing_fresh($q)||!in_array($q['state'],['DRAFT','APPROVED'],true)||$q['calculation']['profitability']!=='ACCEPTABLE')crm_fail(409,'Нужна точная актуальная оценка этого заказа с полными затратами и допустимой доходностью.');
 if(($d['confirm']??false)!==true||($q['calculation']['warnings']&&($d['accept_estimates']??false)!==true))crm_fail(422,'Проверьте цену, условия и допущения оценки.');
 $reason=cc_text($d,'reason',1000);
 if($q['state']==='DRAFT'){crm_query("INSERT INTO nd_pricing_decisions(quotation_id,owner_id,decision,quotation_hash,reason,accepted_estimates) VALUES (?,1,'APPROVED',?,?,?)",[$qid,$q['checksum'],$reason,($d['accept_estimates']??false)?1:0]);crm_query("UPDATE nd_quotations SET state='APPROVED' WHERE id=?",[$qid]);}
 $value=bill_decimal((int)$q['calculation']['selling_minor']);$valid=crm_values('orders',['total_amount'=>$value],$o);crm_query('UPDATE nd_orders SET total_amount=?,version=version+1 WHERE id=?',[$valid['total_amount'],$o['id']]);
 lc_flow_save($a,$f,'preparation_price_approved',['commercial_state'=>'PRICE_APPROVED'],['reason'=>$reason,'quotation_id'=>$qid,'quotation_hash'=>$q['checksum']]);
 lc_audit($a,'order',(int)$o['id'],'workflow_price_applied',(int)$o['version'],['quotation_id'=>$qid,'quotation_hash'=>$q['checksum'],'from_scope_hash'=>hash('sha256',ai_json($q['calculation']['scope'])),'to_scope_hash'=>hash('sha256',ai_json(pricing_scope((int)$f['project_id'])))]);
 $terms=ct_terms_save(['order_id'=>(int)$o['id'],'quotation_id'=>$qid,'direct_preparation'=>true,'values'=>$d['values']??null,'approved'=>true,'confirm_terms'=>true]);
 $result=ct_generate_pair($a,['terms_id'=>$terms['id'],'template_ids'=>$d['template_ids']??null]);
 return $result+['terms_id'=>$terms['id']];
});}
function wf_bind_prepared_agreement(array $d):array{return crm_idempotent('workflow/bind-prepared-agreement',$d,function()use($d){
 [$a,$o,$f]=wf_preparation_lock($d);if(($d['confirm']??false)!==true)crm_fail(422,'Подтвердите проверку подписанных копий.');$reason=cc_text($d,'reason',3000);
 $b=lc_binding($a,cc_id($d['binding_id']??null),true);$in=json_decode($b['input_snapshot'],true);$terms=$in['terms']['id']??null;
 if((int)$b['order_id']!==(int)$o['id']||$b['kind']!=='agreement'||($in['preparation_source']??null)!=='OWNER_REVIEWED_ANSWERS'||(int)$in['quotation']['id']!==(int)$f['quotation_id'])crm_fail(409,'Выберите договор из подготовки именно этого заказа.');
 $rows=crm_query("SELECT b.id,t.kind,b.state,b.signed_file_id,b.verified_at,b.verified_by,b.input_snapshot,a.copy_released_at,a.countersigned_file_id FROM nd_lc_document_bindings b JOIN nd_lc_templates t ON t.id=b.template_id JOIN nd_lc_pdf_assets a ON a.binding_id=b.id WHERE b.order_id=?",[$o['id']])->fetchAll();
 $seen=[];foreach($rows as $row){$snapshot=json_decode($row['input_snapshot'],true);if(($snapshot['terms']['id']??null)!==$terms||!in_array($row['kind'],['agreement','specification'],true))continue;if($row['state']!=='AGREED'||!$row['signed_file_id']||!$row['verified_at']||(int)$row['verified_by']!==1||!$row['copy_released_at']||!$row['countersigned_file_id'])crm_fail(409,'Проверьте подписи и передайте завершённые копии обоих документов.');cc_file_path(cc_file($a,(int)$row['signed_file_id']));cc_file_path(cc_file($a,(int)$row['countersigned_file_id']));$seen[]=$row['kind'];}
 if(count(array_unique($seen))!==2)crm_fail(409,'Нужны договор и ТЗ одной версии условий.');
 return lc_flow_save($a,$f,'prepared_agreement_bound',['agreement_binding_id'=>(int)$b['id'],'commercial_state'=>'PROPOSAL_ACCEPTED'],['reason'=>$reason,'agreement_hash'=>$b['generated_hash'],'source'=>'OWNER_REVIEWED_SIGNED_PAIR','client_online_decision_created'=>false]);
});}
/** Direct terms reuse the approved quote and the existing immutable terms table. */
function wf_direct_terms(array $d):array{
 $a=['type'=>'owner','id'=>1];$o=crm_record('orders',cc_id($d['order_id']??null),true);$f=lc_flow($a,(int)$o['id'],true);lc_flow_active($f);$q=pricing_detail(cc_id($d['quotation_id']??null));
 if($f['agreement_binding_id']||$f['proposal_binding_id']||$f['commercial_state']!=='PRICE_APPROVED'||(int)$f['quotation_id']!==(int)$q['id']||(int)$q['project_id']!==(int)$f['project_id']||$q['state']!=='APPROVED'||!pricing_fresh($q)||($d['approved']??false)!==true||($d['confirm_terms']??false)!==true)crm_fail(409,'Нужна одобренная цена и проверенные условия нового заказа.');
 $values=$d['values']??null;if(!is_array($values)||array_is_list($values))crm_fail(422,'Заполните условия.');$allowed=[];foreach(ct_catalog() as $t)$allowed=array_merge($allowed,$t['fields']);
 foreach($values as $key=>$value)if(!in_array($key,$allowed,true)||str_starts_with($key,'owner.')||str_starts_with($key,'client.')||!is_string($value)||mb_strlen($value)>24000)crm_fail(422,'Некорректное поле условий: '.$key);
 $schedule=lc_schedule_parse(cc_text($values,'payment.schedule',24000),(int)$q['calculation']['selling_minor'],(int)$f['project_id']);
 $fields=['subject'=>'project.purpose','deliverables'=>'spec.functions','exclusions'=>'spec.exclusions','acceptance_criteria'=>'spec.acceptance_criteria','milestones'=>'spec.milestones','dependencies'=>'spec.client_materials','revision_rounds'=>'spec.revision_rounds','third_party_costs'=>'spec.cost_payer','handover_terms'=>'spec.handover','support_terms'=>'support.scope','licenses'=>'spec.dependencies','acceptance_procedure'=>'support.defect_procedure'];
 $legacy=[];foreach($fields as $to=>$from)$legacy[$to]=cc_text($values,$from,24000);if(!preg_match('/^(?:[0-9]|[1-9][0-9]|100)$/D',$legacy['revision_rounds']))crm_fail(422,'Укажите от 0 до 100 включённых раундов правок.');$legacy['price']=bill_decimal((int)$q['calculation']['selling_minor']);$legacy['payment_schedule']=lc_schedule_text($schedule);
 $data=['preparation_source'=>'OWNER_REVIEWED_ANSWERS','quotation_hash'=>$q['checksum'],'answers_revision_id'=>(int)$f['brief_revision_id'],'legacy_fields'=>$legacy,'payment_schedule'=>$schedule,'values'=>$values];$hash=hash('sha256',lc_json($data));
 crm_query('INSERT INTO nd_lc_contract_terms(order_id,quotation_id,data_json,checksum,approved) VALUES (?,?,?,?,1)',[$o['id'],$q['id'],lc_json($data),$hash]);$id=(int)db()->lastInsertId();lc_audit($a,'contract_terms',$id,'approved',null,['hash'=>$hash,'source'=>$data['preparation_source'],'client_agreement_recorded'=>false]);return ['ok'=>true,'id'=>$id];
}
/** The closing act uses the signed terms and the exact accepted result, not a new estimate. */
function wf_prepare_act(array $d):array{return crm_idempotent('workflow/prepare-act',$d,function()use($d){
 $a=['type'=>'owner','id'=>1];$o=crm_record('orders',cc_id($d['order_id']??null),true);$f=lc_flow($a,(int)$o['id'],true);lc_flow_active($f);crm_version($d,$f);
 if(($d['order_version']??null)!==(int)$o['version']||($d['confirm']??false)!==true||!$f['agreement_binding_id']||$f['acceptance_state']!=='ACCEPTED')crm_fail(409,'Нужны подписанный договор и точная принятая итоговая версия.');
 $reason=cc_text($d,'reason',2000);$agreement=lc_binding($a,(int)$f['agreement_binding_id']);$input=json_decode($agreement['input_snapshot'],true);if(($input['preparation_source']??null)!=='OWNER_REVIEWED_ANSWERS')crm_fail(409,'Продолжите подготовку акта по сохранённому источнику этого договора.');
 $source=crm_query('SELECT * FROM nd_lc_contract_terms WHERE id=?',[$input['terms']['id']])->fetch();if(!$source||!hash_equals($source['checksum'],$input['terms']['hash'])||!hash_equals($source['checksum'],hash('sha256',lc_json(json_decode($source['data_json'],true)))))crm_fail(409,'Исходные условия договора изменились.');
 for($rows=crm_query("SELECT b.input_snapshot FROM nd_lc_document_bindings b JOIN nd_lc_templates t ON t.id=b.template_id WHERE b.order_id=? AND t.kind='acceptance' AND b.state<>'REJECTED'",[$o['id']])->fetchAll();$row=array_shift($rows);){$existing=json_decode($row['input_snapshot'],true);if(($existing['lifecycle_source']['final_manifest_hash']??null)===$f['final_hash'])crm_fail(409,'Акт этой принятой версии уже подготовлен. Откройте сохранённый документ.');}
 $template=lc_template(cc_id($d['template_id']??null));if($template['kind']!=='acceptance'||$template['state']!=='APPROVED'||!isset($template['clauses']['_package']))crm_fail(409,'Выберите одобренный отдельный шаблон акта.');
 $project=crm_record('projects',(int)$f['project_id']);$actual=lc_downstream_document_source($a,$template,$project,$o,[]);$manifest=$actual['evidence']['milestones'];$payment=lc_financial_facets($f);$minor=bill_minor($o['total_amount']);if($payment['net_minor']>$minor)crm_fail(409,'Перед актом требуется сверка переплаты.');
 $values=$d['values']??null;$ownerFields=['act.date','act.open_issues','act.remaining_obligations','act.files_and_repository','act.instructions','act.access_transfer_record','act.access_period','act.support_dates'];if(!is_array($values)||array_diff(array_keys($values),$ownerFields))crm_fail(422,'Проверьте фактические условия акта.');foreach($ownerFields as $key)$values[$key]=cc_text($values,$key,6000);
 $schedule=$input['payment_schedule'];$values+=['act.number'=>'ACT-'.$o['number'],'act.milestone'=>implode('; ',array_column($manifest,'title')),'act.deliverables'=>$actual['fields']['deliverables'],'act.revision'=>implode('; ',array_map(static fn($m)=>$m['evidence']['published_revision'].' · SHA256 '.$m['checksum'],$manifest)),'act.url'=>implode("\n",array_unique(array_column(array_column($manifest,'evidence'),'deployment_url'))),'act.checks'=>implode("\n",array_map(static fn($m)=>$m['evidence']['test_results'].' · '.$m['evidence']['verification_evidence'],$manifest)),'act.amount'=>bill_decimal($minor),'act.rights_fee'=>$input['package_fields']['price.rights_fee'],'act.paid'=>bill_decimal($payment['net_minor']),'act.balance'=>bill_decimal($payment['outstanding_minor']),'act.balance_due'=>$schedule[count($schedule)-1]['due_on'],'act.handover_status'=>$f['delivery_state']==='HANDED_OVER'?'Передача подтверждена заказчиком.':'Фактическая передача ещё не подтверждена заказчиком.'];
 $data=json_decode($source['data_json'],true);foreach(array_keys($data['values']) as $key)if(str_starts_with($key,'act.'))unset($data['values'][$key]);$data['values']=array_replace($data['values'],$values);$hash=hash('sha256',lc_json($data));crm_query('INSERT INTO nd_lc_contract_terms(order_id,quotation_id,data_json,checksum,approved) VALUES (?,?,?,?,1)',[$o['id'],$source['quotation_id'],lc_json($data),$hash]);$terms=(int)db()->lastInsertId();lc_audit($a,'contract_terms',$terms,'closing_act_approved',null,['hash'=>$hash,'agreement_hash'=>$agreement['generated_hash'],'final_hash'=>$f['final_hash'],'reason'=>$reason]);
 return ct_generate($a,['template_id'=>(int)$template['id'],'terms_id'=>$terms]);
});}
