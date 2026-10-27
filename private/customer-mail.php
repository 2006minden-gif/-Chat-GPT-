<?php
declare(strict_types=1);
/** Synchronous SMTP acceptance, not a claim of delivery to the inbox. No message/token spool. */
function customer_mail(string $recipient, string $purpose, string $token): bool {
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
    if (!filter_var($recipient,FILTER_VALIDATE_EMAIL) || preg_match('/[\r\n]/',$recipient)) return false;
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
        $stream=null;
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
            $write($message."\r\n.\r\n");$reply([250]);
            // DATA acceptance is the only success criterion. QUIT failures cannot undo it.
            @fwrite($stream,"QUIT\r\n");fclose($stream);return true;
        } catch (Throwable $e) {
            if (is_resource($stream)) fclose($stream);
            // Never log server replies, addresses, passwords, URLs or message bodies.
        }
    }
    return false;
}
