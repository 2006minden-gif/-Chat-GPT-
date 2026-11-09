<?php
declare(strict_types=1);
/** Optional MAX transport for the same customer session, without changing website cookie policy. */
function ma_session_token(string $raw):string{
 if((config()['max_miniapp_enabled']??false)!==true||!preg_match('/^[a-f0-9]{64}$/D',$raw))ca_fail(401,'max_session_expired','Откройте мини-приложение MAX заново.');
 $q=db()->prepare('SELECT s.token_hash FROM nd_max_sessions s JOIN nd_max_account_links l ON l.max_user_id=s.max_user_id JOIN nd_customer_sessions c ON c.token_hash=s.token_hash WHERE s.token_hash=? AND s.expires_at>? AND c.account_id=l.account_id');$q->execute([hash('sha256',$raw),time()]);if(!$q->fetchColumn())ca_fail(401,'max_session_expired','Сессия MAX истекла или привязка отозвана.');return $raw;
}
