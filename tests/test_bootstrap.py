"""Bootstrap administrative contracts. No real GitHub writes, SSH or customer data."""
import copy
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/github'))
import bootstrap
import control
sys.path.insert(0,str(ROOT/'scripts/deploy'))
import client

class BootstrapSafety(unittest.TestCase):
 def proof(self):
  policy=json.loads((ROOT/'scripts/deploy/policy.json').read_text());hashes={prefix+'/'+name:'b'*64 for prefix,key in [('public_html','public_files'),('private','private_files')] for name in policy[key]};checks={'/':{'ok':True}}
  checks.update({'/'+path.split('/',1)[1]:{'ok':True,'sha256':digest} for path,digest in hashes.items() if path.startswith('public_html/') and path.endswith(('.js','.css'))})
  return {'mode':'bootstrap','result':'deployed_and_verified','revision':'a'*40,
   'before':{'ok':True,'complete':True,'checks':{'/':{'ok':True}}},'after':{'ok':True,'complete':True,'checks':checks},
   'apply':{'revision':'a'*40,'backup_verified':True,'recovery_verified':True,'migrations':[],'files_sha256':hashes},'finalize':{'revision':'a'*40,'files_verified':True}}
 def test_evidence_requires_actual_recovery_health_and_revision(self):
  bootstrap.verify_report(self.proof(),'a'*40)
  for path,value in [('mode','deploy'),('revision','c'*40),('result','failed'),('apply.recovery_verified',False),('apply.backup_verified',False),('apply.migrations',['004_crm_foundation']),('apply.files_sha256',{}),('after.complete',False),('before.ok',False),('after.checks',{}),('finalize.files_verified',False)]:
   d=self.proof();parts=path.split('.');target=d
   for part in parts[:-1]:target=target[part]
   target[parts[-1]]=value
   with self.subTest(path=path),self.assertRaises(control.GitHubFailure):bootstrap.verify_report(d,'a'*40)
 def test_promotion_never_writes_before_verified_evidence_and_current_main(self):
  def fake(method,path,payload=None,**kwargs):
   if path=='repos/'+control.REPO:return {'full_name':control.REPO,'permissions':{'admin':True}}
   if path.endswith('/heads/main'):return {'object':{'sha':'c'*40}}
   raise AssertionError('Unexpected write or endpoint')
  with patch.object(bootstrap,'api',side_effect=fake),patch.object(bootstrap,'required_delivery_policy'),patch.object(bootstrap,'verify_environment'),patch.object(bootstrap,'read_report',return_value=({'head_sha':'a'*40},self.proof())),patch.object(bootstrap,'set_variable') as write:
   with self.assertRaises(control.GitHubFailure):bootstrap.promote('123')
   write.assert_not_called()
 def test_promote_ready_is_last_and_clears_single_use_smoke_authorization(self):
  def fake(method,path,*args,**kwargs):return {'full_name':control.REPO,'permissions':{'admin':True}} if path=='repos/'+control.REPO else {'object':{'sha':'a'*40}}
  with patch.object(bootstrap,'api',side_effect=fake),patch.object(bootstrap,'required_delivery_policy'),patch.object(bootstrap,'verify_environment'),patch.object(bootstrap,'read_report',return_value=({'head_sha':'a'*40},self.proof())),patch.object(bootstrap,'set_variable') as write,patch('sys.stdout',new_callable=io.StringIO):bootstrap.promote('123')
  self.assertEqual(write.call_args.args[1:],('AUTOMATION_READY','true'));self.assertIn(('BOOTSTRAP_APPROVED_SHA',''),[c.args[1:] for c in write.call_args_list])
 def test_main_only_environment_does_not_accept_tags_wildcards_or_protected_branches(self):
  for policy in [{'name':'*','type':'branch'},{'name':'main','type':'tag'},{'name':'feature/*','type':'branch'}]:
   with patch.object(control,'api',return_value={'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}}),patch.object(control,'pages',return_value=[policy]):
    with self.assertRaises(control.GitHubFailure):control.verify_environment('repos/'+control.REPO,'production')
 def test_partial_secret_scope_union_is_accepted_and_missing_is_rejected(self):
  repo=[{'name':n} for n in ['SSH_HOST','SSH_USER','SSH_PORT']];env=[{'name':n} for n in ['DEPLOY_PATH','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS']]
  with patch.object(control,'pages',side_effect=[repo,env]):self.assertEqual(len(control.secret_metadata('repos/'+control.REPO,1)['repository']),3)
  with patch.object(control,'pages',side_effect=[repo,env[:-1]]),self.assertRaises(control.GitHubFailure):control.secret_metadata('repos/'+control.REPO,1)
 def test_single_owner_ci_only_mode_is_not_enabled_without_confirmation(self):
  policy={'enforce_admins':{'enabled':True},'required_pull_request_reviews':{'required_approving_review_count':0},'required_status_checks':{'strict':True,'checks':[{'context':'Validate','app_id':15368}]}}
  with self.assertRaises(control.GitHubFailure):control.verify_protection(policy)

 def test_release_checks_accept_main_validate_only_but_not_unprotected_release(self):
  base='repos/'+control.REPO
  protected={'required_status_checks':{'strict':True,'checks':[{'context':'Validate','app_id':15368}]}}
  with patch.object(control,'api',return_value=protected):
   self.assertTrue(control.required_delivery_policy(base))
  for broken in [
   {'required_status_checks':{'strict':False,'checks':[{'context':'Validate','app_id':15368}]}},
   {'required_status_checks':{'strict':True,'checks':[{'context':'Validate','app_id':999}]}}
  ]:
   with patch.object(control,'api',return_value=broken),self.assertRaises(control.GitHubFailure):
    control.required_delivery_policy(base)
  def denied(method,path,*args,**kwargs):
   if path.endswith('/branches/main/protection'):raise control.GitHubFailure('Forbidden')
   return []
  with patch.object(control,'api',side_effect=denied),self.assertRaises(control.GitHubFailure):
   control.required_delivery_policy(base)

 def test_initial_configuration_keeps_auto_merge_and_delivery_off(self):
  repo={'full_name':control.REPO,'permissions':{'admin':True},'id':42,'allow_auto_merge':True}
  def fake(method,path,*args,**kwargs):
   if path=='repos/'+control.REPO:return repo
   if path.endswith('/AUTOMERGE_APP_ID'):return None
   if path.endswith('/heads/main'):return {'object':{'sha':'a'*40}}
   raise AssertionError('Unexpected request '+path)
  with patch.object(control,'api',side_effect=fake),patch.object(control,'required_delivery_policy'),patch.object(control,'verify_environment'),patch.object(control,'secret_metadata',return_value={'repository':set(),'production':set()}),patch.object(control,'set_variable') as write,patch('sys.stdout',new_callable=io.StringIO):
   control.bootstrap()
  settings={call.args[1]:call.args[2] for call in write.call_args_list}
  self.assertEqual(settings['AUTOMATION_READY'],'false')
  self.assertEqual(settings['BOOTSTRAP_APPROVED_SHA'],'')
  self.assertEqual(settings['AUTOMERGE_ENABLED'],'false')
  self.assertEqual(settings['BOOTSTRAP_CONFIGURED_SHA'],'a'*40)

 def test_bootstrap_unhealthy_baseline_stops_before_transfer_or_backup(self):
  calls=[]
  class Remote:
   def preflight(self):calls.append('preflight');return {'ok':True}
   def stage(self,*a):calls.append('stage');raise AssertionError('No writes')
  r=client.coordinate(Remote(),'bootstrap',snapshot=lambda:{'ok':False,'complete':True,'checks':{}},attempts=1)
  self.assertEqual(r['error'],'bootstrap_requires_healthy_baseline');self.assertEqual(calls,['preflight'])

 def test_forged_validate_commit_status_cannot_replace_actions_check(self):
  pr={'draft':False,'base':{'ref':'main'},'head':{'repo':{'full_name':control.REPO},'sha':'a'*40},'user':{'login':'author'}}
  reviews=[{'state':'APPROVED','user':{'login':'reviewer'},'commit_id':'a'*40}]
  self.assertFalse(control.eligible(pr,reviews,[],[{'state':'success','context':'Validate'}],{'reviewer':'admin'},1,['Validate']))
 def test_old_dispatch_contract_is_rejected_and_existing_run_not_duplicated(self):
  import base64
  calls=[]
  def fake(method,path,payload=None,**kwargs):
   calls.append((method,path))
   if path.endswith('/heads/main'):return {'object':{'sha':'a'*40}}
   if '/runs?' in path:return {'workflow_runs':[]}
   return {'content':base64.b64encode(b'name: NeuroDelo CI/CD\noperation:').decode()}
  with patch.dict(control.os.environ,{'GITHUB_TOKEN_FALLBACK':'true','AUTOMATION_READY':'true'}),patch.object(control,'api',side_effect=fake),self.assertRaises(control.GitHubFailure):control.ensure_main_ci()
  self.assertFalse(any(m=='POST' for m,p in calls))

 def test_initial_smoke_dispatch_requires_fresh_main_validate_and_exact_owner_sha(self):
  import base64
  calls=[];runs=[]
  def fake(method,path,payload=None,**kwargs):
   calls.append((method,path,payload))
   if path.endswith('/heads/main'):return {'object':{'sha':'a'*40}}
   if '/runs?' in path:return {'workflow_runs':runs}
   if '/jobs?' in path:return {'jobs':[{'name':'Validate','conclusion':'success'}]}
   if '/contents/' in path:return {'content':base64.b64encode(b'name: NeuroDelo CI/CD\noperation:\nexpected_revision:').decode()}
  env={'GITHUB_TOKEN_FALLBACK':'true','AUTOMATION_READY':'false','BOOTSTRAP_APPROVED_SHA':'a'*40,'BOOTSTRAP_CONFIGURED_SHA':'a'*40}
  with patch.dict(control.os.environ,env),patch.object(control,'api',side_effect=fake),patch('sys.stdout',new_callable=io.StringIO):control.ensure_main_ci()
  self.assertEqual(calls[-1][2]['inputs']['operation'],'preview')
  runs.append({'id':1,'head_sha':'a'*40,'status':'completed','conclusion':'success','event':'push'})
  with patch.dict(control.os.environ,env),patch.object(control,'api',side_effect=fake),patch('sys.stdout',new_callable=io.StringIO):control.ensure_main_ci()
  self.assertEqual(calls[-1][2]['inputs'],{'operation':'bootstrap','expected_revision':'a'*40})
  runs.append({'head_sha':'a'*40,'event':'workflow_dispatch','display_title':'bootstrap '+'a'*40})
  calls.clear()
  with patch.dict(control.os.environ,env),patch.object(control,'api',side_effect=fake):control.ensure_main_ci()
  self.assertFalse(any(m=='POST' for m,p,d in calls))

 def test_trusted_report_archive_is_read_and_untrusted_run_is_rejected(self):
  import zipfile
  from types import SimpleNamespace
  data=io.BytesIO()
  with zipfile.ZipFile(data,'w') as z:z.writestr('deployment-report.json',json.dumps(self.proof()))
  run={'status':'completed','head_branch':'main','head_repository':{'full_name':control.REPO},'path':'.github/workflows/deploy.yml','event':'workflow_dispatch','conclusion':'success','head_sha':'a'*40}
  def fake(method,path,*a,**kw):
   if path.endswith('/123'):return run
   if '/jobs?' in path:return {'jobs':[{'name':n,'conclusion':'success'} for n in ['Validate','Publish approved main']]}
   if '/artifacts?' in path:return {'artifacts':[{'id':1,'name':'deployment-evidence-123-1','size_in_bytes':len(data.getvalue()),'expired':False}]}
   raise AssertionError('Unexpected endpoint')
  with patch.object(bootstrap,'api',side_effect=fake),patch.object(bootstrap.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout=data.getvalue())):self.assertEqual(bootstrap.read_report('repos/'+control.REPO,'123')[0]['head_sha'],'a'*40)
  run['head_branch']='feature/untrusted'
  with patch.object(bootstrap,'api',side_effect=fake),self.assertRaises(control.GitHubFailure):bootstrap.read_report('repos/'+control.REPO,'123')
 def test_administration_workflow_is_manual_main_only_and_has_no_ssh(self):
  import yaml
  w=yaml.load((ROOT/'.github/workflows/bootstrap.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertEqual(set(w['on']),{'workflow_dispatch'});job=w['jobs']['administration'];self.assertEqual(job['if'],"github.ref == 'refs/heads/main'");self.assertEqual(job['environment'],'automation');self.assertNotIn('SSH_',str(w));self.assertNotIn('DEPLOY_PATH',str(w))
  self.assertIn('bootstrap --apply',str(w));self.assertIn('promote --run-id',str(w));self.assertNotIn('rsync',str(w))

if __name__=='__main__':unittest.main()
