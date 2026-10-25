<?php
declare(strict_types=1);
function pricing_automatic_projects():int{
 if((config()['ai_pricing_auto_enabled']??false)!==true)return 0;pricing_gate();$lock='nd_pricing_scan_'.substr(hash('sha256',config()['db_name']),0,32);if((int)crm_query('SELECT GET_LOCK(?,0)',[$lock])->fetchColumn()!==1)return 0;$changed=0;
 try{
  crm_query('INSERT INTO nd_pricing_scan_state(id,last_project) VALUES (1,0) ON DUPLICATE KEY UPDATE id=VALUES(id)');$after=(int)crm_query('SELECT last_project FROM nd_pricing_scan_state WHERE id=1')->fetchColumn();$projects=crm_query("SELECT id FROM nd_projects WHERE id>? AND archived_at IS NULL AND status IN ('planned','active','on_hold') ORDER BY id LIMIT 20",[$after])->fetchAll();if(!$projects){crm_query('UPDATE nd_pricing_scan_state SET last_project=0 WHERE id=1');return 0;}
  foreach($projects as $p){$id=(int)$p['id'];$scope=pricing_scope($id);$hash=hash('sha256',ai_json($scope));$e=crm_query('SELECT * FROM nd_project_estimates WHERE project_id=? ORDER BY revision_number DESC LIMIT 1',[$id])->fetch();
   if(!$e||!hash_equals($e['scope_hash'],$hash)){
    try{ai_create(['type'=>'owner','id'=>'1'],['agent'=>'cost_estimator','question'=>'Оцените полный состав затрат из брифа проекта. Неизвестные количества — null. Никаких выдуманных ставок или окончательной цены.','project_id'=>$id,'request_key'=>hash('sha256','auto-pricing:'.$id.':'.$hash)]);$changed++;}catch(CrmFailure $error){/* Safe unavailable/limit status remains visible in AI settings and tasks. */}
   }else{
    crm_atomic(function()use($id,$e,&$changed){pricing_scope($id,true);$last=crm_query('SELECT id FROM nd_quotations WHERE project_id=? ORDER BY revision_number DESC LIMIT 1 FOR UPDATE',[$id])->fetchColumn();$q=$last?pricing_detail((int)$last):null;$override=$q&&$q['calculation']['owner_override']?bill_decimal((int)$q['calculation']['owner_requested_price_minor']):null;$calculation=pricing_compute($e,$override);if(!$q||!hash_equals($q['checksum'],hash('sha256',ai_json($calculation)))){pricing_quote($e,$override,$q?(int)$q['id']:null);$changed++;}});
   }
   crm_query('UPDATE nd_pricing_scan_state SET last_project=? WHERE id=1',[$id]);
  }return $changed;
 }finally{crm_query('SELECT RELEASE_LOCK(?)',[$lock]);}
}
