"""Automatic CI/CD contracts; never dispatches a workflow or connects to SpaceWeb."""
from pathlib import Path
import re
import subprocess
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
    for step in job['steps']:
     if 'uses' in step:self.assertRegex(step['uses'],r'@[a-f0-9]{40}$')
 def test_auto_merge_uses_trusted_main_and_app_token(self):
  w=yaml.load((ROOT/'.github/workflows/auto-merge.yml').read_text(),Loader=yaml.BaseLoader)
  self.assertNotIn('pull_request_target',w['on']);self.assertNotIn('pull_request_review',w['on'])
  self.assertIn('schedule',w['on']);job=w['jobs']['approved'];self.assertEqual(job['environment'],'automation')
  self.assertEqual(job['steps'][0]['with']['ref'],'main')
  self.assertTrue(any(s.get('uses','').startswith('actions/create-github-app-token@') for s in job['steps']))
  self.assertNotIn('SSH_PRIVATE_KEY',str(w));self.assertNotIn('download-artifact',str(w))
 def test_shell_syntax(self):
  for path in (ROOT/'.github/workflows').glob('*.yml'):
   w=yaml.load(path.read_text(),Loader=yaml.BaseLoader)
   for job in w['jobs'].values():
    for step in job['steps']:
     if 'run' in step:subprocess.run(['bash','-n'],input=step['run'],text=True,check=True)

if __name__=='__main__':unittest.main()
