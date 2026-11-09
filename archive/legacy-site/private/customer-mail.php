<?php
declare(strict_types=1);
/** Branded, self-contained HTML plus unchanged plain text. No tracking or remote images. */
function neuro_mail_html(string $plain,string $title):string{
 $esc=fn($s)=>htmlspecialchars($s,ENT_QUOTES|ENT_SUBSTITUTE,'UTF-8');$paragraphs=[];
 foreach(preg_split('/\r?\n\s*\r?\n/u',trim($plain)) as $paragraph){$chunks=preg_split('~(https?://[^\s<>"\']+)~u',$paragraph,-1,PREG_SPLIT_DELIM_CAPTURE);$html='';foreach($chunks as $i=>$chunk){if($i%2){$path=parse_url($chunk,PHP_URL_PATH)?:'';$label=str_ends_with($path,'prospect.php')?'Открыть документы':(str_ends_with($path,'customer.php')?'Продолжить в НейроДело':'Открыть кабинет');$html.='<a href="'.$esc($chunk).'" style="display:inline-block;padding:12px 18px;margin:8px 0;background:#306be3;border:1px solid #8bb7ff;border-radius:9px;color:#ffffff;text-decoration:none;font-weight:bold;line-height:1.5">'.$label.'</a>';}else $html.=nl2br($esc($chunk),false);}$paragraphs[]='<p style="margin:0 0 18px;line-height:1.7;color:#e6edfa;overflow-wrap:anywhere">'.$html.'</p>';}
 return '<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="dark"></head><body style="margin:0;padding:0;background:#080c14;color:#f0f4ff;font-family:Arial,sans-serif"><table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="#080c14"><tr><td align="center" style="padding:24px 12px"><table role="presentation" width="640" cellpadding="0" cellspacing="0" style="width:100%;max-width:640px;border:1px solid #40536f;border-radius:16px;background:#141c2b" bgcolor="#141c2b"><tr><td style="padding:24px;border-bottom:2px solid #ff3da6"><div style="font-size:28px;font-weight:bold;letter-spacing:-1px;color:#f0f4ff">НейроДело<span style="color:#ff3da6">.</span></div><div style="margin-top:8px;color:#b4c2d8;font-size:13px">Сайты · веб-приложения · ИИ-автоматизация</div></td></tr><tr><td style="padding:24px;font-size:16px"><h1 style="font-size:23px;line-height:1.35;margin:0 0 22px;color:#f0f4ff">'.$esc($title).'</h1>'.implode('',$paragraphs).'</td></tr><tr><td style="padding:18px 24px;border-top:1px solid #40536f;color:#b4c2d8;font-size:12px;line-height:1.7">Служебное письмо НейроДело. Ссылки доступа предназначены только получателю.</td></tr></table></td></tr></table></body></html>';
}
function neuro_brand_mail(string $message):string{
 if(str_contains($message,"X-NeuroDelo-Brand: 1\r\n"))return $message;
 $split=explode("\r\n\r\n",$message,2);if(count($split)!==2)throw new RuntimeException('mail_format_invalid');[$headers,$payload]=$split;$plain=null;
 if(preg_match('/Content-Type:\s*text\/plain/i',$headers)&&preg_match('/Content-Transfer-Encoding:\s*base64/i',$headers))$plain=base64_decode($payload,true);
 elseif(preg_match('/Content-Type:\s*multipart\/alternative;\s*boundary="([^"\r\n]+)"/i',$headers,$m)){foreach(explode('--'.$m[1],$payload) as $part){$p=explode("\r\n\r\n",ltrim($part,"\r\n"),2);if(count($p)===2&&preg_match('/Content-Type:\s*text\/plain/i',$p[0])&&preg_match('/Content-Transfer-Encoding:\s*base64/i',$p[0])){$plain=base64_decode(trim($p[1]),true);break;}}}
 if(!is_string($plain))throw new RuntimeException('mail_text_missing');$title='Сообщение НейроДело';if(preg_match('/^Subject:\s*=\?UTF-8\?B\?([^?]+)\?=/mi',$headers,$m)){$decoded=base64_decode($m[1],true);if(is_string($decoded))$title=$decoded;}
 $html=neuro_mail_html($plain,$title);$headers=preg_replace('/^(?:MIME-Version|Content-Type|Content-Transfer-Encoding):[^\r\n]*(?:\r?\n|$)/mi','',$headers);
 $headers=preg_replace_callback('/^From:\s*([^\r\n]+)/mi',static function($m){$from=trim($m[1]);return filter_var($from,FILTER_VALIDATE_EMAIL)?'From: =?UTF-8?B?'.base64_encode('НейроДело').'?= <'.$from.'>':$m[0];},$headers);
 $boundary='neuro_'.bin2hex(random_bytes(16));return rtrim($headers,"\r\n")."\r\nX-NeuroDelo-Brand: 1\r\nMIME-Version: 1.0\r\nContent-Type: multipart/alternative; boundary=\"".$boundary."\"\r\n\r\n--".$boundary."\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($plain),76,"\r\n").'--'.$boundary."\r\nContent-Type: text/html; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($html),76,"\r\n").'--'.$boundary."--\r\n";
}
/** Synchronous SMTP acceptance, not a claim of delivery to the inbox. No message/token spool. */
function customer_mail(string $recipient, string $purpose, string $token): bool {
    $GLOBALS['customer_smtp_outcome']='not_accepted';
    $c=config();$m=$c['customer_mail'] ?? [];
    $test=($m['transport'] ?? '')==='test-smtp';
    $host=$m['host'] ?? '';$port=(int)($m['port'] ?? 0);$from=$m['from'] ?? '';
    $loopback=in_array(parse_url($c['app_url'],PHP_URL_HOST),['127.0.0.1','localhost','::1'],true);
    if ($test && (!(($c['customer_auth_test_mode'] ?? false)===true && $loopback) || !in_array($host,['127.0.0.1','::1'],true))) return false;
    if ((!$test && ($m['transport'] ?? '')!=='smtp') || !is_string($host) || !preg_match('/^[A-Za-z0-9.:-]+$/D',$host)
        || $port<1 || $port>65535 || !is_string($from) || !filter_var($from,FILTER_VALIDATE_EMAIL)) return false;
    $tls=$m['encryption'] ?? 'starttls';
    if (!$test && !in_array($tls,['starttls','ssl'],true)) return false;
    $view=['verify'=>'verify','invite'=>'invite','reset'=>'reset'][$purpose];
    $link=rtrim($c['app_url'],'/').'/customer.php?view='.$view.'#token='.$token;
    $subject=['verify'=>'Подтвердите email — НейроДело','invite'=>'Приглашение в НейроДело','reset'=>'Восстановление пароля — НейроДело'][$purpose];
    $body="НейроДело\r\n\r\nОткройте ссылку для продолжения:\r\n".$link."\r\n\r\nЕсли вы не ожидали это письмо, просто проигнорируйте его.\r\n";
    $message='From: '.$from."\r\nTo: ".$recipient."\r\nSubject: =?UTF-8?B?".base64_encode($subject)."?=\r\nMIME-Version: 1.0\r\nContent-Type: text/plain; charset=UTF-8\r\nContent-Transfer-Encoding: base64\r\n\r\n".chunk_split(base64_encode($body),76,"\r\n");
    return customer_smtp_send($recipient,$message);
}
/** Shared SMTP transport. DATA acceptance is not inbox delivery. */
function customer_smtp_send(string $recipient,string $message,?array $override=null):bool {
    $GLOBALS['customer_smtp_outcome']='not_accepted';
    if (!filter_var($recipient,FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/',$recipient)) return false;
    try{$message=neuro_brand_mail($message);}catch(Throwable $e){return false;}
    $c=config();$m=$override??($c['customer_mail'] ?? []);
    $test=($m['transport'] ?? '')==='test-smtp';
    $host=$m['host'] ?? '';$port=(int)($m['port'] ?? 0);$from=$m['from'] ?? '';
    $loopback=in_array(parse_url($c['app_url'],PHP_URL_HOST),['127.0.0.1','localhost','::1'],true);
    if ($test && (!(($c['customer_auth_test_mode'] ?? false)===true && $loopback) || !in_array($host,['127.0.0.1','::1'],true))) return false;
    if ((!$test && ($m['transport'] ?? '')!=='smtp') || !is_string($host) || !preg_match('/^[A-Za-z0-9.:-]+$/D',$host)
        || $port<1 || $port>65535 || !is_string($from) || !filter_var($from,FILTER_VALIDATE_EMAIL)) return false;
    $tls=$m['encryption'] ?? 'starttls';
    if (!$test && !in_array($tls,['starttls','ssl'],true)) return false;
    for ($attempt=0;$attempt<2;$attempt++) {
        $stream=null;$dataStarted=false;
        try {
            $context=stream_context_create(['ssl'=>['verify_peer'=>true,'verify_peer_name'=>true,'peer_name'=>$host,'allow_self_signed'=>false,'crypto_method'=>STREAM_CRYPTO_METHOD_TLSv1_2_CLIENT|STREAM_CRYPTO_METHOD_TLSv1_3_CLIENT]]);
            $stream=@stream_socket_client(($tls==='ssl'&&!$test?'ssl://':'tcp://').$host.':'.$port,$errno,$error,5,STREAM_CLIENT_CONNECT,$context);
            if (!$stream) throw new RuntimeException('smtp_connect_failed');
            stream_set_timeout($stream,5);
            $reply=static function(array $expected) use($stream): void {
                $count=0;
                do {
                    $line=fgets($stream,1024);
                    if ($line===false || !preg_match('/^([0-9]{3})([ -])/',$line,$parts) || ++$count>50) throw new RuntimeException('smtp_protocol_failed');
                } while ($parts[2]==='-');
                if (!in_array((int)$parts[1],$expected,true)) throw new RuntimeException('smtp_rejected');
            };
            $write=static function(string $data) use($stream):void {
                while ($data!=='') {$n=fwrite($stream,$data);if($n===false||$n===0)throw new RuntimeException('smtp_write_failed');$data=substr($data,$n);}
            };
            $command=static function(string $line,array $expected)use($write,$reply):void {$write($line."\r\n");$reply($expected);};
            $reply([220]);$command('EHLO neurodelo.pro',[250]);
            if (!$test && $tls==='starttls') {
                $command('STARTTLS',[220]);
                if (@stream_socket_enable_crypto($stream,true,STREAM_CRYPTO_METHOD_TLSv1_2_CLIENT|STREAM_CRYPTO_METHOD_TLSv1_3_CLIENT)!==true) throw new RuntimeException('smtp_tls_failed');
                $command('EHLO neurodelo.pro',[250]);
            }
            if (!$test) {
                $user=$m['username'] ?? '';$password=$m['password'] ?? '';
                if (!is_string($user)||!is_string($password)||$user===''||$password==='')throw new RuntimeException('smtp_auth_missing');
                $command('AUTH PLAIN '.base64_encode("\0".$user."\0".$password),[235]);
            }
            $command('MAIL FROM:<'.$from.'>',[250]);$command('RCPT TO:<'.$recipient.'>',[250,251]);$command('DATA',[354]);
            $dataStarted=true;$write($message."\r\n.\r\n");$reply([250]);
            $GLOBALS['customer_smtp_outcome']='accepted';
            // DATA acceptance is the only success criterion. QUIT failures cannot undo it.
            @fwrite($stream,"QUIT\r\n");fclose($stream);return true;
        } catch (Throwable $e) {
            if (is_resource($stream)) fclose($stream);
            if($dataStarted && $e->getMessage()!=='smtp_rejected'){$GLOBALS['customer_smtp_outcome']='uncertain';return false;}
            // Never log server replies, addresses, passwords, URLs or message bodies.
        }
    }
    return false;
}
