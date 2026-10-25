<?php
declare(strict_types=1);
function prod_bundle(int $run):array{
 $rows=crm_query("SELECT a.*,s.step_key,s.agent_id,s.ai_task_id FROM nd_prod_artifacts a JOIN nd_prod_steps s ON s.id=a.step_id WHERE s.run_id=? AND s.step_key<>'__qa' AND a.revision_number=s.revision_number AND s.state='COMPLETED' ORDER BY s.id",[$run])->fetchAll();$files=[];$refs=[];$bytes=0;
 foreach($rows as $r){if(!hash_equals($r['checksum'],hash('sha256',$r['files_json'])))crm_fail(409,'Контрольная сумма артефакта нарушена.');foreach(json_decode($r['files_json'],true) as $f){$path=prod_path($f['path']);if(isset($files[strtolower($path)]))crm_fail(409,'Повторяющийся файл в наборе.');$bytes+=strlen($f['content']);$files[strtolower($path)]=$f;}$refs[]=['id'=>(int)$r['id'],'step_id'=>(int)$r['step_id'],'ai_task_id'=>(int)$r['ai_task_id'],'agent'=>$r['agent_id'],'checksum'=>$r['checksum'],'revision'=>(int)$r['revision_number']];}
 if($bytes>20000)crm_fail(422,'Набор слишком велик для текущего проверенного канала QA. Нужна декомпозиция.');ksort($files);return ['files'=>$files,'references'=>$refs,'hash'=>hash('sha256',ai_json(['files'=>$files,'references'=>$refs]))];
}
function prod_step_for_task(int $task):array{
 $s=crm_query('SELECT * FROM nd_prod_steps WHERE ai_task_id=?',[$task])->fetch();if(!$s)crm_fail(409,'Задание не связано с одобренным шагом производства.');return $s;
}
function prod_assert_scheduled(array $t,bool $allowPaused=false):array{
 prod_gate();if(!$allowPaused&&(config()['production_execution_enabled']??false)!==true)crm_fail(503,'Выполнение отключено владельцем.');$s=prod_step_for_task((int)$t['id']);$r=prod_run((int)$s['run_id']);$p=prod_plan((int)$r['plan_id']);prod_current_source($p);if(!in_array($r['state'],$allowPaused?['EXECUTING','PAUSED']:['EXECUTING'],true)||!in_array($s['state'],['QUEUED','RUNNING'],true)||$s['agent_id']!==$t['agent_id']||(int)$t['project_id']!==(int)$p['project_id'])crm_fail(409,'Шаг остановлен или не разрешён текущим планом.');
 if(crm_query("SELECT 1 FROM nd_prod_dependencies d JOIN nd_prod_steps s ON s.id=d.predecessor_id WHERE d.step_id=? AND s.state<>'COMPLETED'",[$s['id']])->fetchColumn())crm_fail(409,'Зависимости шага ещё не выполнены.');return compact('s','r','p');
}
function prod_ai_context(array $t):array{
 prod_gate();
 if($t['agent_id']==='production_coordinator'){
  $spec=crm_query("SELECT r.id FROM nd_cc_documents d JOIN nd_cc_revisions r ON r.document_id=d.id AND r.revision_number=d.head_revision WHERE d.project_id=? AND d.kind='specification' AND r.status IN ('approved','finalized') ORDER BY d.id DESC LIMIT 1",[$t['project_id']])->fetchColumn();if(!$spec)crm_fail(409,'Нет принятого ТЗ для планирования.');$source=prod_source((int)$t['project_id'],(int)$spec);return ['mode'=>'plan_draft','accepted_source'=>$source,'sandbox_available'=>false,'live_adapter_available'=>false];
 }
 $link=prod_assert_scheduled($t);$source=json_decode($link['p']['source_json'],true);$body=json_decode($link['p']['body'],true);$context=['mode'=>'DRAFT_ONLY','plan_id'=>(int)$link['p']['id'],'plan_hash'=>$link['p']['checksum'],'accepted_requirements'=>$source['requirements'],'sandbox_available'=>false];
 if($link['s']['step_key']==='__qa'){$bundle=prod_bundle((int)$link['r']['id']);$context['reviewed_hash']=$bundle['hash'];$context['untrusted_artifacts']=$bundle['files'];$context['provenance']=$bundle['references'];$context['required_checks']=$body['requirements'];}
 else{
  foreach($body['steps'] as $node)if($node['key']===$link['s']['step_key'])$context['step']=$node;
  $refs=crm_query('SELECT p.id,p.run_id FROM nd_prod_dependencies d JOIN nd_prod_steps p ON p.id=d.predecessor_id WHERE d.step_id=?',[$link['s']['id']])->fetchAll();$context['inputs']=[];foreach($refs as $r){$a=crm_query('SELECT a.* FROM nd_prod_artifacts a JOIN nd_prod_steps s ON s.id=a.step_id AND s.revision_number=a.revision_number WHERE a.step_id=?',[$r['id']])->fetch();if(!$a)crm_fail(409,'Нет неизменяемого результата зависимости.');$context['inputs'][]=['artifact_id'=>(int)$a['id'],'checksum'=>$a['checksum'],'untrusted_files'=>json_decode($a['files_json'],true)];}
  $revision=crm_query('SELECT reason FROM nd_prod_revisions WHERE run_id=? ORDER BY cycle DESC LIMIT 1',[$link['r']['id']])->fetchColumn();if($revision)$context['revision_request']=$revision;
 }
 return $context;
}
function prod_capture(array $t,int $aiArtifact,array $o):array{
 prod_gate();if($t['agent_id']==='production_coordinator'){$ctx=prod_ai_context($t);return prod_create_plan_effect((int)$t['project_id'],(int)$ctx['accepted_source']['spec_revision_id'],$o['result']['plan'],$aiArtifact);}
 $link=prod_assert_scheduled($t,true);$s=crm_query('SELECT * FROM nd_prod_steps WHERE id=? FOR UPDATE',[$link['s']['id']])->fetch();$r=prod_run((int)$s['run_id'],true);$p=prod_plan((int)$r['plan_id']);prod_current_source($p,true);
 if($s['agent_id']==='production_qa')return prod_qa_capture($t,$aiArtifact,$link,$o);
 $body=json_decode($p['body'],true);$node=null;foreach($body['steps'] as $n)if($n['key']===$s['step_key'])$node=$n;if(!$node)crm_fail(409,'Шаг больше не входит в план.');$files=prod_files_contract($o['result']['files']);$paths=array_column($files,'path');if(array_diff($paths,$node['files']))crm_fail(422,'Агент создал незапланированные файлы.');foreach($o['result']['requirement_ids'] as $id)if(!in_array($id,$node['requirement_ids'],true))crm_fail(422,'Артефакт ссылается на чужое требование.');
 $raw=ai_json($files);$inputs=[];foreach(crm_query('SELECT a.id,a.checksum,a.revision_number FROM nd_prod_dependencies d JOIN nd_prod_steps s ON s.id=d.predecessor_id JOIN nd_prod_artifacts a ON a.step_id=s.id AND a.revision_number=s.revision_number WHERE d.step_id=? ORDER BY a.id',[$s['id']])->fetchAll() as $input)$inputs[]=$input;
 $contract=['input_artifacts'=>$inputs,'task_id'=>(int)$t['id'],'agent_id'=>$t['agent_id'],'agent_version'=>1,'order_id'=>(int)$p['order_id'],'project_id'=>(int)$p['project_id'],'plan_id'=>(int)$p['id'],'plan_hash'=>$p['checksum'],'source_hash'=>$p['source_hash'],'requirements'=>$o['result']['requirement_ids'],'notes'=>$o['result']['notes'],'limitations'=>$o['result']['limitations'],'execution_status'=>'DRAFT_ONLY','runtime_verification'=>'NOT_TESTED'];
 crm_query('INSERT INTO nd_prod_artifacts(step_id,revision_number,ai_artifact_id,files_json,checksum,contract_json) VALUES (?,?,?,?,?,?)',[$s['id'],$s['revision_number'],$aiArtifact,$raw,hash('sha256',$raw),ai_json($contract)]);$id=(int)db()->lastInsertId();crm_query("UPDATE nd_prod_steps SET state='COMPLETED',version=version+1 WHERE id=?",[$s['id']]);prod_event((int)$p['id'],(int)$r['id'],'draft_artifact_saved');return ['ok'=>true,'id'=>$id,'entity'=>'production_artifacts'];
}
