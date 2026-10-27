<?php
declare(strict_types=1);
require dirname(__DIR__).'/private/app.php';
require dirname(__DIR__).'/private/notifications/max.php';
security_headers();
header('Cache-Control: no-store');header('X-Robots-Tag: noindex, nofollow');
try {
    $route=$_GET['r'] ?? ''; $method=$_SERVER['REQUEST_METHOD'];
    if(!is_string($route)) fail(404,'Не найдено');
    if($route==='privacy' && $method==='GET') {
        $policy=privacy_settings();unset($policy['hash']);json_response($policy);
    }
    if($route==='notifications/max' && $method==='GET') {
        current_session();$status=max_status();$status['pair_received']=max_pending_pair();json_response($status);
    }
    if($route==='notifications/max' && $method==='POST') {
        current_session(true);$data=input();rate('max-settings',20);
        try {
            if(($data['action']??'')==='connect') {
                $token=$data['token']??'';
                if(!is_string($token)||!preg_match('/^[A-Za-z0-9._:-]{20,512}$/D',$token))fail(422,'Проверьте токен бота');
                json_response(max_connect($token));
            }
            if(($data['action']??'')==='confirm'){max_confirm();json_response(['ok'=>true]);}
            if(($data['action']??'')==='retry'){max_pump();json_response(['ok'=>true]);}
            if(($data['action']??'')==='disable'){max_locked(function(){$s=max_read();$s['enabled']=false;unset($s['pending_user_id'],$s['pair_hash'],$s['pair_expires']);max_write($s);});json_response(['ok'=>true]);}
            fail(422,'Неизвестное действие');
        }catch(RuntimeException $e){fail(502,'Не удалось подключиться к MAX. Проверьте токен и повторите позже.','max_connection_error');}
    }
    if($route==='login' && $method==='POST') {
        same_origin();rate('login',10);$data=input();
        $password=$data['password'] ?? '';
        if(!is_string($password) || strlen($password)>256 || $password==='')fail(422,'Введите пароль');
        $hash=db()->query('SELECT password_hash FROM nd_admin WHERE id=1')->fetchColumn();
        if(!$hash)fail(503,'Вход ещё не настроен владельцем сайта');
        if(!password_verify($password,$hash))fail(401,'Неверный пароль');
        if(password_needs_rehash($hash,PASSWORD_DEFAULT))db()->prepare('UPDATE nd_admin SET password_hash=? WHERE id=1')->execute([password_hash($password,PASSWORD_DEFAULT)]);
        $token=bin2hex(random_bytes(32));$csrf=bin2hex(random_bytes(32));
        $old=$_COOKIE['nd_session'] ?? '';
        db()->prepare('DELETE FROM nd_sessions WHERE expires<=? OR token=?')->execute([time(),hash('sha256',is_string($old)?$old:'')]);
        db()->prepare('INSERT INTO nd_sessions VALUES (?,?,?)')->execute([hash('sha256',$token),$csrf,time()+28800]);
        session_cookie($token,time()+28800);json_response(['csrf'=>$csrf]);
    }
    if($route==='session' && $method==='GET') { $s=current_session();json_response(['csrf'=>$s['csrf'],'statuses'=>statuses()]); }
    if($route==='logout' && $method==='POST') { $s=current_session(true);db()->prepare('DELETE FROM nd_sessions WHERE token=?')->execute([$s['token']]);session_cookie('',time()-3600);json_response(['ok'=>true]); }
    if($route==='leads' && $method==='POST') {
        same_origin();$data=input();
        $values=[field($data,'name',100),field($data,'contact',200),field($data,'service',100),field($data,'idea',5000)];
        if(!valid_contact($values[1]))fail(422,'Укажите корректный email, Telegram @username (5–32 символа) телефон РФ в формате +7/8 и 10 цифр или ссылку профиля MAX.','invalid_contact');
        if(!in_array($values[2],['Сайт или лендинг','ИИ-агент','Веб-приложение','Другая идея'],true))fail(422,'Выберите услугу из списка','invalid_service');
        $key=$data['idempotency_key'] ?? '';
        if(!is_string($key) || !preg_match('/^[a-f0-9]{64}$/D',$key))fail(422,'Не удалось проверить отправку. Обновите страницу и повторите попытку.');
        $policy=privacy_settings();
        if(!$policy['enabled'])fail(503,'Политика ещё не опубликована','privacy_unavailable');
        if(($data['consent'] ?? null)!==true)fail(422,'Подтвердите согласие на обработку данных','consent_required');
        if(($data['policy_version'] ?? '')!==$policy['version'])fail(409,'Политика обновлена. Прочитайте её и подтвердите согласие заново.','policy_changed');
        $hash=hash('sha256',json_encode([...$values,true,$policy['version'],$policy['hash']],JSON_UNESCAPED_UNICODE|JSON_THROW_ON_ERROR));
        $replay=function() use($key,$hash): void {
            $q=db()->prepare('SELECT id,request_hash FROM nd_leads WHERE request_key=?');$q->execute([$key]);$row=$q->fetch();
            if($row) {
                if(!hash_equals($row['request_hash'],$hash))fail(409,'Этот запрос уже использован для другой заявки. Отправьте изменённую заявку заново.','idempotency_conflict');
                max_after_lead();json_response(['ok'=>true,'lead_id'=>(int)$row['id']],201);
            }
        };
        $replay();rate('lead',20);
        try {
            db()->prepare("INSERT INTO nd_leads (name,contact,service,idea,notes,created,request_key,request_hash,consent,consent_at,policy_version,policy_hash) VALUES (?,?,?,?,'',?,?,?,1,?,?,?)")->execute([...$values,time(),$key,$hash,time(),$policy['version'],$policy['hash']]);
        } catch(PDOException $e) {
            if($e->getCode()==='23000')$replay();
            throw $e;
        }
        $leadId=(int)db()->lastInsertId();max_after_lead();json_response(['ok'=>true,'lead_id'=>$leadId],201);
    }
    if($route==='leads' && $method==='GET') {
        current_session();$rows=db()->query('SELECT * FROM nd_leads ORDER BY id DESC')->fetchAll();
        foreach($rows as &$row){$row['id']=(int)$row['id'];$row['created']=(int)$row['created'];$row['version']=(int)$row['version'];if($row['consent_at']!==null)$row['consent_at']=(int)$row['consent_at'];if($row['consent']!==null)$row['consent']=(int)$row['consent'];}unset($row);
        json_response($rows);
    }
    if(preg_match('~^leads/([1-9][0-9]*)$~D',$route,$match) && $method==='PATCH') {
        current_session(true);$data=input();$status=field($data,'status',30);
        if(!in_array($status,statuses(),true))fail(422,'Неизвестный статус');
        $notes=field($data,'notes',10000,false);$next=field($data,'next_step',500,false);
        $version=$data['version'] ?? null;
        if(!is_int($version) || $version<1)fail(422,'Обновите заявку перед сохранением');
        $q=db()->prepare('UPDATE nd_leads SET status=?,notes=?,next_step=?,version=version+1 WHERE id=? AND version=?');
        $q->execute([$status,$notes,$next,$match[1],$version]);
        if($q->rowCount()!==1) {
            $exists=db()->prepare('SELECT id FROM nd_leads WHERE id=?');$exists->execute([$match[1]]);
            if(!$exists->fetch())fail(404,'Заявка не найдена');
            fail(409,'Заявка изменена в другой вкладке. Загрузите актуальные данные и проверьте изменения. Ваши правки пока не сохранены.');
        }
        json_response(['ok'=>true,'version'=>$version+1]);
    }
    fail(404,'Не найдено');
} catch(Throwable $e){server_error($e);}
