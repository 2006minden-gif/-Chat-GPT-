"""PR creation is independent of merge permission; no real API calls in this suite."""
import base64
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import yaml
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('pr_control',ROOT/'scripts/github/control.py');control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)

class PrAutomation(unittest.TestCase):
 def setUp(self):
  self.sha='a'*40;self.branch='feature/example';self.calls=[];self.existing=[];self.heads=[self.sha,self.sha];self.ahead=1;self.post_error=None;self.definition_changed=False
  self.run={'id':77,'head_sha':self.sha,'head_branch':self.branch,'event':'push','status':'completed','conclusion':'success','head_repository':{'full_name':control.REPO},'repository':{'full_name':control.REPO},'path':'.github/workflows/deploy.yml','workflow_id':9}
  self.jobs=[{'name':'Validate','conclusion':'success'}]
  self.env=patch.dict(os.environ,{'AUTOMERGE_ENABLED':'false','GITHUB_TOKEN_FALLBACK':'false'});self.env.start();self.addCleanup(self.env.stop)
 def api(self,method,path,payload=None,**kwargs):
  self.calls.append((method,path,payload))
  if '/jobs?' in path:return {'jobs':self.jobs}
  if '/actions/runs/77' in path:return self.run
  if path.endswith('/actions/workflows/deploy.yml'):return {'id':9}
  if '/git/ref/heads/main' in path:return {'object':{'sha':'b'*40}}
  if '/git/ref/heads/' in path:return {'object':{'sha':self.heads.pop(0) if len(self.heads)>1 else self.heads[0]}}
  if '/compare/' in path:return {'ahead_by':self.ahead}
  if '/contents/' in path:
   text=b'trusted ci'
   if self.definition_changed and path.endswith(self.sha):text=b'no op'
   return {'content':base64.b64encode(text).decode()}
  if method=='GET' and '/pulls?' in path:return self.existing
  if method=='POST' and path.endswith('/pulls'):
   if self.post_error:
    if 'HTTP 422' in self.post_error:self.existing=[{'number':4}]
    raise control.GitHubFailure(self.post_error)
   self.existing=[{'number':4}];return self.existing[0]
  if method=='POST' and path.endswith('/dispatches'):return None
  raise AssertionError('Unexpected API request '+method+' '+path)
 def invoke(self):
  with patch.object(control,'api',side_effect=self.api),patch('sys.stdout',new_callable=io.StringIO),patch.object(control,'required_policy',side_effect=AssertionError('PR creation must not inspect merge governance')):
   return control.ensure_pr_for_validated_branch('77')
 def posts(self):return [c for c in self.calls if c[0]=='POST' and c[1].endswith('/pulls')]
 def test_success_creates_one_pr_with_merge_disabled(self):
  self.assertEqual(self.invoke()['number'],4);self.assertEqual(len(self.posts()),1)
  self.assertEqual(self.posts()[0][2]['base'],'main');self.assertIn(self.sha,self.posts()[0][2]['body'])
 def test_replay_does_not_duplicate(self):
  self.invoke();self.invoke();self.assertEqual(len(self.posts()),1)
 def test_existing_stacked_pr_preserved(self):
  self.existing=[{'number':22,'base':{'ref':'feature/dependency'}}];self.assertEqual(self.invoke()['number'],22);self.assertEqual(self.posts(),[])
 def test_failed_queued_forked_or_other_workflow_run_is_rejected(self):
  for k,v in [('conclusion','failure'),('status','in_progress'),('head_repository',{'full_name':'fork/repo'}),('repository',{'full_name':'other/repo'}),('path','.github/workflows/untrusted.yml'),('workflow_id',123)]:
   with self.subTest(k=k),patch.dict(self.run,{k:v}):
    with self.assertRaises(control.GitHubFailure):self.invoke()
  self.assertEqual(self.posts(),[])
 def test_skipped_validate_job_is_not_success(self):
  self.jobs=[{'name':'Validate','conclusion':'skipped'}]
  with self.assertRaises(control.GitHubFailure):self.invoke()
  self.assertEqual(self.posts(),[])
 def test_stale_head_at_start_and_before_write(self):
  for heads in [['c'*40],['a'*40,'c'*40]]:
   self.heads=heads;self.assertIsNone(self.invoke())
  self.assertEqual(self.posts(),[])
 def test_no_changes_ahead_of_main(self):
  self.ahead=0;self.assertIsNone(self.invoke());self.assertEqual(self.posts(),[])
 def test_untrusted_ci_definition_is_not_accepted(self):
  self.definition_changed=True
  with self.assertRaisesRegex(control.GitHubFailure,'CI definition changed'):self.invoke()
  self.assertEqual(self.posts(),[])
 def test_concurrent_duplicate_422_recovers_existing_pr(self):
  self.post_error='HTTP 422 invalid_request';self.assertEqual(self.invoke()['number'],4);self.assertEqual(len(self.posts()),1)
 def test_missing_permission_has_actionable_bounded_diagnostic(self):
  self.post_error='HTTP 403 insufficient_permissions_or_policy'
  with self.assertRaisesRegex(control.GitHubFailure,'pull_requests:write'):self.invoke()
 def test_native_token_requests_branch_validation_without_production_dispatch(self):
  with patch.dict(os.environ,{'GITHUB_TOKEN_FALLBACK':'true'}):self.invoke()
  dispatch=[p for m,u,p in self.calls if m=='POST' and u.endswith('/dispatches')]
  self.assertEqual(dispatch,[{'ref':self.branch,'inputs':{'operation':'preview','expected_revision':self.sha}}])
 def test_forged_workflow_event_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'event.json';p.write_text(json.dumps({'workflow_run':{**self.run,'head_sha':'d'*40}}))
   with patch.dict(os.environ,{'GITHUB_EVENT_NAME':'workflow_run','GITHUB_EVENT_PATH':str(p)}),patch.object(control,'api',side_effect=self.api):
    with self.assertRaisesRegex(control.GitHubFailure,'does not match'):control.ensure_pr_for_validated_branch()
 def test_invalid_run_id_rejected_before_network(self):
  with patch.object(control,'api',side_effect=AssertionError('network not permitted')):
   with self.assertRaises(control.GitHubFailure):control.ensure_pr_for_validated_branch('77; echo bad')

