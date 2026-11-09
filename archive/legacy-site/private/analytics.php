<?php
declare(strict_types=1);
function nd_analytics_approved():bool{
 try{if(!is_file(__DIR__.'/config.php'))return false;if(file_exists(__DIR__.'/runtime/analytics-disabled')||is_link(__DIR__.'/runtime/analytics-disabled'))return false;$d=release_legal_documents();return ($d['analytics_counter']??0)===114024456&&($d['analytics_approved']??false)===true&&privacy_settings()['version']===$d['version'];}catch(Throwable $e){return false;}
}
function nd_analytics_public_path(string $uri):bool{
 $path=parse_url($uri,PHP_URL_PATH);if(!in_array($path,['/','/index.php','/services.php','/catalog.php','/portfolio.php','/reviews.php','/portfolio-case.php','/privacy.php','/consent.php','/sitemap.php'],true))return false;
 parse_str((string)(parse_url($uri,PHP_URL_QUERY)??''),$q);$allowed=$path==='/services.php'?['service']:['case'];foreach($q as $key=>$value)if(!in_array($key,$allowed,true)||!is_string($value)||!preg_match('/^[a-z0-9_-]{1,120}$/D',$value))return false;return true;
}
function nd_analytics_private_session():bool{foreach(['nd_session','__Host-nd_customer','nd_customer','__Host-nd_prospect','nd_prospect'] as $key)if(isset($_COOKIE[$key]))return true;return false;}
function nd_analytics_choice():bool{$r=nd_analytics_receipt();return ($r['choice']??null)==='allow'&&!isset($_COOKIE['neuro_analytics_block']);}
function nd_analytics_key(bool $create=false):?string{
 $root=__DIR__.'/runtime';if(is_link($root)||(!is_dir($root)&&(!$create||!@mkdir($root,0700))))return null;$path=$root.'/analytics-consent.key';if(is_link($path))return null;
 if(!file_exists($path)&&$create){$h=@fopen($path,'x');if($h){chmod($path,0600);$bytes=random_bytes(32);$written=fwrite($h,$bytes);fclose($h);if($written!==32)return null;}}
 $key=is_file($path)?@file_get_contents($path):false;return is_string($key)&&strlen($key)===32?$key:null;
}
function nd_analytics_receipt():?array{
 $cookie=$_COOKIE['neuro_analytics']??'';$key=nd_analytics_key();if(!$key||!is_string($cookie)||strlen($cookie)>600)return null;$p=explode('.',$cookie);if(count($p)!==2||!hash_equals(hash_hmac('sha256',$p[0],$key),$p[1]))return null;$r=json_decode((string)base64_decode(strtr($p[0],'-_','+/'),true),true);
 if(!is_array($r)||array_keys($r)!==['version','time','choice']||$r['version']!=='analytics-2026-11-02-v1'||!is_int($r['time'])||$r['time']>time()||time()-$r['time']>=15552000||!in_array($r['choice'],['allow','deny'],true))return null;return $r;
}
function nd_analytics_record(string $choice):array{
 $key=nd_analytics_key(true);if(!$key)fail(503,'Не удалось сохранить выбор аналитики. Счётчик не запускается.');$r=['version'=>'analytics-2026-11-02-v1','time'=>time(),'choice'=>$choice];$data=rtrim(strtr(base64_encode(json_encode($r,JSON_THROW_ON_ERROR)),'+/','-_'),'=');$value=$data.'.'.hash_hmac('sha256',$data,$key);
 setcookie('neuro_analytics',$value,['expires'=>time()+15552000,'path'=>'/','secure'=>parse_url(config()['app_url'],PHP_URL_SCHEME)==='https','httponly'=>true,'samesite'=>'Lax']);return $r;
}

function nd_analytics_opted_out():bool{return isset($_COOKIE['neuro_analytics_block'])||(nd_analytics_receipt()['choice']??null)==='deny';}
function nd_analytics_noscript():string{return nd_analytics_public_path($_SERVER['REQUEST_URI']??'')&&nd_analytics_approved()&&!nd_analytics_opted_out()&&!nd_analytics_private_session()?'<noscript><div><img src="https://mc.yandex.ru/watch/114024456" class="nd-analytics-pixel" alt=""></div></noscript>':'';}
