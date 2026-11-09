<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';
function crm_portal(string $route,string $method):never{
 try{
  if($method!=='GET')crm_fail(405,'Кабинет доступен только для просмотра.');
  crm_gate();$session=ca_session();$account=ca_account((int)($session['account_id']??0));
  if(!ca_account_allowed($account)||!ca_current_consent($account))crm_fail(401,'Войдите в кабинет и подтвердите актуальные документы.');
  $customer=(int)$account['customer_id'];
  if(!preg_match('~^portal/(orders|projects)(?:/([1-9][0-9]*))?$~D',$route,$m))crm_fail(404,'Раздел не найден.');
  $kind=$m[1];$id=isset($m[2])?(int)$m[2]:null;
  // Explicit projection: no SELECT *, notes, employee contacts, costs, tasks or auth metadata.
  $columns=$kind==='orders'?'id,number,title,status,total_amount,currency,due_on,created_at':'id,order_id,title,status,starts_on,due_on,completed_at';
  $params=[$customer];$sql='SELECT '.$columns.' FROM nd_'.$kind.' WHERE customer_id=? AND archived_at IS NULL';
  if($id){$sql.=' AND id=?';$params[]=$id;}
  $page=$id?1:filter_var($_GET['page']??1,FILTER_VALIDATE_INT);if(!$page||$page<1||$page>100000)crm_fail(422,'Некорректная страница.');
  $sql.=' ORDER BY id DESC LIMIT 25 OFFSET '.(($page-1)*25);$rows=crm_query($sql,$params)->fetchAll();
  if($kind==='orders'&&crm_query("SELECT state FROM nd_schema_migrations WHERE version='016_order_lifecycle'")->fetchColumn()==='applied')foreach($rows as &$row){$flow=crm_query('SELECT commercial_state FROM nd_lc_order_flow WHERE order_id=?',[$row['id']])->fetchColumn();if(!in_array($flow,['PROPOSAL_SENT','PROPOSAL_ACCEPTED'],true)){$row['total_amount']=null;$row['price_pending_approval']=true;}}unset($row);
  if($id&&!$rows)crm_fail(404,'Запись не найдена.');
  require_once dirname(__DIR__).'/support/core.php';foreach($rows as &$row){$oid=$kind==='orders'?(int)$row['id']:(int)($row['order_id']??0);$state=$oid?sa_state($oid):['state'=>'UNCONFIGURED'];$row['workspace_access']=$state['state']!=='EXPIRED';$row['access']=array_intersect_key($state,array_flip(['state','expires_on','archive_available']));if($id&&$kind==='projects'&&!$row['workspace_access'])crm_fail(403,'Срок рабочего доступа завершён. Документы доступны в приватном архиве.');}unset($row);
  if($kind==='projects')foreach($rows as &$r){if(!$r['workspace_access'])continue;$r['progress']=crm_progress((int)$r['id']);$r['stages']=crm_query('SELECT id,title,status,position,due_on,completed_at FROM nd_project_stages WHERE project_id=? ORDER BY position,id',[$r['id']])->fetchAll();}unset($r);
  json_response($id?['ok'=>true,'record'=>$rows[0]]:['ok'=>true,'items'=>$rows,'page'=>$page,'page_size'=>25]);
 }catch(CrmFailure $e){fail($e->status,$e->getMessage(),'portal_error');}
}
