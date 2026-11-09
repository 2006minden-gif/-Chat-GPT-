<?php
declare(strict_types=1);
require_once __DIR__.'/core.php';require_once __DIR__.'/actions.php';
function mh_dispatch(array $a,string $route,string $method):never{
 mh_gate($a);rate('manual:owner',100);
 if($method==='GET'){
  if($route==='jobs'){$page=cc_page();$project=filter_var($_GET['project_id']??null,FILTER_VALIDATE_INT);if(isset($_GET['project_id'])&&(!$project||$project<1))crm_fail(422,'Выберите существующий номер проекта.');$where=$project?' WHERE project_id=?':'';json_response(['ok'=>true,'items'=>crm_query('SELECT id,project_id,task_id,created_at FROM nd_manual_jobs'.$where.' ORDER BY id DESC LIMIT 20 OFFSET '.(($page-1)*20),$project?[$project]:[])->fetchAll(),'page'=>$page,'page_size'=>20]);}
  if(preg_match('~^jobs/([1-9][0-9]*)$~D',$route,$m))json_response(mh_detail((int)$m[1]));
  if(preg_match('~^results/([1-9][0-9]*)$~D',$route,$m))json_response(['ok'=>true,'record'=>mh_result((int)$m[1])]);
 }elseif($method==='POST'){
  $d=input();if($route==='prepare')json_response(mh_prepare($d));
  if(preg_match('~^jobs/([1-9][0-9]*)/import$~D',$route,$m))json_response(mh_import((int)$m[1],$d));
  if(preg_match('~^results/([1-9][0-9]*)/(check|changes|approve|deliver)$~D',$route,$m))json_response(mh_action((int)$m[1],$m[2],$d));
 }
 crm_fail(404,'Раздел ручной передачи не найден.');
}
