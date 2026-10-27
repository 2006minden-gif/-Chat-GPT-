<?php
declare(strict_types=1);
ini_set('display_errors','0');require dirname(__DIR__).'/private/app.php';require dirname(__DIR__).'/private/billing/routes.php';security_headers();header('Cache-Control: no-store');
try{
 bill_gate();bill_provider();if($_SERVER['REQUEST_METHOD']!=='POST')fail(405,'Метод не разрешён.');rate('billing-webhook',120);
 if((int)($_SERVER['CONTENT_LENGTH']??0)>8192)fail(413,'Слишком большой запрос.');if(stripos($_SERVER['CONTENT_TYPE']??'','application/json')!==0)fail(415,'Ожидается JSON.');$raw=file_get_contents('php://input',false,null,0,8193);if(!is_string($raw)||strlen($raw)>8192)fail(413,'Слишком большой запрос.');$e=json_decode($raw,true);if(!is_array($e)||json_last_error()!==JSON_ERROR_NONE)fail(400,'Некорректное уведомление.');$id=$e['object']['id']??null;if(!is_string($id)||!preg_match('/^[A-Za-z0-9_-]{1,128}$/D',$id))fail(400,'Некорректное уведомление.');
 $refund=($e['event']??'')==='refund.succeeded';$r=crm_query('SELECT * FROM '.($refund?'nd_refunds':'nd_payment_attempts').' WHERE provider_id=?',[$id])->fetch();if(!$r)fail(404,'Запись не найдена.');
 $verified=bill_provider()->verifyWebhook($e);
 if($refund){$p=crm_query('SELECT * FROM nd_payment_attempts WHERE id=?',[$r['attempt_id']])->fetch();if($p['merchant_hash']!==bill_merchant_hash())crm_fail(409,'Магазин не совпадает.');bill_apply_refund($r,$p,$verified['object']);}else bill_apply_payment($r,$verified['object']);json_response(['ok'=>true]);
}catch(CrmFailure $e){fail($e->status,$e->getMessage(),'payment_event_rejected');}catch(Throwable $e){server_error($e);}
