import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import test_prelaunch as fixture
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/deploy'))
import release, health, client
spec=importlib.util.spec_from_file_location('github_control',ROOT/'scripts/github/control.py');control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)

def good():
 return {'ok':True,'complete':True,'checks':{p:{'ok':True,'transport_ok':True,'status':200,'content_type':'text/html','redirected':False} for p in health.PATHS}}

def bad():
 value=good();value['ok']=False;value['checks']['/api.php?r=privacy'].update(ok=False,status=503,content_type='application/json');return value

class FakeRemote:
 def __init__(self,fail=None):self.calls=[];self.fail=fail
 def preflight(self):self.calls.append('preflight');return {'ok':True}
 def preview(self):self.calls.append('preview')
 def stage(self,before):self.calls.append('stage')
 def evidence(self,after):self.calls.append('evidence')
 def action(self,op,release_id=None):
  self.calls.append(op)
  if op==self.fail:raise client.RemoteFailure('injected_failure')
  if op in ['rollback','recover']:return {'ok':True,'id':'fixture','baseline':good()}
  return {'ok':True}

class CoordinatorTests(unittest.TestCase):
 def test_success_requires_post_health_and_file_finalize(self):
  remote=FakeRemote();values=iter([good(),good()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'deployed_and_verified');self.assertEqual(remote.calls,['preflight','stage','apply','evidence','finalize'])
 def test_failed_health_always_fails_even_after_verified_rollback(self):
  remote=FakeRemote();values=iter([good(),bad(),good()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'failed');self.assertTrue(r['rollback_verified']);self.assertIn('confirm-rollback',remote.calls)
 def test_preexisting_503_not_disguised_as_success(self):
  remote=FakeRemote();values=iter([bad(),bad(),bad()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'failed');self.assertFalse(r['rollback_verified']);self.assertIn('/api.php?r=privacy',r['preexisting_failures']);self.assertIn('mark-unhealthy',remote.calls);self.assertNotIn('rollback',remote.calls)
 def test_new_regression_on_unhealthy_baseline_still_rolls_back(self):
  remote=FakeRemote();worse=bad();worse['checks']['/']['ok']=False
  values=iter([bad(),worse,bad()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'failed');self.assertTrue(r['rollback_verified']);self.assertIn('rollback',remote.calls)
 def test_rollback_failure_never_marked_verified(self):
  remote=FakeRemote('rollback');values=iter([good(),bad()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertFalse(r['rollback_verified']);self.assertEqual(r['result'],'failed')
 def test_transport_failure_stops_before_writes(self):
  before=good();before['complete']=False;remote=FakeRemote();r=client.coordinate(remote,snapshot=lambda:before)
  self.assertEqual(remote.calls,[]);self.assertEqual(r['result'],'failed')
 def test_preview_never_stages_backs_up_or_applies(self):
  remote=FakeRemote();r=client.coordinate(remote,'preview',snapshot=good)
  self.assertEqual(r['result'],'preview_passed');self.assertEqual(remote.calls,['preflight','preview'])
 def test_apply_failure_attempts_file_rollback(self):
  remote=FakeRemote('apply');values=iter([good(),good()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'failed');self.assertTrue(r['rollback_verified'])
 def test_finalize_failure_rolls_back(self):
  remote=FakeRemote('finalize');values=iter([good(),good(),good()]);r=client.coordinate(remote,snapshot=lambda:next(values),attempts=1)
  self.assertEqual(r['result'],'failed');self.assertTrue(r['rollback_verified'])

class ReleaseFilesTests(unittest.TestCase):
 def test_allowlisted_artifact_never_contains_credentials_or_installer(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=Path(tmp)/'release';m=release.build(bundle,'a'*40)
   self.assertEqual(len(m['files']),len(release.policy_check()['public_files'])+len(release.policy_check()['private_files']));client.validate_bundle(bundle,'a'*40)
   self.assertIn('database/schema.sql',m['tools']);self.assertTrue(all(not p.startswith('public_html/') for p in m['tools'] if p.endswith('.sql')))
   self.assertNotIn('private/config.php',m['files']);self.assertNotIn('public_html/setup.php',m['files'])
   (bundle/'private/app.php').write_text('tampered')
   with self.assertRaises(ValueError):client.validate_bundle(bundle,'a'*40)
 def test_unknown_revision_and_extra_files_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=Path(tmp)/'release';release.build(bundle,'a'*40)
   with self.assertRaises(ValueError):client.validate_bundle(bundle,'b'*40)
   (bundle/'secret.key').write_text('SYNTHETIC')
   with self.assertRaises(ValueError):client.validate_bundle(bundle,'a'*40)
 def test_automatic_destructive_migration_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);folder=root/'database/migrations/004_crm_foundation';folder.mkdir(parents=True);(root/'scripts/deploy').mkdir(parents=True)
   (folder/'up.sql').write_text('DROP TABLE nd_leads;');(folder/'down.sql').write_text('SELECT 1;')
   policy={'schema_version':1,'keep_backups':3,'migrations':[{'version':'004_crm_foundation','kind':'additive','automatic':True,'required':True,'up_sha256':release.digest(folder/'up.sql'),'down_sha256':release.digest(folder/'down.sql')}]}
   (root/'scripts/deploy/policy.json').write_text(json.dumps(policy))
   with self.assertRaisesRegex(ValueError,'destructive'):release.policy_check(root)

class RemoteFilesystemTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=fixture.Prelaunch;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  for folder in ['public_html','private','.neurodelo-deploy/incoming']:(self.root/folder).mkdir(parents=True,exist_ok=True)
  self.id='release0';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id
  self.manifest=release.build(self.candidate,'a'*40)
  # Most tests exercise file delivery, not a pending business migration.
  self.manifest['migrations']=[];(self.candidate/'manifest.json').write_text(json.dumps(self.manifest))
  for path in self.manifest['files']:
   (self.root/path).parent.mkdir(parents=True,exist_ok=True);(self.root/path).write_text('OLD '+path)
  (self.root/'private/config.php').write_text((self.f.path/'private/config.php').read_text().replace(self.f.base,'https://neurodelo.pro'))
  shutil.copyfile(self.f.path/'private/privacy-policy.txt',self.root/'private/privacy-policy.txt')
  (self.root/'public_html/customer-upload.dat').write_text('PRESERVE CUSTOMER FILE')
  self.baseline=good();(self.candidate/'baseline.json').write_text(json.dumps(self.baseline))
  self.before={path:release.digest(self.root/path) for path in self.manifest['files']}
  self.protected={path:release.digest(self.root/path) for path in ['private/config.php','private/privacy-policy.txt','public_html/customer-upload.dat']}
 def agent(self,op,expected=0,id=None):
  env=dict(os.environ,NEURO_PHP_BIN=self.f.php)
  r=subprocess.run([self.f.php,str(ROOT/'scripts/deploy/remote.php'),op,str(self.root),id or self.id],capture_output=True,text=True,env=env)
  self.assertEqual(r.returncode,expected,r.stdout+r.stderr)
  return json.loads(r.stdout)
 def assert_protected(self):
  for path,digest in self.protected.items():self.assertEqual(release.digest(self.root/path),digest,path)
 def finish(self):
  (self.candidate/'after-health.json').write_text(json.dumps(good()));return self.agent('finalize')
 def test_readonly_preflight_creates_no_backup_or_lock(self):
  before=set(self.root.rglob('*'));self.agent('preflight');self.assertEqual(set(self.root.rglob('*')),before);self.assert_protected()
 def test_apply_verified_backup_and_rollback_preserve_uploads_and_config(self):
  applied=self.agent('apply');self.assertTrue(applied['backup_verified']);self.assertTrue(applied['recovery_verified']);self.assertEqual(applied['files_sha256'],self.manifest['files']);self.assert_protected()
  backup=self.root/'.neurodelo-deploy/backups'/self.id
  for path,digest in self.before.items():self.assertEqual(release.digest(backup/'files'/path),digest);self.assertEqual(release.digest(self.root/path),self.manifest['files'][path])
  self.assertFalse((backup/'files/private/config.php').exists());self.assertFalse((backup/'recovery-check').exists())
  result=self.agent('rollback');self.assertTrue(result['files_restored']);self.assertFalse(result['health_verified'])
  for path,digest in self.before.items():self.assertEqual(release.digest(self.root/path),digest)
  self.agent('confirm-rollback');self.assert_protected()
 def test_checksum_tampering_blocks_all_application_writes(self):
  (self.candidate/'public_html/script.js').write_text('TAMPERED')
  self.assertEqual(self.agent('apply',1)['error'],'release_checksum_mismatch')
  for path,digest in self.before.items():self.assertEqual(release.digest(self.root/path),digest)
 def test_extra_config_in_candidate_is_rejected(self):
  (self.candidate/'private/config.php').write_text('SYNTHETIC SECRET')
  self.assertEqual(self.agent('apply',1)['error'],'unexpected_release_file');self.assert_protected()
 def test_symlink_never_overwrites_its_target(self):
  target=self.root/'private/secret';target.write_text('SYNTHETIC');path=self.root/'public_html/script.js';path.unlink();path.symlink_to(target)
  self.assertEqual(self.agent('apply',1)['error'],'symlink_refused');self.assertEqual(target.read_text(),'SYNTHETIC')
 def test_conflicting_manual_change_is_not_silently_overwritten(self):
  self.agent('apply');(self.root/'public_html/script.js').write_text('MANUAL CHANGE')
  self.assertEqual(self.agent('rollback',1)['error'],'rollback_conflicting_manual_change')
  self.assertEqual((self.root/'public_html/script.js').read_text(),'MANUAL CHANGE')
  self.assertEqual(release.digest(self.root/'private/app.php'),self.manifest['files']['private/app.php'])
 def test_config_rotation_is_preserved_during_rollback(self):
  self.agent('apply');config=self.root/'private/config.php';config.write_text(config.read_text()+'\n// rotated independently\n')
  rotated=release.digest(config);self.agent('rollback');self.assertEqual(release.digest(config),rotated)
 def test_corrupted_backup_never_used(self):
  self.agent('apply');path=self.root/'.neurodelo-deploy/backups'/self.id/'files/public_html/script.js';path.write_text('CORRUPTED')
  self.assertEqual(self.agent('rollback',1)['error'],'backup_checksum_mismatch')
  self.assertEqual(release.digest(self.root/'public_html/script.js'),self.manifest['files']['public_html/script.js'])
 def test_finalize_requires_health_and_preserves_latest_good_snapshot(self):
  self.agent('apply');self.assertEqual(self.agent('finalize',1)['error'],'metadata_missing')
  self.finish();state=json.loads((self.root/'.neurodelo-deploy/state.json').read_text())
  self.assertEqual(state['last_result'],'healthy');self.assertTrue(state['known_good_backup'].startswith('good-'))
  snapshot=self.root/'.neurodelo-deploy/backups'/state['known_good_backup']
  self.assertTrue((snapshot/'backup.json').is_file());self.assertEqual(release.digest(snapshot/'files/private/app.php'),self.manifest['files']['private/app.php'])
 def test_retention_is_bounded_and_keeps_recovery_points(self):
  self.agent('apply');self.finish()
  (self.candidate/'leftover-config-link').symlink_to(self.root/'private/config.php')
  for number in range(1,5):
   self.id='release'+str(number);self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id
   m=release.build(self.candidate,format(number,'040x'));m['migrations']=[];(self.candidate/'manifest.json').write_text(json.dumps(m));(self.candidate/'baseline.json').write_text(json.dumps(good()))
   self.agent('apply');self.finish()
  state=json.loads((self.root/'.neurodelo-deploy/state.json').read_text());backups=self.root/'.neurodelo-deploy/backups'
  pinned={state.get(k) for k in ['known_good_backup','database_recovery_backup','active','last_release'] if state.get(k)}
  self.assertLessEqual(len({p.name for p in backups.iterdir()}-pinned),3);self.assertTrue((backups/state['known_good_backup']).exists());self.assertTrue((backups/state['last_release']).exists());self.assert_protected()
 def test_preexisting_failure_keeps_improvements_but_never_marks_good(self):
  (self.candidate/'baseline.json').write_text(json.dumps(bad()));self.agent('apply')
  (self.candidate/'after-health.json').write_text(json.dumps(bad()));result=self.agent('mark-unhealthy')
  self.assertFalse(result['healthy']);self.assertFalse(result['known_good_advanced'])
  state=json.loads((self.root/'.neurodelo-deploy/state.json').read_text())
  self.assertEqual(state['last_result'],'unhealthy_preexisting');self.assertNotIn('known_good_backup',state)
  self.assertEqual(release.digest(self.root/'public_html/.htaccess'),self.manifest['files']['public_html/.htaccess']);self.assert_protected()
 def test_new_regression_cannot_be_marked_as_preexisting(self):
  (self.candidate/'baseline.json').write_text(json.dumps(bad()));self.agent('apply')
  worse=bad();worse['checks']['/']['ok']=False
  (self.candidate/'after-health.json').write_text(json.dumps(worse))
  self.assertEqual(self.agent('mark-unhealthy',1)['error'],'new_regression_requires_rollback')
  self.agent('rollback')
 def test_private_payment_qr_original_survives_release_and_rollback(self):
  file=self.root/'private/payment-qr-files'/'synthetic-original';file.parent.mkdir();data=b'SYNTHETIC private QR original bytes, not a payment QR';file.write_bytes(data)
  self.agent('apply');self.assertEqual(file.read_bytes(),data);self.agent('rollback');self.assertEqual(file.read_bytes(),data)
 def test_private_publication_upload_survives_release_and_rollback(self):
  file=self.root/'private/publication-files'/'synthetic-retained-media';file.parent.mkdir();file.write_bytes(b'SYNTHETIC private publication media')
  self.agent('apply');self.assertEqual(file.read_bytes(),b'SYNTHETIC private publication media');self.agent('rollback');self.assertEqual(file.read_bytes(),b'SYNTHETIC private publication media')

 def test_unfinished_release_blocks_new_apply(self):
  self.agent('apply');self.assertEqual(self.agent('apply',1)['error'],'unfinished_release_requires_recovery')
 def test_wrong_auto_rollback_id_cannot_undo_prior_success(self):
  self.agent('apply');self.finish()
  self.assertEqual(self.agent('rollback',1,id='different')['error'],'release_writes_not_started')

 def test_approved_additive_migration_is_backed_up_and_dump_restorable(self):
  # Synthetic operator: proves orchestration/backup ordering, not Stage 3's unmerged code.
  self.agent('apply');self.finish()
  self.id='migration-release';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id
  release.build(self.candidate,'b'*40);(self.candidate/'baseline.json').write_text(json.dumps(good()))
  version='004_crm_foundation';folder=self.candidate/'database/migrations'/version;folder.mkdir(parents=True,exist_ok=True)
  up='\n'.join('CREATE TABLE nd_ci_'+chr(97+i)+' (id INT PRIMARY KEY) ENGINE=InnoDB;' for i in range(12))
  down='\n'.join('DROP TABLE nd_ci_'+chr(97+i)+';' for i in reversed(range(12)))
  (folder/'up.sql').write_text(up);(folder/'down.sql').write_text(down)
  (self.candidate/'scripts').mkdir(exist_ok=True)
  operator='''<?php
$c=require dirname(__DIR__).'/private/config.php';
$p=new PDO('mysql:host='.$c['db_host'].';port='.$c['db_port'].';dbname='.$c['db_name'].';charset=utf8mb4',$c['db_user'],$c['db_password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
if(($argv[1]??'')!=='up')exit(2);
$base=dirname(__DIR__).'/database/migrations/004_crm_foundation/';$p->exec(file_get_contents($base.'up.sql'));
$p->exec('CREATE TABLE nd_schema_migrations(version VARCHAR(64) PRIMARY KEY,state VARCHAR(32),up_checksum CHAR(64),down_checksum CHAR(64))');
$p->prepare('INSERT INTO nd_schema_migrations VALUES (?,?,?,?)')->execute(['004_crm_foundation','applied',hash_file('sha256',$base.'up.sql'),hash_file('sha256',$base.'down.sql')]);
'''
  (self.candidate/'scripts/migrate.php').write_text(operator)
  manifest=json.loads((self.candidate/'manifest.json').read_text())
  manifest['migrations']=[{'version':version,'kind':'additive','automatic':True,'required':True,'up_sha256':release.digest(folder/'up.sql'),'down_sha256':release.digest(folder/'down.sql')}]
  for path in ['scripts/migrate.php','database/migrations/'+version+'/up.sql','database/migrations/'+version+'/down.sql']:manifest['tools'][path]=release.digest(self.candidate/path)
  manifest['verification_contract']='missing-proof';(self.candidate/'manifest.json').write_text(json.dumps(manifest))
  self.assertEqual(self.agent('apply',1)['error'],'pipeline_backup_recovery_not_verified');self.agent('rollback')
  old=self.candidate;self.id='migration-release-retry';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id;shutil.copytree(old,self.candidate)
  manifest['verification_contract']='ci-mysql57-backup-restore-v1';(self.candidate/'manifest.json').write_text(json.dumps(manifest))
  restore='neuro_test_restore_'+__import__('secrets').token_hex(8)
  try:
   result=self.agent('apply');self.assertEqual(result['migrations'],[version]);self.assert_protected()
   backup=self.root/'.neurodelo-deploy/backups'/self.id
   self.assertTrue((backup/'database.sql').is_file());self.assertFalse((backup/'.mysql-client.cnf').exists())
   metadata=json.loads((backup/'database.json').read_text());self.assertEqual(metadata['sha256'],release.digest(backup/'database.sql'))
   self.assertEqual(self.f.sql("SELECT state FROM nd_schema_migrations WHERE version='004_crm_foundation'")[0]['state'],'applied')
   # Restore only to another randomly named synthetic DB, never over the source DB.
   sql=(backup/'database.sql').read_text().replace('`'+self.f.dbname+'`','`'+restore+'`')
   self.f.sql(sql,admin=True)
   restored=self.f.sql('SELECT id,password_hash FROM `'+restore+'`.nd_admin',admin=True)
   self.assertEqual(restored,self.f.sql('SELECT id,password_hash FROM nd_admin'))
   self.agent('rollback');self.assertEqual(self.f.sql('SELECT COUNT(*) AS n FROM nd_ci_a')[0]['n'],0)
  finally:
   self.f.sql('DROP DATABASE IF EXISTS `'+restore+'`',admin=True)
   for i in range(12):self.f.sql('DROP TABLE IF EXISTS nd_ci_'+chr(97+i))
   self.f.sql('DROP TABLE IF EXISTS nd_schema_migrations')

class SSHIsolationTests(unittest.TestCase):
 def test_strict_host_identity_preview_and_key_cleanup(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=Path(tmp)/'bundle';release.build(bundle,'a'*40)
   env={'SSH_HOST':'fixture.invalid','SSH_USER':'fixture','SSH_PORT':'22','DEPLOY_PATH':client.ACCOUNT+'/public_html','SSH_PRIVATE_KEY':'SYNTHETIC_NOT_A_REAL_KEY','SSH_KNOWN_HOSTS':'SYNTHETIC_NOT_A_REAL_HOST_KEY'}
   with patch.dict(os.environ,env):remote=client.Remote(bundle,'a'*40,'fixture')
   self.assertEqual(remote.php,os.environ.get('PHP_CLI') or '/usr/bin/php8.4')
   key=Path(remote.ssh[remote.ssh.index('-i')+1]);self.assertEqual(key.stat().st_mode&0o777,0o600)
   self.assertIn('StrictHostKeyChecking=yes',remote.ssh);self.assertIn('IdentitiesOnly=yes',remote.ssh);self.assertIn('BatchMode=yes',remote.ssh)
   try:
    with patch('client.subprocess.run') as run:
     run.return_value.returncode=0;remote.preview()
     self.assertEqual(run.call_count,2)
     for call in run.call_args_list:self.assertIn('--dry-run',call.args[0]);self.assertNotIn('--delete',call.args[0])
   finally:remote.close()
   self.assertFalse(key.exists())

class HealthTests(unittest.TestCase):
 def opener(self,enabled=False,broken=None):
  from urllib.parse import urlparse,parse_qs
  def open_response(request,timeout):
   parsed=urlparse(request.full_url);path=parsed.path
   if path=='/api.php':path+='?r='+parse_qs(parsed.query)['r'][0]
   status=200;kind='text/html';text='НейроДело'
   if path=='/api.php?r=privacy':kind='application/json';text=json.dumps({'enabled':enabled,'version':'v1' if enabled else '','url':'/privacy.php'})
   elif path=='/privacy.php':status=200 if enabled else 503;text='Версия: v1' if enabled else 'Приём заявок через форму отключён'
   elif path in ['/api.php?r=session','/api.php?r=leads']:status=401;kind='application/json';text=json.dumps({'detail':'Войдите в CRM'})
   elif path in health.DENIED_PATHS:status=403;text=''
   elif path in health.ASSET_PATHS:kind='text/css' if path.endswith('.css') else 'application/javascript';text='synthetic asset'
   if broken and path==broken[0]:status,kind,text=broken[1:]
   class Response(io.BytesIO):
    def close(self):super().close()
   response=Response(text.encode());response.status=status;response.url=request.full_url
   response.headers={'Content-Type':kind,'X-Request-ID':'fixture-request'};return response
  return open_response
 def test_public_disabled_notice_requires_explicit_marker(self):
  self.assertTrue(health.snapshot(opener=self.opener(False,('/privacy.php',200,'text/html','<article data-privacy-mode="notice">Приём заявок через форму отключён</article>')))['ok'])
  self.assertFalse(health.snapshot(opener=self.opener(False,('/privacy.php',200,'text/html','Приём заявок через форму отключён')))['ok'])
 def test_crawl_assets_require_exact_types_and_bytes(self):
  from io import BytesIO
  base=self.opener()
  def opener(req,timeout):
   path=__import__('urllib.parse',fromlist=['urlsplit']).urlsplit(req.full_url).path
   if path in health.METADATA_TYPES:
    response=BytesIO(b'synthetic metadata');response.status=200;response.url=req.full_url;response.headers={'Content-Type':health.METADATA_TYPES[path][0]};return response
   return base(req,timeout)
  report=health.snapshot(opener=opener,extra_assets=health.METADATA_TYPES)
  self.assertTrue(report['ok']);self.assertEqual(report['checks']['/favicon.ico']['sha256'],hashlib.sha256(b'synthetic metadata').hexdigest())
 def test_disabled_policy_is_healthy_but_not_enabled(self):
  result=health.snapshot(opener=self.opener());self.assertTrue(result['ok']);self.assertFalse(result['checks']['/api.php?r=privacy']['enabled'])
 def test_approved_policy_must_show_same_version(self):
  self.assertTrue(health.snapshot(opener=self.opener(True))['ok'])
  self.assertFalse(health.snapshot(opener=self.opener(True,('/privacy.php',200,'text/html','Версия: wrong')))['ok'])
 def test_generic_backend_503_fails_and_body_is_not_recorded(self):
  result=health.snapshot(opener=self.opener(False,('/api.php?r=privacy',503,'application/json','{"detail":"SYNTHETIC_SECRET"}')))
  self.assertFalse(result['ok']);self.assertTrue(result['complete']);self.assertNotIn('SYNTHETIC_SECRET',json.dumps(result))
 def test_exposed_backup_or_public_api_fails(self):
  for path,status,kind,text in [('/~.htaccess',200,'text/plain',''),('/api.php?r=leads',200,'application/json','[]')]:
   self.assertFalse(health.snapshot(opener=self.opener(False,(path,status,kind,text)))['ok'])
 def test_public_static_revision_mismatch_is_detected(self):
  report=health.snapshot(opener=self.opener());self.assertTrue(report['ok'])
  health.require_asset_revision(report,{'/script.js':'0'*64});self.assertFalse(report['ok'])
  self.assertEqual(report['checks']['/script.js']['error'],'asset_revision_mismatch')
 def test_network_or_tls_failure_is_not_health(self):
  def fail(*args,**kwargs):raise OSError('synthetic connection failure')
  result=health.snapshot(opener=fail);self.assertFalse(result['ok']);self.assertFalse(result['complete'])

class GovernanceTests(unittest.TestCase):
 def test_protection_preserves_stronger_checks_and_reviews(self):
  old={'required_status_checks':{'contexts':['Legacy check']},'required_pull_request_reviews':{'required_approving_review_count':2},'required_linear_history':{'enabled':True}}
  p=control.protection_payload(old);self.assertEqual(p['required_pull_request_reviews']['required_approving_review_count'],2)
  self.assertIn('Legacy check',[c['context'] for c in p['required_status_checks']['checks']]);self.assertTrue(p['required_linear_history']);self.assertTrue(p['enforce_admins']);self.assertFalse(p['allow_force_pushes'])
 def test_only_independent_current_approval_and_passing_actions_can_merge(self):
  pr={'draft':False,'base':{'ref':'main'},'head':{'repo':{'full_name':control.REPO},'sha':'a'*40},'user':{'login':'author'}}
  reviews=[{'state':'APPROVED','user':{'login':'reviewer'},'commit_id':'a'*40}]
  check={'name':'Validate','head_sha':'a'*40,'status':'completed','conclusion':'success','app':{'id':15368}}
  def allowed(p=pr,r=reviews,c=None):return control.eligible(p,r,[check] if c is None else c,[],{'reviewer':'admin','author':'admin'},1,['Validate'])
  self.assertTrue(allowed());self.assertFalse(allowed(r=[]));self.assertFalse(allowed(p={**pr,'draft':True}))
  self.assertFalse(allowed(r=[{**reviews[0],'commit_id':'b'*40}]))
  self.assertFalse(allowed(r=[{**reviews[0],'user':{'login':'author'}}]))
  self.assertFalse(allowed(c=[{**check,'conclusion':'failure'}]));self.assertFalse(allowed(c=[{**check,'app':{'id':999}}]))
  self.assertFalse(allowed(c=[{**check,'conclusion':'skipped'}]));self.assertFalse(allowed(c=[]))
  self.assertTrue(allowed(p={**pr,'checked_sha':'c'*40},c=[{**check,'head_sha':'c'*40}]))
 def test_bootstrap_accepts_repo_secrets_without_weakening_protection_or_environments(self):
  calls=[];variables={};protected={'enforce_admins':{'enabled':True},'required_status_checks':{'strict':True,'checks':[{'context':'Validate','app_id':15368}]},'required_pull_request_reviews':{'required_approving_review_count':1,'dismiss_stale_reviews':True}}
  def fake(method,path,payload=None,missing=False):
   calls.append((method,path,payload))
   if path=='repos/'+control.REPO and method=='GET':return {'id':123,'full_name':control.REPO,'permissions':{'admin':True},'allow_auto_merge':False}
   if path.endswith('/branches/main/protection'):return protected
   if path.endswith('/heads/main'):return {'object':{'sha':'a'*40}}
   if '/actions/variables/' in path and method=='GET':
    value=variables.get(path.rsplit('/',1)[1]);return {'value':value} if value is not None else None
   if '/actions/variables' in path and method in ['POST','PATCH']:variables[payload['name']]=payload['value'];return None
   if '/deployment-branch-policies?' in path:return {'branch_policies':[{'name':'main','type':'branch'}]}
   if path.endswith('/production') or path.endswith('/automation'):return {'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True},'protection_rules':[{'type':'required_reviewers'}]}
   if '/actions/secrets?' in path:return {'secrets':[{'name':n} for n in ['SSH_HOST','SSH_PORT','SSH_USER','DEPLOY_PATH','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS']]}
   if '/secrets?' in path:return {'secrets':[]}
   raise AssertionError('Unexpected API call '+method+' '+path)
  with patch.object(control,'api',side_effect=fake),patch('sys.stdout',new_callable=io.StringIO):control.bootstrap()
  self.assertEqual(variables['AUTOMATION_READY'],'false');self.assertEqual(variables.get('AUTOMERGE_ENABLED','false'),'false');self.assertEqual(variables['BOOTSTRAP_CONFIGURED_SHA'],'a'*40)
  self.assertFalse(any(m in ['PUT','DELETE'] or ('/secrets' in p and m!='GET') for m,p,v in calls))
  self.assertTrue(protected['required_pull_request_reviews']['dismiss_stale_reviews'])
 def test_bootstrap_never_mutates_when_admin_read_is_blocked(self):
  with patch.object(control,'api',side_effect=control.GitHubFailure('blocked')) as api:
   with self.assertRaises(control.GitHubFailure):control.bootstrap()
  self.assertEqual(api.call_count,1);self.assertEqual(api.call_args.args[0],'GET')
 def test_validated_branch_creates_pr_without_executing_branch_code(self):
  import test_pr_automation
  case=test_pr_automation.PrAutomation('test_success_creates_one_pr_with_merge_disabled')
  result=unittest.TestResult();case.run(result);self.assertTrue(result.wasSuccessful(),str(result.errors)+str(result.failures))



 def test_native_actions_uses_active_review_ruleset_without_admin_token(self):
  rules=[{'type':'pull_request','parameters':{'required_approving_review_count':1,'dismiss_stale_reviews_on_push':True}}, {'type':'required_status_checks','parameters':{'strict_required_status_checks_policy':True,'required_status_checks':[{'context':'Validate','integration_id':15368}]}}]
  def fake(method,path,*args,**kwargs):
   if path.endswith('/protection'):raise control.GitHubFailure('not admin')
   return rules
  with patch.object(control,'api',side_effect=fake):self.assertEqual(control.required_policy('repos/'+control.REPO)[1:],(1,['Validate']))
  rules[0]['parameters']['required_approving_review_count']=0
  with patch.object(control,'api',side_effect=fake):
   with self.assertRaises(control.GitHubFailure):control.required_policy('repos/'+control.REPO)
 def test_token_merge_dispatches_main_ci_automatically_but_not_old_workflow(self):
  import base64
  calls=[]
  def fake(method,path,payload=None,**kwargs):
   calls.append((method,path,payload))
   if path.endswith('/heads/main'):return {'object':{'sha':'a'*40}}
   if '/runs?' in path:return {'workflow_runs':[]}
   if '/contents/' in path:return {'content':base64.b64encode(b'name: NeuroDelo CI/CD\noperation:\nexpected_revision:').decode()}
   return None
  with patch.dict(os.environ,{'GITHUB_TOKEN_FALLBACK':'true','AUTOMATION_READY':'true'}),patch.object(control,'api',side_effect=fake),patch('sys.stdout',new_callable=io.StringIO):control.ensure_main_ci()
  self.assertEqual(calls[-1][0],'POST');self.assertEqual(calls[-1][2],{'ref':'main','inputs':{'operation':'deploy','expected_revision':'a'*40}})

if __name__=='__main__':unittest.main()
