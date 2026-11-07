"""Diagnostics stay read-only and cannot disclose runtime credentials or webhook paths."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import unittest
import contextlib
import io
import runpy
import sys
import types
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('max_retry',ROOT/'scripts/notifications/retry.py')
retry=importlib.util.module_from_spec(spec)
spec.loader.exec_module(retry)

class MaxDeliveryDiagnostics(unittest.TestCase):
    def test_retry_job_reports_delivery_failure_and_keeps_other_workers(self):
        commands=[]
        class Remote:
            php='php'
            def __init__(self,*args):pass
            def command(self,command,**kwargs):
                commands.append(command)
                if len(commands)==1:return {'ok':True,'sent':0,'deferred':True,'error_code':'max_connection_failed','access_jobs_processed':2,'token':'SECRET'}
                return {'ok':True,'max_diagnostic':{'identity':'max_connection_failed','token':'SECRET'}}
            def close(self):commands.append('closed')
        module=types.ModuleType('client');module.Remote=Remote;module.ACCOUNT='/home/n/neurodepro'
        stdout=io.StringIO()
        with patch.dict(sys.modules,{'client':module}),contextlib.redirect_stdout(stdout):
            with self.assertRaises(SystemExit) as exc:
                runpy.run_path(str(ROOT/'scripts/notifications/retry.py'),run_name='__main__')
        self.assertEqual(exc.exception.code,1)
        self.assertEqual(commands[-1],'closed')
        self.assertIn('"access_jobs_processed": 2',stdout.getvalue())
        self.assertNotIn('SECRET',stdout.getvalue())

    def test_runner_drops_unexpected_remote_values(self):
        actual=retry.safe_diagnostic({'token':'SECRET','max_diagnostic':{
            'configured':True,'identity':'SECRET','subscription_count':2,'user_id':123,
            'webhook_hosts':['app-ru.naimi.ai','https://example.com/SECRET'],'raw':'SECRET'},
            'max_network':{'platform-api2.max.ru':{'http_status':401,'failure_kind':'SECRET','warning':'SECRET'},'SECRET':{}}})
        self.assertNotIn('SECRET',json.dumps(actual))
        self.assertEqual(actual['max_diagnostic']['webhook_hosts'],['app-ru.naimi.ai'])
        self.assertEqual(actual['max_network']['platform-api2.max.ru'],{'http_status':401})

    def php(self,code):
        script="<?php define('NEURO_MAX_DIAGNOSTIC_LIBRARY',true);require "+json.dumps(str(ROOT/'scripts/notifications/diagnose.php'))+';'+code
        result=subprocess.run([os.environ.get('PHP_BIN','php')],input=script,text=True,capture_output=True,check=True)
        return json.loads(result.stdout)

    def test_only_reads_identity_and_subscriptions_and_strips_secrets(self):
        result=self.php("""
        $state=['token'=>'SECRET','user_id'=>456,'enabled'=>true,'bot_username'=>'same_bot'];$calls=[];
        $out=max_delivery_diagnostic($state,function($method,$path,$token,$body)use(&$calls){
            if($method!=='GET'||$body!==null||$token!=='SECRET')throw new Exception('wrong_request');
            $calls[]=$path;
            return $path==='/me'?['is_bot'=>true,'username'=>'same_bot','user_id'=>123]:
                ['subscriptions'=>[['url'=>'https://neurodelo.pro/max-webhook.php','secret'=>'SECRET'],['url'=>'https://app-ru.naimi.ai/private/SECRET?token=SECRET']]];
        });echo json_encode(['out'=>$out,'calls'=>$calls,'state'=>$state['enabled']]);
        """)
        self.assertEqual(result['calls'],['/me','/subscriptions'])
        self.assertTrue(result['state'])
        self.assertTrue(result['out']['stored_bot_matches'])
        self.assertTrue(result['out']['site_webhook_present'])
        self.assertEqual(result['out']['subscription_count'],2)
        self.assertNotIn('SECRET',json.dumps(result))
        self.assertNotIn('456',json.dumps(result))

    def test_failed_identity_is_classified_without_raw_exception(self):
        for error,expected in [('max_auth_failed','max_auth_failed'),('SECRET transport error','diagnostic_failed')]:
            result=self.php("echo json_encode(max_delivery_diagnostic(['token'=>'SECRET'],function(){throw new RuntimeException("+json.dumps(error)+");}));")
            self.assertEqual(result['identity'],expected)
            self.assertEqual(result['subscriptions'],expected)
            self.assertNotIn('SECRET',json.dumps(result))
