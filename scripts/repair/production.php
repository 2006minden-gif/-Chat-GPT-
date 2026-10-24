<?php
/** One-time CLI-only, server-local repair. Never exports config bytes, tokens or parser messages. */
declare(strict_types=1);
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
ini_set('display_errors','0');ini_set('log_errors','0');umask(0077);
final class RepairFailure extends RuntimeException {}
function rp_assert(bool $ok,string $code):void {if(!$ok)throw new RepairFailure($code);}
function rp_read(string $path):string {
    rp_assert(!is_link($path)&&is_file($path)&&is_readable($path),'unsafe_or_missing_file');
    $s=@file_get_contents($path);rp_assert(is_string($s)&&strlen($s)<=262144,'file_read_or_size_failed');return $s;
}
function rp_syntax(string $s):array {
    rp_assert(function_exists('token_get_all'),'tokenizer_extension_required');
    try{token_get_all($s,TOKEN_PARSE);return ['valid'=>true,'line'=>null];}
    catch(ParseError $e){return ['valid'=>false,'line'=>$e->getLine()];}
}
function rp_tokens(string $s):array {
    $tokens=[];$offset=0;
    foreach(token_get_all($s) as $t){$text=is_array($t)?$t[1]:$t;$id=is_array($t)?$t[0]:null;
        if(!in_array($id,[T_WHITESPACE,T_COMMENT,T_DOC_COMMENT],true))$tokens[]=['id'=>$id,'text'=>$text,'offset'=>$offset,'end'=>$offset+strlen($text)];
        $offset+=strlen($text);
    }return $tokens;
}
function rp_literal_signature(string $s):string {
    // Scalar token spellings, flags, comments and whitespace remain byte-identical, not reserialized.
    $out=[];foreach(token_get_all($s) as $t)if(is_array($t))$out[]=[$t[0],$t[1]];
    return hash('sha256',serialize($out));
}
function rp_static_config(string $s):bool {
    if(!rp_syntax($s)['valid'])return false;$t=rp_tokens($s);$i=0;
    $is=static function(string $text)use(&$t,&$i):bool{return isset($t[$i])&&$t[$i]['text']===$text;};
    $eat=static function(string $text)use(&$i,$is):void{rp_assert($is($text),'nonliteral_configuration');$i++;};
    try{
        rp_assert(($t[$i++]['id']??null)===T_OPEN_TAG,'nonliteral_configuration');
        if(($t[$i]['id']??null)===T_DECLARE){$i++;$eat('(');$eat('strict_types');$eat('=');$eat('1');$eat(')');$eat(';');}
        rp_assert(($t[$i++]['id']??null)===T_RETURN,'nonliteral_configuration');
        $value=null;
        $value=static function(int $depth=0)use(&$value,&$i,$t,$is,$eat):void{
            rp_assert($depth<16,'nonliteral_configuration');$id=$t[$i]['id']??null;
            if($is('[')||$id===T_ARRAY){$array=$id===T_ARRAY;if($array){$i++;$eat('(');}else{$eat('[');}$close=$array?')':']';
                if(!$is($close))while(true){$value($depth+1);if(($t[$i]['id']??null)===T_DOUBLE_ARROW){$i++;$value($depth+1);}if(!$is(','))break;$i++;if($is($close))break;}
                $eat($close);return;
            }
            if($is('-')){$i++;rp_assert(in_array($t[$i]['id']??null,[T_LNUMBER,T_DNUMBER],true),'nonliteral_configuration');$i++;return;}
            rp_assert(in_array($id,[T_CONSTANT_ENCAPSED_STRING,T_LNUMBER,T_DNUMBER],true)||($id===T_STRING&&in_array(strtolower($t[$i]['text']),['true','false','null'],true)),'nonliteral_configuration');$i++;
        };
        rp_assert($is('[')||($t[$i]['id']??null)===T_ARRAY,'nonliteral_configuration');$value();
        if($is(';'))$i++;
        if(($t[$i]['id']??null)===T_CLOSE_TAG)$i++;
        if(($t[$i]['id']??null)===T_INLINE_HTML&&trim($t[$i]['text'])==='')$i++;
        return $i===count($t);
    }catch(RepairFailure $e){return false;}
}
function rp_config_candidate(string $s):array {
    $syntax=rp_syntax($s);
    if($syntax['valid']){rp_assert(rp_static_config($s),'nonliteral_configuration');return ['content'=>$s,'kind'=>'no_change','line'=>null];}
    $t=rp_tokens($s);$candidates=[];
    foreach($t as $i=>$token){
        // Insert only a comma between a literal value and a subsequent array key. No quotes/values changed.
        if($i<1||$token['id']!==T_CONSTANT_ENCAPSED_STRING||($t[$i+1]['id']??null)!==T_DOUBLE_ARROW)continue;
        $previous=$t[$i-1];$isValue=in_array($previous['id'],[T_CONSTANT_ENCAPSED_STRING,T_LNUMBER,T_DNUMBER],true)
            ||($previous['id']===T_STRING&&in_array(strtolower($previous['text']),['true','false','null'],true))||in_array($previous['text'],[']',')'],true);
        if(!$isValue)continue;
        $pos=$previous['end'];$candidate=substr($s,0,$pos).','.substr($s,$pos);
        if(rp_static_config($candidate)&&hash_equals(rp_literal_signature($s),rp_literal_signature($candidate)))$candidates[]=['content'=>$candidate,'kind'=>'missing_comma','line'=>substr_count(substr($s,0,$pos),"\n")+1];
    }
    rp_assert(count($candidates)===1,'unique_literal_preserving_repair_not_found');return $candidates[0];
}
function rp_block():string {
    return <<<'RULES'
# BEGIN NEURODELO ISSUE10 SECURITY
# Public code/assets remain available. Private backups and diagnostic copies never do.
<FilesMatch "(?i)(~|^#.*#$|^\.|\.(bak|bkp|backup|old|orig|save|swp|swo|tmp|temp)(\.|$)|\.(sql|sqlite3?|dump|ini|log|pem|key|p12|pfx|zip|tar|tgz|gz|7z|rar)$)">
    Require all denied
</FilesMatch>
<FilesMatch "(?i)^(config(\.example)?\.php|phpinfo\.php|diagnose\.php|debug\.php)$">
    Require all denied
</FilesMatch>
# Block hidden directories as well as files, preserving ACME certificate renewal.
<If "%{REQUEST_URI} =~ m#(^|/)(\.|%2[eE])# && %{REQUEST_URI} !~ m#^/(\.|%2[eE])well-known/acme-challenge/[A-Za-z0-9_-]+$#">
    Require all denied
</If>
# END NEURODELO ISSUE10 SECURITY
RULES;
}
function rp_htaccess_candidate(string $s):string {
    if(str_contains($s,'# BEGIN NEURODELO ISSUE10 SECURITY')){rp_assert(str_contains($s,rp_block()),'managed_rules_changed');return $s;}
    rp_assert(!str_contains($s,'# END NEURODELO ISSUE10 SECURITY'),'incomplete_managed_rules');
    return $s.(str_ends_with($s,"\n")?'':"\n").rp_block()."\n";
}
function rp_inspect(string $root):array {
    $config=rp_read($root.'/private/config.php');$syntax=rp_syntax($config);$candidate=null;
    try{$candidate=rp_config_candidate($config);}catch(RepairFailure $e){}
    $out=['ok'=>true,'read_only'=>true,'php'=>PHP_VERSION,'configuration'=>['syntax_valid'=>$syntax['valid'],'error_type'=>$syntax['valid']?null:'ParseError','error_line'=>$syntax['line'],'automatic_repair_available'=>$candidate!==null,'repair_kind'=>$candidate['kind']??null,'repair_line'=>$candidate['line']??null],'backup_copies'=>[]];
    foreach(['~.htaccess','index~.html'] as $name){$path=$root.'/public_html/'.$name;$row=['exists'=>is_file($path),'symlink'=>is_link($path)];
        if($row['exists']&&!$row['symlink']){$data=rp_read($path);$row+=['bytes'=>strlen($data),'private_key_marker'=>(bool)preg_match('/-----BEGIN [^-]*PRIVATE KEY-----/',$data),'credential_assignment_marker'=>(bool)preg_match('/(?:password|secret|api_key)\s*[\x22\x27]?\s*(?:=>|=|:)/i',$data),'php_config_marker'=>str_contains($data,'db_password')];}
        $out['backup_copies'][$name]=$row;
    }
    $rules=rp_read($root.'/public_html/.htaccess');$out['managed_rules_present']=str_contains($rules,rp_block());return $out;
}
if(!defined('NEURO_REPAIR_LIBRARY')){
    try{
        rp_assert(PHP_VERSION_ID>=80400,'php_84_required');$op=$argv[1]??'inspect';$root=$argv[2]??'/home/n/neurodepro';
        rp_assert($root==='/home/n/neurodepro'||(getenv('NEURO_REPAIR_TEST')==='1'&&str_starts_with($root,sys_get_temp_dir().'/')),'unexpected_root');
        rp_assert(realpath($root)===$root&&!is_link($root),'unsafe_root');
        rp_assert($op==='inspect','operation_not_implemented');echo json_encode(rp_inspect($root),JSON_UNESCAPED_SLASHES),"\n";
    }catch(Throwable $e){echo json_encode(['ok'=>false,'error'=>$e instanceof RepairFailure?$e->getMessage():'repair_operation_failed','type'=>get_class($e)]),"\n";exit(1);}
}
