<?php
/** CLI-only safe gate evidence. Never exports settings, mail usernames/passwords or customer data. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');require dirname(__DIR__).'/app.php';require __DIR__.'/core.php';
try{$r=wf_readiness();echo json_encode(['ok'=>true,'legal'=>$r['policy'],'document_templates'=>$r['document_templates'],'owner_details_reviewed'=>$r['owner_details_reviewed'],'mail_verified'=>$r['mail']['verified'],'repeat_mail_verification_required'=>false,'capabilities'=>$r['capabilities'],'remaining_actions'=>array_column($r['owner_actions'],'code')],JSON_UNESCAPED_SLASHES|JSON_THROW_ON_ERROR);}
catch(Throwable $e){echo '{"ok":false,"error":"gate_evidence_unavailable"}';exit(1);}
