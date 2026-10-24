"""Only synthetic temporary configs. Never touches production credentials or a remote host."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class RepairSyntax(unittest.TestCase):
 def helper(self,code,source):
  php=os.environ.get('PHP_BIN','php');script="define('NEURO_REPAIR_LIBRARY',true);require $argv[1];$v=json_decode(stream_get_contents(STDIN),true);"+code
  r=subprocess.run([php,'-r',script,str(ROOT/'scripts/repair/production.php')],input=json.dumps(source),text=True,capture_output=True)
  self.assertEqual(r.returncode,0);self.assertEqual(r.stderr,'');return json.loads(r.stdout)
 def test_missing_comma_preserves_all_scalar_spellings(self):
  s="<?php return ['db_password'=>'SYNTHETIC_ONLY',\n'app_url'=>'https://example.invalid'\n'privacy_policy_approved'=>false,'setup_key'=>'','db_port'=>3306];"
  d=self.helper("$c=rp_config_candidate($v);echo json_encode(['kind'=>$c['kind'],'same'=>rp_literal_signature($v)===rp_literal_signature($c['content']),'valid'=>rp_static_config($c['content'])]);",s)
  self.assertEqual(d,{'kind':'missing_comma','same':True,'valid':True})
 def test_missing_terminal_semicolon_is_single_character_and_literal_preserving(self):
  s="<?php return ['db_password'=>'SYNTHETIC_ONLY','privacy_policy_approved'=>false]\n"
  d=self.helper("$c=rp_config_candidate($v);echo json_encode(['kind'=>$c['kind'],'same'=>rp_literal_signature($v)===rp_literal_signature($c['content']),'bytes_added'=>strlen($c['content'])-strlen($v),'valid'=>rp_static_config($c['content'])]);",s)
  self.assertEqual(d,{'kind':'missing_terminal_semicolon','same':True,'bytes_added':1,'valid':True})
 def test_multiple_missing_separators_never_change_literal_bytes(self):
  for s in ["<?php return ['a'=>1 'b'=>2 'c'=>false];", "<?php return ['a'=>'SYNTHETIC_ONLY'\n'b'=>false]"]:
   d=self.helper("$c=rp_config_candidate($v);echo json_encode(['valid'=>rp_static_config($c['content']),'same'=>rp_literal_signature($v)===rp_literal_signature($c['content']),'count'=>$c['insertions']]);",s)
   self.assertEqual(d,{'valid':True,'same':True,'count':2})
 def test_missing_known_key_quote_never_modifies_value_bytes(self):
  for s in ["<?php return ['db_password'=>'SYNTHETIC_ONLY', 'privacy_policy_version => '2026-v1'];", "<?php return [db_password' => 'SYNTHETIC_ONLY','privacy_policy_approved'=>false];"]:
   d=self.helper("$c=rp_config_candidate($v);echo json_encode(['kind'=>$c['kind'],'same'=>rp_literal_signature($v)===rp_literal_signature($c['content']),'valid'=>rp_static_config($c['content'])]);",s)
   self.assertEqual(d,{'kind':'missing_known_key_quote','same':True,'valid':True})
 def test_key_quote_fix_never_guesses_a_corrupted_secret_value(self):
  s="<?php return ['db_password'=>'SYNTHETIC'fragment','privacy_policy_approved'=>false];"
  self.assertTrue(self.helper("try{rp_config_candidate($v);echo 'false';}catch(RepairFailure $e){echo 'true';}",s))
 def test_escape_preserves_declared_string_bytes_in_native_php(self):
  import hashlib
  s="<?php\nreturn [\n 'db_password' => 'SYNTH'fragment',\n 'privacy_policy_approved'=>false,\n];"
  d=self.helper("$c=rp_config_candidate($v);$tmp=tempnam(sys_get_temp_dir(),'repair-value-');try{file_put_contents($tmp,$c['content']);$config=require $tmp;echo json_encode(['kind'=>$c['kind'],'insertions'=>$c['insertions'],'hash'=>hash('sha256',$config['db_password']),'flag'=>$config['privacy_policy_approved']]);}finally{unlink($tmp);}",s)
  self.assertEqual(d,{'kind':'escape_existing_single_quote','insertions':1,'hash':hashlib.sha256(b"SYNTH'fragment").hexdigest(),'flag':False})
 def test_quote_escaping_refuses_multiple_declarations_and_keeps_valid_escapes(self):
  s="<?php\nreturn [\n 'setup_key' => 'SYNTH'fragment', 'privacy_policy_version'=>'v1',\n];"
  self.assertTrue(self.helper("try{rp_config_candidate($v);echo 'false';}catch(RepairFailure $e){echo 'true';}",s))
  valid="<?php\nreturn [\n 'db_password' => 'SYNTH\\'existing',\n];"
  self.assertTrue(self.helper("echo json_encode(rp_value_normalization($v)['content']===$v);",valid))
 def test_crlf_quote_repair_preserves_line_endings(self):
  s="<?php\r\nreturn [\r\n 'setup_key' => 'SYNTH'fragment',\r\n];\r\n"
  d=self.helper("$c=rp_config_candidate($v);echo json_encode(['kind'=>$c['kind'],'line_endings'=>substr_count($v,chr(13).chr(10))===substr_count($c['content'],chr(13).chr(10)),'valid'=>rp_static_config($c['content'])]);",s)
  self.assertEqual(d,{'kind':'escape_existing_single_quote','line_endings':True,'valid':True})
 def test_valid_config_is_unchanged(self):
  s="<?php return ['db_password'=>'SYNTHETIC_ONLY','privacy_policy_approved'=>false];"
  self.assertTrue(self.helper("$c=rp_config_candidate($v);echo json_encode($v===$c['content']);",s))
 def test_refuses_unterminated_string_multiple_defects_and_executable_config(self):
  for s in ["<?php return ['db_password'=>'unterminated];", "<?php return ['a'=>getenv('SECRET')];", "<?php file_put_contents('/tmp/SHOULD_NOT_EXIST','x'); return [];", "<?php return ['a'=>\"$secret\"];", "<?php return ['a'=>1]; echo 'leak';"]:
   self.assertTrue(self.helper("try{rp_config_candidate($v);echo 'false';}catch(RepairFailure $e){echo 'true';}",s))
 def test_handles_comments_nested_arrays_and_booleans_without_reformat(self):
  for s in ["<?php return array('a'=>array('b'=>true)\n/* preserve */'c'=>null);", "<?php declare(strict_types=1); return ['a'=>-2\n'b'=>false];"]:
   self.assertTrue(self.helper("$c=rp_config_candidate($v);echo json_encode(rp_static_config($c['content'])&&rp_literal_signature($v)===rp_literal_signature($c['content']));",s))
 def test_inspect_is_redacted_and_does_not_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'private').mkdir();(p/'public_html').mkdir();(p/'private/config.php').write_text("<?php return ['db_password'=>'SYNTHETIC_ONLY'\n'privacy_policy_approved'=>false];");(p/'public_html/.htaccess').write_text('Options -Indexes\n')
   before={str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()}
   r=subprocess.run([os.environ.get('PHP_BIN','php'),str(ROOT/'scripts/repair/production.php'),'inspect',tmp],env=dict(os.environ,NEURO_REPAIR_TEST='1'),text=True,capture_output=True)
   self.assertEqual(r.returncode,0);self.assertNotIn('SYNTHETIC_ONLY',r.stdout+r.stderr);d=json.loads(r.stdout);self.assertTrue(d['configuration']['automatic_repair_available']);self.assertEqual({str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()},before)


class RepairFiles(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  (self.root/'private').mkdir();(self.root/'public_html').mkdir()
  self.config="<?php return ['db_host'=>'fixture.invalid','db_name'=>'fixture','db_user'=>'fixture','db_password'=>'SYNTHETIC_ONLY','app_url'=>'https://neurodelo.pro'\n'privacy_policy_approved'=>false,'setup_key'=>'SYNTHETIC_SETUP','customer_auth_enabled'=>false];"
  (self.root/'private/config.php').write_text(self.config);(self.root/'public_html/.htaccess').write_text('Options -Indexes\n')
  (self.root/'public_html/~.htaccess').write_text('OLD BACKUP');(self.root/'public_html/index~.html').write_text('OLD PAGE');(self.root/'public_html/customer-upload.dat').write_text('KEEP')
 def rpc(self,op,id='test-plan',receipt=None,expect=0):
  import base64
  args=[os.environ.get('PHP_BIN','php'),str(ROOT/'scripts/repair/production.php'),op,str(self.root),id]
  if receipt is not None:args.append(base64.b64encode(json.dumps(receipt).encode()).decode())
  r=subprocess.run(args,env=dict(os.environ,NEURO_REPAIR_TEST='1',NEURO_REPAIR_TEST_FAKE_PDO='1'),text=True,capture_output=True)
  self.assertEqual(r.returncode,expect,r.stdout+r.stderr);self.assertNotIn('SYNTHETIC_ONLY',r.stdout+r.stderr);return json.loads(r.stdout)
 def test_prepare_apply_and_rollback_preserve_values_and_quarantine_copies(self):
  self.assertTrue(self.rpc('prepare')['backup_verified']);plan=self.root/'.neurodelo-repair/test-plan'
  self.assertEqual((self.root/'private/config.php').read_text(),self.config)
  for f in plan.iterdir():self.assertEqual(f.stat().st_mode&0o777,0o600)
  self.assertEqual(plan.stat().st_mode&0o777,0o700)
  applied=self.rpc('apply');self.assertTrue(applied['configuration_syntax_valid']);self.assertEqual(applied['quarantined_copies'],2)
  self.assertFalse((self.root/'public_html/~.htaccess').exists());self.assertEqual((plan/'quarantine/copy_rules').read_text(),'OLD BACKUP')
  rolled=self.rpc('rollback');self.assertTrue(rolled['bytes_restored']);self.assertEqual((self.root/'private/config.php').read_text(),self.config);self.assertEqual((self.root/'public_html/.htaccess').read_text(),'Options -Indexes\n');self.assertEqual((self.root/'public_html/customer-upload.dat').read_text(),'KEEP');self.assertFalse((self.root/'public_html/index~.html').exists())
 def test_large_public_copy_uses_streaming_backup_and_private_quarantine(self):
  import hashlib
  data=b'SYNTHETIC PUBLIC BACKUP '+b'x'*400000;(self.root/'public_html/index~.html').write_bytes(data)
  inspected=self.rpc('inspect');self.assertFalse(inspected['backup_copies']['index~.html']['scan_complete']);self.assertEqual(inspected['backup_copies']['index~.html']['bytes'],len(data))
  self.rpc('prepare');self.rpc('apply');copy=self.root/'.neurodelo-repair/test-plan/quarantine/copy_index';self.assertEqual(hashlib.sha256(copy.read_bytes()).digest(),hashlib.sha256(data).digest());self.rpc('rollback')
 def test_corrupt_backup_stale_source_and_parallel_plan_are_refused(self):
  self.rpc('prepare');self.assertEqual(self.rpc('prepare','other-plan',expect=1)['error'],'pending_repair_requires_resolution')
  config=self.root/'private/config.php';config.write_text(self.config+'\n');self.assertEqual(self.rpc('apply',expect=1)['error'],'source_changed_since_backup');config.write_text(self.config)
  (self.root/'.neurodelo-repair/test-plan/config.before').write_text('tampered');self.assertEqual(self.rpc('apply',expect=1)['error'],'backup_integrity_failed');self.assertEqual(config.read_text(),self.config)
 def test_confirm_requires_get_and_head_and_retains_verified_rules_on_later_rollback(self):
  self.rpc('prepare');self.rpc('apply');receipt={'plan_id':'test-plan','ok':True,'health':{'ok':True,'complete':True,'checks':{'/':{'ok':True}}},'protection':{}}
  self.assertEqual(self.rpc('confirm',receipt=receipt,expect=1)['error'],'backup_url_not_protected')
  urls=['/~.htaccess','/index~.html','/.nd-repair-test-plan.tmp','/nd-repair-test-plan.bak','/.nd-repair-test-plan/probe.txt'];receipt['protection']={url:{'GET':403,'HEAD':403} for url in urls}
  receipt['protection'][urls[0]]['GET']=200;self.rpc('confirm',receipt=receipt,expect=1);receipt['protection'][urls[0]]['GET']=403
  self.assertTrue(self.rpc('confirm',receipt=receipt)['healthy']);rules=(self.root/'public_html/.htaccess').read_text();self.assertTrue(self.rpc('rollback')['security_rules_retained']);self.assertEqual((self.root/'public_html/.htaccess').read_text(),rules);self.assertEqual((self.root/'private/config.php').read_text(),self.config)
 def test_symlink_and_probe_collision_never_overwrite_user_files(self):
  outside=self.root/'outside';outside.write_text('KEEP');(self.root/'public_html/~.htaccess').unlink();(self.root/'public_html/~.htaccess').symlink_to(outside);self.assertEqual(self.rpc('prepare',expect=1)['error'],'unsafe_or_missing_file');self.assertEqual(outside.read_text(),'KEEP')
 def test_rollback_does_not_overwrite_subsequent_owner_edit(self):
  self.rpc('prepare');self.rpc('apply');(self.root/'private/config.php').write_text('OWNER CHANGED FILE');self.assertEqual(self.rpc('rollback',expect=1)['error'],'rollback_external_change')



class RepairCoordinator(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import importlib.util
  spec=importlib.util.spec_from_file_location('production_repair_client',ROOT/'scripts/repair/client.py');cls.client=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.client)
 def test_failed_head_or_get_never_confirms_and_rolls_back(self):
  import test_release_pipeline as pipeline
  calls=[]
  class Server:
   def rpc(self,op,*a):calls.append(op);return {'ok':True,'bytes_restored':True}
  snapshots=iter([pipeline.bad(),pipeline.good(),pipeline.bad()])
  receipt={p:{'GET':403,'HEAD':403} for p in self.client.probe_urls('test')};receipt['/~.htaccess']['GET']=200
  r=self.client.coordinate(Server(),'apply','test',snapshot=lambda:next(snapshots),probe=lambda _:receipt)
  self.assertEqual(r['result'],'failed');self.assertEqual(calls,['apply','rollback']);self.assertTrue(r['rollback_bytes_verified'])
 def test_missing_baseline_transport_stops_before_apply(self):
  class Server:
   def rpc(self,*a):raise AssertionError('Must not write without a baseline')
  r=self.client.coordinate(Server(),'apply','test',snapshot=lambda:{'ok':False,'complete':False,'checks':{}})
  self.assertEqual(r['error'],'baseline_transport_unavailable')
 def test_real_pdo_http_repair_keeps_database_and_privacy_unchanged(self):
  import base64
  import test_prelaunch as baseline
  class Fixture(baseline.Prelaunch):pass
  f=Fixture;f.setUpClass()
  try:
   f.config['privacy_policy_approved']=False;f.write_config();before=(f.path/'private/config.php').read_text();broken=before.replace(",'setup_key'", "'setup_key'",1);self.assertNotEqual(before,broken);(f.path/'private/config.php').write_text(broken)
   (f.path/'public/.htaccess').write_text('Options -Indexes\n');(f.path/'public/~.htaccess').write_text('SYNTHETIC BACKUP');(f.path/'public/index~.html').write_text('SYNTHETIC PAGE')
   # The actual repair layout is public_html; fixture server retains its original public path via rename.
   f.proc.terminate();f.proc.wait(timeout=5);(f.path/'public').rename(f.path/'public_html')
   f.proc=subprocess.Popen([f.php,'-d','opcache.enable=0','-d','opcache.enable_cli=0','-S','127.0.0.1:'+str(f.port),'-t',str(f.path/'public_html'),str(f.path/'tests/router.php')],stdout=f.log,stderr=f.log)
   import requests,time
   for _ in range(50):
    try:requests.get(f.base,timeout=1);break
    except requests.ConnectionError:time.sleep(.05)
   prior={t:f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_sessions','nd_limits']}
   test=self
   class LocalServer:
    def rpc(self,op,id='',receipt=None):
     args=[f.php,str(ROOT/'scripts/repair/production.php'),op,str(f.path),id]
     if receipt is not None:args.append(base64.b64encode(json.dumps(receipt).encode()).decode())
     r=subprocess.run(args,env=dict(os.environ,NEURO_REPAIR_TEST='1'),capture_output=True,text=True)
     if r.returncode:raise test.client.RemoteFailure('local operation failed')
     return json.loads(r.stdout)
   server=LocalServer();prepared=server.rpc('prepare','live-test');self.assertTrue(prepared['candidate_preflight']['pdo']);self.assertNotIn('synthetic',prepared['candidate_preflight'])
   result=self.client.coordinate(server,'apply','live-test',snapshot=lambda:self.client.health.snapshot(f.base),probe=lambda id:self.client.protection_probe(id,f.base))
   self.assertEqual(result['result'],'repaired_and_verified',result);self.assertEqual((f.path/'private/config.php').read_text(),before)
   self.assertEqual({t:f.sql('SELECT * FROM '+t) for t in prior},prior);self.assertFalse(result['server']['preflight']['privacy_approved']);self.assertFalse(requests.get(f.base+'/api.php?r=privacy').json()['enabled'])
  finally:f.doClassCleanups()



class RepairWorkflow(unittest.TestCase):
 def test_main_only_manual_repair_reuses_ci_without_publishing(self):
  import yaml
  w=yaml.load((ROOT/'.github/workflows/production-repair.yml').read_text(),Loader=yaml.BaseLoader);self.assertEqual(set(w['on']),{'workflow_dispatch'});self.assertEqual(w['jobs']['validate']['uses'],'./.github/workflows/deploy.yml');self.assertEqual(w['jobs']['validate']['with']['validation_only'],'true')
  job=w['jobs']['repair'];self.assertEqual(job['if'],"github.ref == 'refs/heads/main'");self.assertEqual(job['needs'],'validate');self.assertEqual(job['environment'],'production');self.assertEqual(job['concurrency']['group'],'spaceweb-production');self.assertEqual(job['concurrency']['cancel-in-progress'],'false')
  source=(ROOT/'.github/workflows/deploy.yml').read_text();self.assertIn('inputs.validation_only != true',source);self.assertIn('BOOTSTRAP_VERIFIED_RUN',source)
  r=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',"define('NEURO_REPAIR_LIBRARY',true);require $argv[1];echo rp_block();",str(ROOT/'scripts/repair/production.php')],text=True,capture_output=True,check=True);self.assertIn(r.stdout,(ROOT/'public/.htaccess').read_text())
  self.assertNotIn('migrate.php',str(w));self.assertNotIn('AUTOMATION_READY',str(w));self.assertNotIn('secrets: inherit',str(w))

if __name__=='__main__':unittest.main()
