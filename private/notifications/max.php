<?php
declare(strict_types=1);
/** Private runtime secrets/state are separate from versioned deployment files. */
function max_dir(): string {
    $dir=__DIR__.'/runtime';
    if (is_link($dir) || (file_exists($dir)&&!is_dir($dir)))throw new RuntimeException('max_storage_unsafe');
    if (!is_dir($dir)&&!@mkdir($dir,0700)&&!is_dir($dir))throw new RuntimeException('max_storage_unavailable');
    @chmod($dir,0700);return $dir;
}
function max_locked(callable $callback,bool $blocking=true): mixed {
    $dir=max_dir();$lock=$dir.'/lock';
    if (is_link($lock))throw new RuntimeException('max_storage_unsafe');
    $h=@fopen($lock,'c');if(!$h)throw new RuntimeException('max_storage_unavailable');@chmod($lock,0600);
    if(!flock($h,LOCK_EX|($blocking?0:LOCK_NB))){fclose($h);return null;}
    try{return $callback();}finally{flock($h,LOCK_UN);fclose($h);}
}
function max_read(): array {
    $p=max_dir().'/state.json';if(is_link($p))throw new RuntimeException('max_storage_unsafe');
    if(!is_file($p))return [];
    $raw=@file_get_contents($p);$v=$raw===false?null:json_decode($raw,true);
    if(!is_array($v))throw new RuntimeException('max_state_invalid');return $v;
}
function max_write(array $v): void {
    $p=max_dir().'/state.json';if(is_link($p))throw new RuntimeException('max_storage_unsafe');
    $tmp=max_dir().'/'.bin2hex(random_bytes(16)).'.tmp';
    $h=@fopen($tmp,'x');if(!$h)throw new RuntimeException('max_storage_unavailable');
    try{chmod($tmp,0600);$s=json_encode($v,JSON_THROW_ON_ERROR);if(fwrite($h,$s)!==strlen($s))throw new RuntimeException('max_state_write_failed');fflush($h);fclose($h);$h=null;if(!rename($tmp,$p))throw new RuntimeException('max_state_write_failed');}
    finally{if(is_resource($h))fclose($h);if(is_file($tmp))unlink($tmp);}
}
function max_http(string $method,string $path,string $token,?array $body=null): array {
    // Fixed host, bounded I/O, no redirects, TLS verification stays enabled.
    if (!preg_match('/^[A-Za-z0-9._:-]{20,512}$/D',$token))throw new RuntimeException('max_invalid_token');
    if (!preg_match('#^/(me|subscriptions|messages\?user_id=[1-9][0-9]{0,18}&disable_link_preview=true)$#D',$path))throw new RuntimeException('max_invalid_api_path');
    $options=['http'=>['method'=>$method,'header'=>"Authorization: ".$token."\r\nContent-Type: application/json\r\n",'timeout'=>4,'ignore_errors'=>true,'follow_location'=>0,'max_redirects'=>0],
        'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'allow_self_signed'=>false]];
    if($body!==null)$options['http']['content']=json_encode($body,JSON_THROW_ON_ERROR|JSON_UNESCAPED_UNICODE);
    $context=stream_context_create($options);$stream=@fopen('https://platform-api2.max.ru'.$path,'rb',false,$context);
    if(!$stream)throw new RuntimeException('max_connection_failed');
    try{$meta=stream_get_meta_data($stream);$raw=stream_get_contents($stream,131073);}finally{fclose($stream);}
    $status=0;foreach($meta['wrapper_data']??[] as $line)if(preg_match('#^HTTP/\S+ ([0-9]{3})#',$line,$m))$status=(int)$m[1];
    if($status===401||$status===403)throw new RuntimeException('max_auth_failed');
    if($status===429)throw new RuntimeException('max_rate_limited');
    if($status!==200||$raw===false||strlen($raw)>131072)throw new RuntimeException('max_api_failed');
    $data=json_decode($raw,true);if(!is_array($data))throw new RuntimeException('max_invalid_response');return $data;
}
function max_status(): array {
    return max_locked(function(){
        $s=max_read();$connected=isset($s['user_id'])&&($s['enabled']??false)===true;
        $pending=0;if($connected){$q=db()->prepare('SELECT COUNT(*) FROM nd_leads WHERE id>?');$q->execute([$s['cursor']??0]);$pending=(int)$q->fetchColumn();}
        return ['configured'=>isset($s['token']),'connected'=>$connected,'bot_username'=>$s['bot_username']??'',
            'pending'=>$pending,'last_sent_at'=>$s['last_sent_at']??null,'error_code'=>$s['error_code']??''];
    });
}
function max_connect(string $token,?callable $http=null): array {
    $http??='max_http';$me=$http('GET','/me',$token,null);
    if(($me['is_bot']??false)!==true||!is_int($me['user_id']??null)||!preg_match('/^[A-Za-z0-9_]{1,64}$/D',$me['username']??''))throw new RuntimeException('max_invalid_bot');
    return max_locked(function()use($token,$me,$http){
        $s=max_read();$prior=$s;
        $pair=bin2hex(random_bytes(16));
        $s=['token'=>$token,'webhook_secret'=>bin2hex(random_bytes(32)),'bot_username'=>$me['username'],
            'pair_hash'=>hash('sha256',$pair),'pair_expires'=>time()+900,'enabled'=>false];
        // Persist the secret before registration: MAX may validate the webhook immediately.
        max_write($s);
        try{$result=$http('POST','/subscriptions',$token,['url'=>'https://neurodelo.pro/max-webhook.php','update_types'=>['message_created'],'secret'=>$s['webhook_secret']]);
            if(($result['success']??false)!==true)throw new RuntimeException('max_subscription_failed');
        }catch(Throwable $e){max_write($prior);throw $e;}
        return ['ok'=>true,'command'=>'/connect '.$pair,'bot_url'=>'https://max.ru/'.$s['bot_username']];
    });
}
function max_webhook(array $event,string $secret): void {
    max_locked(function()use($event,$secret){
        $s=max_read();
        if(!is_string($s['webhook_secret']??null)||!hash_equals($s['webhook_secret'],$secret))fail(403,'Недопустимый запрос');
        if(($event['update_type']??'')!=='message_created')return;
        $m=$event['message']??[];$sender=$m['sender']??[];$text=$m['body']['text']??'';
        if(($m['recipient']['chat_type']??'')!=='dialog'||($sender['is_bot']??true)!==false||!is_int($sender['user_id']??null)||$sender['user_id']<1)return;
        if(!is_string($text)||!preg_match('/^\/connect ([a-f0-9]{32})$/D',trim($text),$match))return;
        if(($s['pair_expires']??0)<time()||!isset($s['pair_hash'])||!hash_equals($s['pair_hash'],hash('sha256',$match[1])))return;
        $s['pending_user_id']=$sender['user_id'];unset($s['pair_hash'],$s['pair_expires']);max_write($s);
    });
}
function max_confirm(?callable $http=null): void {
    $http??='max_http';max_locked(function()use($http){$s=max_read();if(!isset($s['pending_user_id']))throw new RuntimeException('max_pair_missing');
        // Only after an actual successful test message do we enable new lead notifications.
        $result=$http('POST','/messages?user_id='.$s['pending_user_id'].'&disable_link_preview=true',$s['token'],['text'=>'НейроДело: уведомления подключены. Новые заявки будут приходить сюда.','notify'=>true]);
        if(!isset($result['message']['body']['mid']))throw new RuntimeException('max_invalid_response');
        $s['user_id']=$s['pending_user_id'];unset($s['pending_user_id']);$s['enabled']=true;
        $s['cursor']=(int)db()->query('SELECT COALESCE(MAX(id),0) FROM nd_leads')->fetchColumn();$s['last_sent_at']=time();$s['error_code']='';max_write($s);
    });
}
function max_pending_pair(): bool {return max_locked(fn()=>isset(max_read()['pending_user_id']));}
function max_pump(int $limit=1,?callable $http=null): array {
    $http??='max_http';$limit=max(1,min($limit,10));
    return max_locked(function()use($limit,$http){$s=max_read();$sent=0;
        if(($s['enabled']??false)!==true||!isset($s['user_id']))return ['ok'=>true,'sent'=>0,'configured'=>false];
        if(($s['retry_at']??0)>time())return ['ok'=>true,'sent'=>0,'deferred'=>true];
        $q=db()->prepare('SELECT id FROM nd_leads WHERE id>? ORDER BY id LIMIT '.$limit);$q->execute([$s['cursor']??0]);$ids=$q->fetchAll(PDO::FETCH_COLUMN);
        foreach($ids as $id){
            if($sent)usleep(550000);
            try{$response=$http('POST','/messages?user_id='.$s['user_id'].'&disable_link_preview=true',$s['token'],['text'=>'Новая заявка №'.$id.' на НейроДело.','notify'=>true,'attachments'=>[['type'=>'inline_keyboard','payload'=>['buttons'=>[[['type'=>'link','text'=>'Открыть кабинет','url'=>'https://neurodelo.pro/studio.php']]]]]]]);
                if(!isset($response['message']['body']['mid']))throw new RuntimeException('max_invalid_response');
                $s['cursor']=(int)$id;$s['last_sent_at']=time();$s['error_code']='';$s['failures']=0;unset($s['retry_at']);max_write($s);$sent++;
            }catch(Throwable $e){$s['error_code']=in_array($e->getMessage(),['max_connection_failed','max_auth_failed','max_rate_limited','max_api_failed','max_invalid_response'],true)?$e->getMessage():'max_delivery_failed';$s['failures']=min(10,($s['failures']??0)+1);$s['retry_at']=time()+min(3600,30*(2**$s['failures']));max_write($s);break;}
        }
        return ['ok'=>true,'sent'=>$sent,'error_code'=>$s['error_code']??''];
    },false)??['ok'=>true,'busy'=>true,'sent'=>0];
}
function max_after_lead(): void {
    try{max_pump();}catch(Throwable $e){error_log('NeuroDelo {"event":"max_notification_deferred"}');}
}
