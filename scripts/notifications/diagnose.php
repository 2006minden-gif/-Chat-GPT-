<?php
declare(strict_types=1);
/** Read-only MAX checks. Never emit tokens, recipient IDs, messages or webhook URLs. */
function max_delivery_diagnostic(array $state, callable $request): array {
    $out=['configured'=>isset($state['token']),'enabled'=>($state['enabled']??false)===true,
        'owner_bound'=>isset($state['user_id']),'stored_error'=>in_array($state['error_code']??'',
            ['max_connection_failed','max_auth_failed','max_rate_limited','max_api_failed','max_invalid_response','max_delivery_failed'],true)?$state['error_code']:''];
    if(!isset($state['token']))return $out;
    foreach(['/me','/subscriptions'] as $path){
        $key=$path==='/me'?'identity':'subscriptions';
        try{
            $data=$request('GET',$path,$state['token'],null);
            $out[$key]='ok';
            if($path==='/me'){
                $out['is_bot']=($data['is_bot']??false)===true;
                $out['stored_bot_matches']=is_string($data['username']??null)&&is_string($state['bot_username']??null)&&hash_equals($state['bot_username'],$data['username']);
            }else{
                $subscriptions=$data['subscriptions']??[];
                $out['subscription_count']=is_array($subscriptions)?count($subscriptions):0;
                $out['site_webhook_present']=false;$hosts=[];
                foreach(is_array($subscriptions)?$subscriptions:[] as $sub){
                    $url=$sub['url']??'';
                    if(!is_string($url))continue;
                    if($url==='https://neurodelo.pro/max-webhook.php')$out['site_webhook_present']=true;
                    $host=parse_url($url,PHP_URL_HOST);
                    if(is_string($host)&&preg_match('/^[a-zA-Z0-9.-]{1,253}$/D',$host))$hosts[]=strtolower($host);
                }
                $out['webhook_hosts']=array_values(array_unique($hosts));
            }
        }catch(Throwable $e){
            $out[$key]=in_array($e->getMessage(),['max_connection_failed','max_auth_failed','max_rate_limited','max_api_failed','max_invalid_response'],true)?$e->getMessage():'diagnostic_failed';
        }
    }
    return $out;
}
function max_network_diagnostic():array {
    $out=[];
    // Public, unauthenticated probes only. No token is sent to alternative hosts.
    foreach(['platform-api2.max.ru','platform-api.max.ru','botapi.max.ru'] as $host){
        $row=['dns_ipv4_count'=>count(@gethostbynamel($host)?:[])];
        $context=stream_context_create(['http'=>['timeout'=>5,'ignore_errors'=>true,'follow_location'=>0,'max_redirects'=>0],
            'ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'allow_self_signed'=>false]]);
        $warning='';
        set_error_handler(static function(int $level,string $message)use(&$warning):bool{$warning=$message;return true;});
        try{$stream=fopen('https://'.$host.'/me','rb',false,$context);}finally{restore_error_handler();}
        if($stream){
            $meta=stream_get_meta_data($stream);fclose($stream);$row['http_status']=0;
            foreach($meta['wrapper_data']??[] as $line)if(preg_match('#^HTTP/\S+ ([0-9]{3})#',$line,$m))$row['http_status']=(int)$m[1];
        }else{
            $row['connection']='failed';
            $row['failure_kind']=preg_match('/getaddrinfo|name resolution|resolve|php_network_getaddresses/i',$warning)?'dns':
                (preg_match('/certificate|SSL|crypto|TLS/i',$warning)?'tls':(preg_match('/timed out|timeout/i',$warning)?'timeout':'transport'));
        }
        $out[$host]=$row;
    }
    return $out;
}
if(!defined('NEURO_MAX_DIAGNOSTIC_LIBRARY')){
    if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
    try{
        require '/home/n/neurodepro/private/notifications/max.php';
        $state=max_locked(static fn()=>max_read());
        echo json_encode(['ok'=>true,'max_diagnostic'=>max_delivery_diagnostic($state,'max_http'),'max_network'=>max_network_diagnostic()],JSON_THROW_ON_ERROR);
    }catch(Throwable $e){echo '{"ok":true,"max_diagnostic":{"error":"diagnostic_unavailable"}}';}
}
