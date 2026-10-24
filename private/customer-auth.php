<?php
declare(strict_types=1);
require_once __DIR__.'/customer-mail.php';
final class CustomerFailure extends RuntimeException {
    public function __construct(public int $status, public string $errorCode, string $message) {parent::__construct($message);}
}
function ca_fail(int $status,string $code,string $message): never {throw new CustomerFailure($status,$code,$message);}
function ca_enabled(): bool {
    $c=config();$host=parse_url($c['app_url'],PHP_URL_HOST);
    $safeOrigin=parse_url($c['app_url'],PHP_URL_SCHEME)==='https' || (($c['customer_auth_test_mode']??false)===true && in_array($host,['127.0.0.1','localhost','::1'],true));
    return ($c['customer_auth_enabled']??false)===true && ($c['customer_auth_privacy_approved']??false)===true && $safeOrigin && privacy_settings()['enabled'];
}
function ca_gate(): void {
    if (!ca_enabled()) ca_fail(503,'registration_unavailable','Кабинет временно недоступен. Регистрация пока закрыта.');
    $q=db()->query("SELECT version,state FROM nd_schema_migrations WHERE version IN ('004_crm_foundation','005_customer_auth')");
    $states=$q->fetchAll(PDO::FETCH_KEY_PAIR);
    if (($states['004_crm_foundation']??'')!=='applied'||($states['005_customer_auth']??'')!=='applied')ca_fail(503,'registration_unavailable','Кабинет временно недоступен.');
}
function ca_email(array $data): string {
    $email=mb_strtolower(field($data,'email',190),'UTF-8');
    // SMTP envelope uses ASCII addresses; no CR/LF or SMTPUTF8 ambiguity.
    if (!preg_match('/^[\x21-\x7e]+$/D',$email)||filter_var($email,FILTER_VALIDATE_EMAIL)===false)ca_fail(422,'invalid_email','Укажите корректный email.');
    return $email;
}
function ca_password(array $data,bool $confirm=true): string {
    $p=$data['password']??'';
    if (!is_string($p)||!mb_check_encoding($p,'UTF-8')||str_contains($p,"\0")||mb_strlen($p)<12||strlen($p)>72||!preg_match('/\p{L}/u',$p)||!preg_match('/\p{N}/u',$p))ca_fail(422,'weak_password','Пароль: от 12 символов, буквы и цифры, не более 72 байт.');
    if ($confirm && (!is_string($data['password_confirmation']??null)||!hash_equals($p,$data['password_confirmation'])))ca_fail(422,'password_mismatch','Пароли не совпадают.');
    return $p;
}
function ca_consent(array $data): array {
    $policy=privacy_settings();
    if (!$policy['enabled'])ca_fail(503,'registration_unavailable','Регистрация пока закрыта.');
    if (($data['consent']??null)!==true)ca_fail(422,'consent_required','Подтвердите согласие на обработку данных.');
    if (($data['policy_version']??'')!==$policy['version'])ca_fail(409,'policy_changed','Документы обновлены. Прочитайте их и подтвердите согласие заново.');
    return $policy;
}
function ca_rate(string $kind,int $max,string $key): void {
    $pdo=db();$bucket=hash('sha256','customer:'.$kind.':'.$key);$now=time();
    $pdo->prepare('DELETE FROM nd_limits WHERE expires<=? LIMIT 500')->execute([$now]);
    $pdo->beginTransaction();
    try {
        $pdo->prepare('DELETE FROM nd_limits WHERE bucket=? AND expires<=?')->execute([$bucket,$now]);
        $pdo->prepare('INSERT INTO nd_limits(bucket,attempts,expires) VALUES (?,1,?) ON DUPLICATE KEY UPDATE attempts=attempts+1')->execute([$bucket,$now+900]);
        $q=$pdo->prepare('SELECT attempts FROM nd_limits WHERE bucket=? FOR UPDATE');$q->execute([$bucket]);$n=(int)$q->fetchColumn();$pdo->commit();
    } catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
    if ($n>$max){header('Retry-After: 900');ca_fail(429,'rate_limited','Слишком много попыток. Повторите через 15 минут.');}
}
function ca_event(string $event,?int $account=null,?int $admin=null):void {
    db()->prepare('INSERT INTO nd_customer_auth_events(account_id,actor_admin_id,event,created_at) VALUES (?,?,?,?)')->execute([$account,$admin,$event,time()]);
}
function ca_cookie_name():string {return parse_url(config()['app_url'],PHP_URL_SCHEME)==='https'?'__Host-nd_customer':'nd_customer';}
function ca_cookie(string $raw,int $expiry):void {
    setcookie(ca_cookie_name(),$raw,['expires'=>$expiry,'path'=>'/','secure'=>parse_url(config()['app_url'],PHP_URL_SCHEME)==='https','httponly'=>true,'samesite'=>'Strict']);
}
function ca_csrf(string $raw):string {return hash_hmac('sha256','customer-csrf-v1',$raw);}
function ca_session(bool $write=false):array {
    $raw=$_COOKIE[ca_cookie_name()]??'';
    if (!is_string($raw)||!preg_match('/^[a-f0-9]{64}$/D',$raw))ca_fail(401,'session_expired','Войдите в кабинет заново.');
    $q=db()->prepare('SELECT * FROM nd_customer_sessions WHERE token_hash=? AND expires_at>?');$q->execute([hash('sha256',$raw),time()]);$row=$q->fetch();
    if (!$row)ca_fail(401,'session_expired','Войдите в кабинет заново.');
    if ($write) {
        same_origin();$csrf=$_SERVER['HTTP_X_CSRF_TOKEN']??'';
        if (!is_string($csrf)||!hash_equals($row['csrf_hash'],hash('sha256',$csrf)))ca_fail(403,'csrf_invalid','Обновите страницу и повторите действие.');
    }
    $row['csrf']=ca_csrf($raw);return $row;
}
function ca_new_session(?int $account,?string $old=null):array {
    $raw=bin2hex(random_bytes(32));$csrf=ca_csrf($raw);$expiry=time()+($account===null?1800:28800);
    if ($old!==null) db()->prepare('DELETE FROM nd_customer_sessions WHERE token_hash=?')->execute([$old]);
    db()->prepare('DELETE FROM nd_customer_sessions WHERE expires_at<=?')->execute([time()]);
    db()->prepare('INSERT INTO nd_customer_sessions(token_hash,csrf_hash,account_id,created_at,expires_at) VALUES (?,?,?,?,?)')->execute([hash('sha256',$raw),hash('sha256',$csrf),$account,time(),$expiry]);
    return ['raw'=>$raw,'csrf'=>$csrf,'expiry'=>$expiry];
}
function ca_account(int $id,bool $lock=false):array|false {
    $q=db()->prepare('SELECT a.*,c.status AS customer_status,c.name,h.email_verified_at,h.registration_method,h.policy_version,h.policy_hash FROM nd_customer_accounts a JOIN nd_customers c ON c.id=a.customer_id JOIN nd_customer_auth h ON h.account_id=a.id WHERE a.id=?'.($lock?' FOR UPDATE':''));$q->execute([$id]);return $q->fetch();
}
function ca_account_allowed(array|false $a):bool {return $a && $a['status']==='active'&&$a['customer_status']==='active'&&$a['email_verified_at']!==null;}
function ca_current_consent(array $a):bool {$p=privacy_settings();return $p['enabled']&&$a['policy_version']===$p['version']&&hash_equals($p['hash'],$a['policy_hash']);}
function ca_record_consent(int $id,array $p,string $purpose):void {
    db()->prepare('UPDATE nd_customer_auth SET consent_at=?,policy_version=?,policy_hash=? WHERE account_id=?')->execute([time(),$p['version'],$p['hash'],$id]);
    db()->prepare('INSERT INTO nd_customer_consents(account_id,consent,consent_at,policy_version,policy_hash,purpose) VALUES (?,1,?,?,?,?)')->execute([$id,time(),$p['version'],$p['hash'],$purpose]);
}
function ca_issue(int $id,string $purpose,?int $admin=null):string {
    $raw=bin2hex(random_bytes(32));$now=time();$ttl=['verify'=>86400,'invite'=>172800,'reset'=>1800][$purpose];
    db()->prepare('UPDATE nd_customer_tokens SET used_at=? WHERE account_id=? AND purpose=? AND used_at IS NULL')->execute([$now,$id,$purpose]);
    db()->prepare('INSERT INTO nd_customer_tokens(token_hash,account_id,purpose,created_at,expires_at,issuer_admin_id) VALUES (?,?,?,?,?,?)')->execute([hash('sha256',$raw),$id,$purpose,$now,$now+$ttl,$admin]);return $raw;
}
function ca_send(int $id,string $email,string $purpose,string $raw):void {
    $accepted=customer_mail($email,$purpose,$raw);
    ca_event($accepted?'mail_accepted':'mail_failed',$id);
    if (!$accepted)error_log('NeuroDelo {"event":"customer_mail_failed"}');
}
function ca_neutral():never {json_response(['ok'=>true,'message'=>'Если действие доступно для этого адреса, письмо будет отправлено. Проверьте почту и папку «Спам». При отсутствии письма повторите запрос позже.'],202);}
function ca_transaction(callable $action):mixed {
    $pdo=db();$pdo->beginTransaction();
    try{$result=$action();$pdo->commit();return $result;}catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
}
function ca_token(array $data):string {
    $token=$data['token']??'';
    if(!is_string($token)||!preg_match('/^[a-f0-9]{64}$/D',$token))ca_fail(422,'invalid_token','Ссылка недействительна или срок её действия истёк. Запросите новую.');
    return hash('sha256',$token);
}
function ca_consume(array $data,string $purpose,?string $newPassword=null,?array $consent=null):void {
    $hash=ca_token($data);
    // All account operations lock account before token: stable ordering for consume/reissue/disable.
    $q=db()->prepare('SELECT account_id FROM nd_customer_tokens WHERE token_hash=? AND purpose=?');$q->execute([$hash,$purpose]);$id=$q->fetchColumn();
    if(!$id)ca_fail(422,'invalid_token','Ссылка недействительна или срок её действия истёк.');
    ca_transaction(function()use($id,$hash,$purpose,$newPassword,$consent){
        $a=ca_account((int)$id,true);
        $q=db()->prepare('SELECT * FROM nd_customer_tokens WHERE token_hash=? AND purpose=? FOR UPDATE');$q->execute([$hash,$purpose]);$t=$q->fetch();
        if (!$t||$t['used_at']!==null||(int)$t['expires_at']<=time()||!$a||$a['status']==='disabled'||$a['customer_status']!=='active')ca_fail(422,'invalid_token','Ссылка недействительна или срок её действия истёк.');
        if (($purpose==='reset'&&!ca_account_allowed($a))||($purpose==='invite'&&($a['registration_method']!=='invitation'||$a['email_verified_at']!==null))||($purpose==='verify'&&($a['registration_method']!=='self'||$a['email_verified_at']!==null)))ca_fail(422,'invalid_token','Ссылка недействительна или уже использована.');
        db()->prepare('UPDATE nd_customer_tokens SET used_at=? WHERE token_hash=?')->execute([time(),$hash]);
        if($purpose==='verify') {
            // Verification does not silently accept a changed legal document.
            if(!ca_current_consent($a))ca_record_consent((int)$id,$consent,'reconsent');
            db()->prepare('UPDATE nd_customer_auth SET email_verified_at=? WHERE account_id=?')->execute([time(),$id]);
            db()->prepare("UPDATE nd_customer_accounts SET status='active',version=version+1 WHERE id=?")->execute([$id]);
        } else {
            db()->prepare("UPDATE nd_customer_accounts SET password_hash=?,status='active',version=version+1 WHERE id=?")->execute([$newPassword,$id]);
            if($purpose==='invite'){
                db()->prepare('UPDATE nd_customer_auth SET email_verified_at=? WHERE account_id=?')->execute([time(),$id]);ca_record_consent((int)$id,$consent,'invitation');
            }
            db()->prepare('DELETE FROM nd_customer_sessions WHERE account_id=?')->execute([$id]);
            db()->prepare('UPDATE nd_customer_tokens SET used_at=? WHERE account_id=? AND used_at IS NULL')->execute([time(),$id]);
        }
        ca_event($purpose.'_completed',(int)$id);
    });
}
function ca_dispatch(string $route,string $method):never {
    if($route==='settings'&&$method==='GET'){
        $p=privacy_settings();unset($p['hash']);json_response(['enabled'=>ca_enabled(),'policy'=>$p]);
    }
    ca_gate();
    ca_rate('ip',120,$_SERVER['REMOTE_ADDR']??'unknown');
    if(str_starts_with($route,'collab/')){require_once __DIR__.'/collab/routes.php';cc_dispatch(true,substr($route,7),$method);}
    if(str_starts_with($route,'portal/')){require_once __DIR__.'/crm/portal.php';crm_portal($route,$method);}
    if(str_starts_with($route,'owner/')) {ca_owner($route,$method);}
    if($route==='session'&&$method==='GET'){
        try{$s=ca_session();}catch(CustomerFailure $e){if($e->status!==401)throw $e;$new=ca_new_session(null);ca_cookie($new['raw'],$new['expiry']);json_response(['ok'=>true,'authenticated'=>false,'csrf'=>$new['csrf']]);}
        if($s['account_id']===null)json_response(['ok'=>true,'authenticated'=>false,'csrf'=>$s['csrf']]);
        $a=ca_account((int)$s['account_id']);
        if(!ca_account_allowed($a)){$new=ca_new_session(null,$s['token_hash']);ca_cookie($new['raw'],$new['expiry']);json_response(['ok'=>true,'authenticated'=>false,'csrf'=>$new['csrf']]);}
        if(!ca_current_consent($a))json_response(['ok'=>true,'authenticated'=>false,'csrf'=>$s['csrf'],'needs_consent'=>true]);
        json_response(['ok'=>true,'authenticated'=>true,'csrf'=>$s['csrf'],'account'=>['id'=>(int)$a['id'],'name'=>$a['name'],'email'=>$a['email']]]);
    }
    if($method!=='POST')ca_fail(404,'not_found','Не найдено.');
    $s=ca_session(true);$d=input();ca_rate($route,20,$_SERVER['REMOTE_ADDR']??'unknown');
    if($route==='logout'){
        db()->prepare('DELETE FROM nd_customer_sessions WHERE token_hash=?')->execute([$s['token_hash']]);ca_cookie('',time()-3600);json_response(['ok'=>true]);
    }
    if(in_array($route,['register','login','forgot','resend'],true)){$email=ca_email($d);ca_rate('identity:'.$route,8,$email);}
    if($route==='register'){
        $name=field($d,'name',190);$password=ca_password($d);$p=ca_consent($d);$hash=password_hash($password,PASSWORD_DEFAULT);
        try{
            $pending=ca_transaction(function()use($name,$email,$hash,$p){
                $q=db()->prepare('SELECT id FROM nd_customer_accounts WHERE email=? FOR UPDATE');$q->execute([$email]);
                if($q->fetchColumn()!==false)return null;
                db()->prepare('INSERT INTO nd_customers(name,email) VALUES (?,?)')->execute([$name,$email]);$customer=(int)db()->lastInsertId();
                db()->prepare('INSERT INTO nd_customer_accounts(customer_id,email,password_hash) VALUES (?,?,?)')->execute([$customer,$email,$hash]);$id=(int)db()->lastInsertId();
                db()->prepare("INSERT INTO nd_customer_auth(account_id,registration_method,consent_at,policy_version,policy_hash) VALUES (?,'self',?,?,?)")->execute([$id,time(),$p['version'],$p['hash']]);
                ca_record_consent($id,$p,'registration');ca_event('registered',$id);return [$id,ca_issue($id,'verify')];
            });
        }catch(PDOException $e){if(!in_array($e->errorInfo[1]??0,[1062,1213],true))throw $e;$pending=null;}
        if($pending)ca_send($pending[0],$email,'verify',$pending[1]);ca_neutral();
    }
    if($route==='login'){
        $password=$d['password']??'';
        if(!is_string($password)||strlen($password)>72||str_contains($password,"\0"))ca_fail(401,'login_failed','Не удалось войти. Проверьте данные и подтверждение email.');
        $q=db()->prepare('SELECT id,password_hash FROM nd_customer_accounts WHERE email=?');$q->execute([$email]);$identity=$q->fetch();
        // Public dummy bcrypt hash is only timing padding, never a production password.
        $dummy='$2y$12$92IXUNpkjO0rOQ5byMi.Ye4oKoEa3Ro9llC/.og/at2uheWG/igi.';
        $valid=password_verify($password,$identity['password_hash']??$dummy);
        $new=ca_transaction(function()use($identity,$valid,$d,$s){
            $a=$identity?ca_account((int)$identity['id'],true):false;
            // Re-verify if a password reset raced the initial hash read.
            if(!$valid||!ca_account_allowed($a)||!hash_equals($identity['password_hash']??'',$a['password_hash']??''))ca_fail(401,'login_failed','Не удалось войти. Проверьте данные и подтверждение email.');
            if(!ca_current_consent($a))ca_record_consent((int)$a['id'],ca_consent($d),'reconsent');
            db()->prepare('UPDATE nd_customer_accounts SET last_login_at=UTC_TIMESTAMP() WHERE id=?')->execute([$a['id']]);
            ca_event('login',(int)$a['id']);return ca_new_session((int)$a['id'],$s['token_hash']);
        });
        ca_cookie($new['raw'],$new['expiry']);json_response(['ok'=>true,'csrf'=>$new['csrf']]);
    }
    if($route==='forgot'||$route==='resend'){
        $q=db()->prepare('SELECT id FROM nd_customer_accounts WHERE email=?');$q->execute([$email]);$id=$q->fetchColumn();
        $purpose=$route==='forgot'?'reset':'verify';
        $raw=$id?ca_transaction(function()use($id,$purpose){
            $a=ca_account((int)$id,true);
            $eligible=$purpose==='reset'?ca_account_allowed($a):($a&&$a['status']==='invited'&&$a['customer_status']==='active'&&$a['email_verified_at']===null&&$a['registration_method']==='self');
            return $eligible?ca_issue((int)$id,$purpose):null;
        }):null;
        if($raw)ca_send((int)$id,$email,$purpose,$raw);ca_neutral();
    }
    if(in_array($route,['verify','invite','reset'],true)){
        $hashedPassword=$route==='verify'?null:password_hash(ca_password($d),PASSWORD_DEFAULT);
        $p=in_array($route,['invite','verify'],true)?ca_consent($d):null;
        ca_consume($d,$route,$hashedPassword,$p);json_response(['ok'=>true]);
    }
    ca_fail(404,'not_found','Не найдено.');
}
function ca_owner(string $route,string $method):never {
    current_session($method!=='GET');ca_rate('owner',30,$_SERVER['REMOTE_ADDR']??'unknown');
    if($route==='owner/accounts'&&$method==='GET'){
        $rows=db()->query("SELECT a.id,a.customer_id,a.email,a.status,a.version,c.name,h.email_verified_at,(SELECT e.event FROM nd_customer_auth_events e WHERE e.account_id=a.id AND e.event IN ('mail_accepted','mail_failed') ORDER BY e.id DESC LIMIT 1) AS mail_status FROM nd_customer_accounts a JOIN nd_customers c ON c.id=a.customer_id LEFT JOIN nd_customer_auth h ON h.account_id=a.id ORDER BY a.id DESC LIMIT 200")->fetchAll();
        foreach($rows as &$row){foreach(['id','customer_id','version'] as $k)$row[$k]=(int)$row[$k];$row['verified']=$row['email_verified_at']!==null;unset($row['email_verified_at']);}unset($row);
        json_response(['ok'=>true,'accounts'=>$rows]);
    }
    if($method!=='POST')ca_fail(404,'not_found','Не найдено.');$d=input();
    if($route==='owner/invite'){
        $email=ca_email($d);ca_rate('invitation_identity',5,$email);$customer=$d['customer_id']??null;
        if($customer!==null&&(!is_int($customer)||$customer<1))ca_fail(422,'invalid_customer','Выберите корректного клиента.');
        $name=$customer===null?field($d,'name',190):'';
        $pending=ca_transaction(function()use($email,$customer,$name){
            $q=db()->prepare('SELECT id FROM nd_customer_accounts WHERE email=? FOR UPDATE');$q->execute([$email]);$existing=$q->fetchColumn();
            if($existing){$a=ca_account((int)$existing,true);return ($a&&$customer!==null&&(int)$a['customer_id']===$customer&&$a['status']==='invited'&&$a['registration_method']==='invitation'&&$a['customer_status']==='active')?[(int)$existing,ca_issue((int)$existing,'invite',1)]:null;}
            if($customer!==null){$q=db()->prepare("SELECT id FROM nd_customers WHERE id=? AND status='active' FOR UPDATE");$q->execute([$customer]);if(!$q->fetchColumn())ca_fail(422,'invalid_customer','Клиент недоступен.');}
            else{db()->prepare('INSERT INTO nd_customers(name,email) VALUES (?,?)')->execute([$name,$email]);$customer=(int)db()->lastInsertId();}
            db()->prepare('INSERT INTO nd_customer_accounts(customer_id,email) VALUES (?,?)')->execute([$customer,$email]);$id=(int)db()->lastInsertId();
            db()->prepare("INSERT INTO nd_customer_auth(account_id,registration_method,consent_at,policy_version,policy_hash) VALUES (?,'invitation',0,'','')")->execute([$id]);
            ca_event('invited',$id,1);return [$id,ca_issue($id,'invite',1)];
        });
        if($pending)ca_send($pending[0],$email,'invite',$pending[1]);ca_neutral();
    }
    if($route==='owner/lifecycle'){
        $id=$d['account_id']??null;$version=$d['version']??null;$action=$d['action']??'';
        if(!is_int($id)||$id<1||!is_int($version)||!in_array($action,['disable','enable','revoke_sessions'],true))ca_fail(422,'invalid_action','Проверьте выбранное действие.');
        $next=ca_transaction(function()use($id,$version,$action){
            $q=db()->prepare('SELECT * FROM nd_customer_accounts WHERE id=? FOR UPDATE');$q->execute([$id]);$a=$q->fetch();
            if(!$a)ca_fail(404,'not_found','Аккаунт не найден.');
            if((int)$a['version']!==$version)ca_fail(409,'version_conflict','Аккаунт изменён. Обновите список.');
            $auth=ca_account($id);
            if($action==='enable'&&(!$auth||$auth['email_verified_at']===null||$a['password_hash']===null||$auth['customer_status']!=='active'))ca_fail(422,'activation_forbidden','Сначала клиент должен подтвердить email и завершить регистрацию.');
            $status=$action==='disable'?'disabled':($action==='enable'?'active':$a['status']);
            db()->prepare('UPDATE nd_customer_accounts SET status=?,version=version+1 WHERE id=?')->execute([$status,$id]);
            db()->prepare('DELETE FROM nd_customer_sessions WHERE account_id=?')->execute([$id]);
            if($action==='disable')db()->prepare('UPDATE nd_customer_tokens SET used_at=? WHERE account_id=? AND used_at IS NULL')->execute([time(),$id]);
            ca_event($action,$id,1);return $version+1;
        });json_response(['ok'=>true,'version'=>$next]);
    }
    ca_fail(404,'not_found','Не найдено.');
}
