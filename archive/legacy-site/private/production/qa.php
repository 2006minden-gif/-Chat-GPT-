<?php
declare(strict_types=1);
function prod_static_checks(array $plan,array $bundle,array $modelFindings):array{
 $body=json_decode($plan['body'],true);$files=$bundle['files'];$checks=[];$add=static function($id,$method,$result,$description,$evidence,$severity='warning')use(&$checks){$checks[]=['requirement_id'=>$id,'method'=>$method,'result'=>$result,'description'=>$description,'evidence'=>$evidence,'severity'=>$severity,'correction'=>$result==='PASS'?'':'Исправьте указанное требование и повторите проверку.','retest_required'=>$result!=='PASS'];};
 foreach($body['steps'] as $s)foreach($s['files'] as $path)$add('completeness','file_presence',isset($files[strtolower($path)])?'PASS':'FAIL','Наличие запланированного файла '.$path,isset($files[strtolower($path)])?hash('sha256',$files[strtolower($path)]['content']):'missing');
 foreach($body['requirements'] as $req){$file=$files[strtolower($req['file'])]??null;$runtime=in_array($req['method'],['runtime','browser'],true);$pass=$file&&($req['method']==='exists'||$req['method']==='contains'&&str_contains($file['content'],$req['expected']));$add($req['id'],$runtime?$req['method']:'literal_contract',$runtime?'NOT_TESTED':($pass?'PASS':'FAIL'),$req['description'],$file?hash('sha256',$file['content']):'missing');}
 foreach($files as $file){$unsafe=(bool)preg_match('/-----BEGIN [A-Z ]*PRIVATE KEY-----|(?:password|api_key|secret_key)\s*[=:]\s*[\x22\x27](?!YOUR_|CHANGEME|EXAMPLE|\x22|\x27)[^\x22\x27]{8,}|\b(?:eval|shell_exec|passthru|proc_open|exec|system)\s*\(|169\.254\.169\.254/iu',$file['content']);$add('security','static_pattern',$unsafe?'FAIL':'PASS','Ограниченный поиск секретов и опасных конструкций: '.$file['path'],hash('sha256',$file['content']),$unsafe?'critical':'info');}
 foreach(['installation.md','limitations.md'] as $path)$add('documentation','file_presence',isset($files[$path])&&trim($files[$path]['content'])!==''?'PASS':'FAIL','Документация '.$path,isset($files[$path])?hash('sha256',$files[$path]['content']):'missing');
 if(in_array($plan['service_type'],['website','application','integration'],true)||array_filter(array_keys($files),fn($path)=>preg_match('/\.(php|js|html|css)$/i',$path))||array_filter($files,fn($f)=>$f['kind']==='source')){foreach(['runtime','browser','accessibility'] as $method)$add('technical',$method,'NOT_TESTED','Нет одобренной изолированной среды для технической проверки.','sandbox_unavailable');}
 foreach($modelFindings as $f){if($f['result']==='PASS')continue;$add($f['requirement_id'],'ai_review',$f['result'],$f['description'],'ai_advisory_only',$f['severity']);}
 $fail=array_filter($checks,fn($c)=>in_array($c['result'],['FAIL','NEEDS_REVISION','BLOCKED'],true));$untested=array_filter($checks,fn($c)=>$c['result']==='NOT_TESTED');return ['checks'=>$checks,'verdict'=>$fail?'FAIL':($untested?'NOT_TESTED':'PASS')];
}
function prod_qa_capture(array $t,int $artifact,array $link,array $o):array{
 $r=prod_run((int)$link['r']['id'],true);$p=prod_plan((int)$r['plan_id']);$bundle=prod_bundle((int)$r['id']);if(!is_string($o['result']['reviewed_hash'])||!hash_equals($bundle['hash'],$o['result']['reviewed_hash']))crm_fail(409,'QA проверил другую редакцию результатов.');foreach($bundle['references'] as $ref)if($ref['agent']==='production_qa'||$ref['ai_task_id']===(int)$t['id'])crm_fail(403,'Производящий агент не может сертифицировать собственный результат.');
 $findings=prod_findings_contract($o['result']['findings']);$requirements=json_decode($p['source_json'],true)['requirements'];foreach($findings as $f)if(!isset($requirements[$f['requirement_id']])&&!in_array($f['requirement_id'],['general','security','documentation'],true))crm_fail(422,'QA ссылается на неизвестное требование.');$report=prod_static_checks($p,$bundle,$findings);crm_query('INSERT INTO nd_prod_qa_reports(run_id,ai_task_id,bundle_hash,verdict,checks_json) VALUES (?,?,?,?,?)',[$r['id'],$t['id'],$bundle['hash'],$report['verdict'],ai_json($report)]);$rid=(int)db()->lastInsertId();
 foreach($report['checks'] as $c)crm_query('INSERT INTO nd_prod_findings(report_id,requirement_id,method,result,severity,description,evidence,correction,retest_required) VALUES (?,?,?,?,?,?,?,?,?)',[$rid,$c['requirement_id'],$c['method'],$c['result'],$c['severity'],$c['description'],$c['evidence'],$c['correction'],$c['retest_required']?1:0]);
 crm_query("UPDATE nd_prod_steps SET state='COMPLETED',version=version+1 WHERE id=?",[$link['s']['id']]);
 if($report['verdict']==='PASS'){
  if($r['state']==='EXECUTING')prod_run_state($r,'READY','qa_pass_static_evidence');
 }elseif($report['verdict']==='NOT_TESTED')prod_issue($r,'technical_verification_unavailable');
 else{if($r['state']==='EXECUTING')prod_run_state($r,'QA_REJECTED','qa_rejected');}
 return ['ok'=>true,'id'=>$rid,'entity'=>'production_qa'];
}
function prod_revision(int $run,array $d):array{
 return crm_idempotent('production:revision:'.$run,$d,function()use($run,$d){$r=prod_run($run,true);crm_version($d,$r);$p=prod_plan((int)$r['plan_id']);prod_current_source($p,true);$report=crm_query('SELECT * FROM nd_prod_qa_reports WHERE run_id=? ORDER BY id DESC LIMIT 1 FOR UPDATE',[$run])->fetch();$limit=(int)json_decode($p['body'],true)['max_revisions'];
  if(!$report||!in_array($r['state'],['QA_REJECTED','READY'],true))crm_fail(409,'Нет результата, доступного для доработки.');if((int)$r['revision_cycles']>=$limit){prod_issue($r,'revision_limit');return ['ok'=>true,'id'=>$run,'state'=>'NEEDS_HUMAN'];}
  $cycle=(int)$r['revision_cycles']+1;$reason=cc_text($d,'reason',1000);crm_query('INSERT INTO nd_prod_revisions(run_id,report_id,cycle,reason) VALUES (?,?,?,?)',[$run,$report['id'],$cycle,$reason]);
  // Conservative whole-graph revision: all downstream inputs revalidated, old artifacts immutable.
  crm_query("UPDATE nd_prod_steps SET state='WAITING_FOR_DEPENDENCY',revision_number=revision_number+1,ai_task_id=NULL,pending_key=NULL,pending_micro=NULL,last_error=NULL,version=version+1 WHERE run_id=?",[$run]);crm_query('UPDATE nd_prod_runs SET revision_cycles=? WHERE id=?',[$cycle,$run]);prod_run_state($r,'EXECUTING','revision_requested');return ['ok'=>true,'id'=>$run,'cycle'=>$cycle];
 });
}
