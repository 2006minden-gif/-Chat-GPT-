"""Automatic CI/CD contracts; never dispatches a workflow or connects to SpaceWeb."""
from pathlib import Path
import re
import subprocess
import os
import tempfile
import unittest
import yaml
ROOT=Path(__file__).resolve().parents[1]

class DeploymentSafety(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.w=yaml.load((ROOT/'.github/workflows/deploy.yml').read_text(),Loader=yaml.BaseLoader)
 def test_ci_for_main_and_pull_requests(self):
  self.assertEqual(self.w['on']['push']['branches'],['**']);self.assertEqual(self.w['on']['pull_request']['branches'],['main'])
  self.assertIn('workflow_dispatch',self.w['on']);self.assertNotIn('pull_request_target',self.w['on'])
  self.assertNotIn('dry_run',self.w['on']['workflow_dispatch']['inputs'])
 def test_deployment_requires_success_and_main(self):
  job=self.w['jobs']['deploy'];self.assertEqual(job['needs'],'validate')
  self.assertIn("github.ref == 'refs/heads/main'",job['if']);self.assertNotIn('always()',job['if'])
  self.assertIn("github.event_name == 'push'",job['if']);self.assertNotIn('pull_request',job['if'])
  self.assertEqual(job['concurrency'],{'group':'spaceweb-production','cancel-in-progress':'false'})
  self.assertEqual(job['environment']['name'],'production')
 def test_no_production_secrets_in_ci(self):
  self.assertNotIn('secrets.',str(self.w['jobs']['validate']))
  steps=self.w['jobs']['deploy']['steps'];secret_steps=[s for s in steps if 'secrets.' in str(s)]
  self.assertEqual(len(secret_steps),1);self.assertEqual(secret_steps[0]['name'],'Publish or maintain checked release')
  self.assertEqual(self.w['permissions'],{'contents':'read'})
 def test_reproducible_required_tests(self):
  job=self.w['jobs']['validate'];self.assertEqual(job['services']['mysql']['image'],'mysql:5.7.44')
  code='\n'.join(s.get('run','') for s in job['steps'])
  for marker in ['php -l','node --check','unittest discover','api-client.test.cjs','release.py --check','sha256sum -c']:
   self.assertIn(marker,code)
  self.assertNotIn('continue-on-error',str(job));self.assertNotIn('|| true',code)
  php=[s for s in job['steps'] if s.get('uses','').startswith('shivammathur/')][0]
  self.assertEqual(php['with']['php-version'],'8.4')
 def test_artifact_pinning_and_hidden_security_files(self):
  upload=[s for s in self.w['jobs']['validate']['steps'] if s.get('uses','').startswith('actions/upload-artifact')][0]
  self.assertEqual(upload['with']['include-hidden-files'],'true');self.assertEqual(upload['with']['if-no-files-found'],'error')
  for path in (ROOT/'.github/workflows').glob('*.yml'):
   workflow=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
   for job in workflow['jobs'].values():
    for step in job.get('steps',[]):
     if 'uses' in step:self.assertRegex(step['uses'],r'@[a-f0-9]{40}$')
 def test_auto_merge_uses_trusted_main_and_app_token(self):
  w=yaml.load((ROOT/'.github/workflows/auto-merge.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertNotIn('pull_request_target',w['on']);self.assertNotIn('pull_request_review',w['on'])
  self.assertIn('schedule',w['on']);job=w['jobs']['approved'];self.assertEqual(job['environment'],'automation')
  self.assertEqual(job['steps'][0]['with']['ref'],'main')
  self.assertTrue(any(s.get('uses','').startswith('actions/create-github-app-token@') for s in job['steps']))
  self.assertNotIn('SSH_PRIVATE_KEY',str(w));self.assertNotIn('download-artifact',str(w))
 def test_stale_main_validation_never_configures_and_is_not_a_failure(self):
  w=yaml.load((ROOT/'.github/workflows/auto-merge.yml').read_text(),Loader=yaml.BaseLoader)
  job=w['jobs']['configure_validated_main'];steps=job['steps']
  self.assertEqual(steps[0]['id'],'current')
  self.assertEqual(steps[1]['if'],"steps.current.outputs.current == 'true'")
  self.assertEqual(steps[2]['if'],"steps.current.outputs.current == 'true'")
  self.assertIn('ref',steps[1]['with'])
  self.assertNotIn('|| true',steps[0]['run'])
  with tempfile.TemporaryDirectory() as tmp:
   output=Path(tmp)/'github-output'
   for current,validated,expected in [('b'*40,'a'*40,'current=false'),('a'*40,'a'*40,'current=true')]:
    output.write_text('')
    script='gh() { printf "%s\\n" "$CURRENT_SHA"; }\\n'+steps[0]['run']
    result=subprocess.run(['bash','-e'],input=script,text=True,env=dict(os.environ,GITHUB_OUTPUT=str(output),GITHUB_REPOSITORY='2006minden-gif/-Chat-GPT-',CURRENT_SHA=current,VALIDATED=validated),capture_output=True)
    self.assertEqual(result.returncode,0,result.stderr)
    self.assertIn(expected,output.read_text())

 def test_bootstrap_and_native_dispatch_are_sha_bound_and_keep_ready_closed(self):
  inputs=self.w['on']['workflow_dispatch']['inputs'];self.assertIn('bootstrap',inputs['operation']['options']);self.assertIn('expected_revision',inputs)
  job=self.w['jobs']['deploy'];self.assertIn("vars.AUTOMATION_READY == 'true'",job['if']);self.assertIn('BOOTSTRAP_CONFIGURED_SHA == github.sha',job['if']);self.assertIn('BOOTSTRAP_APPROVED_SHA == github.sha',job['if']);self.assertIn('BOOTSTRAP_VERIFIED_RUN',job['if']);self.assertNotIn("inputs.operation != 'deploy'",job['if']);self.assertIn("inputs.operation == 'rollback'",job['if'])
  names=[s.get('name') for s in job['steps']];self.assertLess(names.index('Recheck production environment before secret use'),names.index('Publish or maintain checked release'))
  code='\n'.join(s.get('run','') for s in self.w['jobs']['validate']['steps']);self.assertIn('$EXPECTED',code);self.assertIn('$REVISION',code)
 def test_release_gate_bootstraps_without_circular_proof_but_never_bypasses_validation(self):
  # Execute the actual workflow expression with synthetic GitHub contexts.
  expression=self.w['jobs']['deploy']['if']
  def allowed(**changes):
   context={'inputs.validation_only':False,'vars.AUTOMATION_READY':'false',
    'vars.BOOTSTRAP_VERIFIED_RUN':'','vars.BOOTSTRAP_VERIFIED_SHA':'',
    'vars.BOOTSTRAP_APPROVED_SHA':'a'*40,'vars.BOOTSTRAP_CONFIGURED_SHA':'a'*40,
    'vars.DEPLOY_PAUSED':'false','github.ref':'refs/heads/main',
    'github.event_name':'workflow_dispatch','inputs.operation':'bootstrap','github.sha':'a'*40}
   context.update(changes)
   code=expression
   for key in sorted(context,key=len,reverse=True):code=code.replace(key,repr(context[key]))
   code=code.replace('&&',' and ').replace('||',' or ')
   code=re.sub(r'\btrue\b','True',code)
   return eval(' '.join(code.split()),{'__builtins__':{}},{})
  self.assertTrue(allowed())
  for changes in [{'inputs.validation_only':True},{'vars.BOOTSTRAP_APPROVED_SHA':'b'*40},
   {'vars.BOOTSTRAP_CONFIGURED_SHA':''},{'vars.DEPLOY_PAUSED':'true'},
   {'github.ref':'refs/heads/feature'},{'github.event_name':'push'},
   {'inputs.operation':'deploy'},{'github.event_name':'pull_request'}]:
   with self.subTest(changes=changes):self.assertFalse(allowed(**changes))
  routine={'github.event_name':'push','inputs.operation':'','vars.AUTOMATION_READY':'true',
   'vars.BOOTSTRAP_VERIFIED_RUN':'123','vars.BOOTSTRAP_VERIFIED_SHA':'b'*40}
  self.assertTrue(allowed(**routine))
  for missing in ['vars.BOOTSTRAP_VERIFIED_RUN','vars.BOOTSTRAP_VERIFIED_SHA']:
   self.assertFalse(allowed(**dict(routine,**{missing:''})))
  self.assertFalse(allowed(**dict(routine,**{'inputs.validation_only':True})))
  repair=yaml.load((ROOT/'.github/workflows/production-repair.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertEqual(repair['jobs']['validate']['with']['validation_only'],'true')
  self.assertEqual(repair['jobs']['repair']['needs'],'validate')
  self.assertEqual(repair['jobs']['repair']['concurrency']['group'],'spaceweb-production')
 def test_shell_syntax(self):
  for path in (ROOT/'.github/workflows').glob('*.yml'):
   w=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
   for job in w['jobs'].values():
    for step in job.get('steps',[]):
     if 'run' in step:subprocess.run(['bash','-n'],input=step['run'],text=True,check=True)

if __name__=='__main__':unittest.main()