class WorkflowSeparation(unittest.TestCase):
 def test_pr_creation_not_gated_by_auto_merge_and_uses_main_only(self):
  w=yaml.load((ROOT/'.github/workflows/auto-merge.yml').read_text(),Loader=yaml.BaseLoader)
  j=w['jobs']['create_pr'];self.assertNotIn('AUTOMERGE_ENABLED',str(j));self.assertNotIn('needs',j)
  for text in ["github.ref == 'refs/heads/main'","head_branch != 'main'","conclusion == 'success'","head_repository.full_name == github.repository"]:self.assertIn(text,j['if'])
  self.assertEqual(j['steps'][0]['with']['ref'],'main');self.assertEqual(j['environment'],'automation');self.assertEqual(j['concurrency']['cancel-in-progress'],'false')
  self.assertNotIn('download-artifact',str(j));self.assertNotIn('SSH_',str(j));self.assertEqual(j['permissions']['pull-requests'],'write')
  self.assertIn("vars.AUTOMERGE_ENABLED == 'true'",w['jobs']['approved']['if'])
 def test_merge_operation_no_longer_calls_pr_creation(self):
  source=(ROOT/'scripts/github/control.py').read_text();merge=source[source.index('def auto_merge():'):source.index("if __name__=='__main__':")]
  self.assertNotIn('ensure_pr_for_validated_branch',merge);self.assertIn('required_policy(base)',merge);self.assertIn("reviewDecision')!='APPROVED'",merge)
