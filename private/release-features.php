<?php
declare(strict_types=1);
/** Technical availability only. Client collection/paid integrations remain closed in slice A. */
function nd_release_config(array $base):array {
 if(parse_url($base['app_url']??'',PHP_URL_HOST)!=='neurodelo.pro')return $base;
 return array_replace(['crm_operations_enabled'=>true,'client_collaboration_enabled'=>true,'catalog_enabled'=>true,'ai_pricing_enabled'=>true],$base,
  ['single_owner_mode'=>true,'customer_auth_enabled'=>false,'catalog_requests_enabled'=>false,'billing_enabled'=>false,'ai_enabled'=>false,'production_enabled'=>false,'manual_handoff_enabled'=>false,'lifecycle_document_gate_ready'=>false]);
}
