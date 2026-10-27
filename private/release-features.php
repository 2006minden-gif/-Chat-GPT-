<?php
declare(strict_types=1);
/** Technical availability only. Client collection/paid integrations remain closed in slice A. */
function nd_release_config(array $base):array {
 require_once __DIR__.'/customer-settings-state.php';$host=parse_url($base['app_url']??'',PHP_URL_HOST);
 if($host!=='neurodelo.pro'){if(($base['customer_settings_test_mode']??false)===true&&in_array($host,['127.0.0.1','localhost','::1'],true))return ocs_runtime_overlay($base);return $base;}
 $configured=array_replace(['crm_operations_enabled'=>true,'client_collaboration_enabled'=>true,'catalog_enabled'=>true,'ai_pricing_enabled'=>true],$base,
  ['order_lifecycle_enabled'=>true,'lifecycle_finance_enabled'=>true,'lifecycle_documents_enabled'=>true,'single_owner_mode'=>true,'customer_auth_enabled'=>false,'catalog_requests_enabled'=>false,'billing_enabled'=>false,'ai_enabled'=>false,'production_enabled'=>false,'manual_handoff_enabled'=>false,'lifecycle_document_gate_ready'=>false]);
 return ocs_runtime_overlay($configured);
}
