"""The real MAX transport must keep TLS/name checks and the reviewed CA."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[1]

class MaxTransport(unittest.TestCase):
    def request(self,status=200):
        script='''<?php
require %s;
class CapturedHttps {
 public $context;
 public $status;
 public static array $request=[];
 private string $body='{"is_bot":true,"user_id":123}';
 private int $position=0;
 function stream_open($path,$mode,$options,&$opened_path):bool {
  self::$request=['url'=>$path,'options'=>stream_context_get_options($this->context)];
  unset($this->context);$this->status='HTTP/1.1 %d Test';return true;
 }
 function stream_read($count):string {$s=substr($this->body,$this->position,$count);$this->position+=strlen($s);return $s;}
 function stream_eof():bool {return $this->position>=strlen($this->body);}
 function stream_stat():array {return [];}
}
stream_wrapper_unregister('https');stream_wrapper_register('https',CapturedHttps::class);
try{$result=max_http('GET','/me','SYNTHETIC_NOT_A_REAL_TOKEN');}catch(Throwable $e){$result=['error'=>$e->getMessage()];}
$request=CapturedHttps::$request;$ssl=$request['options']['ssl'];
$cert=file_get_contents($ssl['cafile']);
$parsed=openssl_x509_parse($cert);
echo json_encode(['result'=>$result,'url'=>$request['url'],'ssl'=>$ssl,
 'http'=>$request['options']['http'],'fingerprint'=>openssl_x509_fingerprint($cert,'sha256'),
 'ca'=>$parsed['extensions']['basicConstraints']??'','expires'=>$parsed['validTo_time_t']]);
'''%(json.dumps(str(ROOT/'private/notifications/max.php')),status)
        r=subprocess.run([os.environ.get('PHP_BIN','php')],input=script,text=True,capture_output=True,check=True)
        return json.loads(r.stdout)

    def test_fixed_host_validated_tls_and_pinned_official_root(self):
        r=self.request()
        self.assertTrue(r['result']['is_bot'])
        self.assertEqual(r['url'],'https://platform-api2.max.ru/me')
        self.assertTrue(r['ssl']['verify_peer']);self.assertTrue(r['ssl']['verify_peer_name'])
        self.assertFalse(r['ssl']['allow_self_signed'])
        self.assertEqual(r['fingerprint'],'d26d2d0231b7c39f92cc738512ba54103519e4405d68b5bd703e9788ca8ecf31')
        self.assertIn('CA:TRUE',r['ca'])
        self.assertEqual(r['http']['follow_location'],0)
        self.assertEqual(r['http']['timeout'],4)
        self.assertIn('Authorization: SYNTHETIC_NOT_A_REAL_TOKEN',r['http']['header'])

    def test_authentication_failure_is_not_a_delivery_success(self):
        self.assertEqual(self.request(401)['result'],{'error':'max_auth_failed'})
