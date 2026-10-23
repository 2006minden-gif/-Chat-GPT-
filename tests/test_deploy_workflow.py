"""Deployment safety contracts. Needs PyYAML; SSH/rsync are synthetic local stubs.
No host connection, real credential access or GitHub workflow dispatch is performed.
"""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import yaml

ROOT = Path(__file__).resolve().parents[1]

class DeploymentSafety(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # BaseLoader preserves GitHub's YAML 1.2 `on` key (not YAML 1.1 boolean True).
        cls.workflow = yaml.load((ROOT / '.github/workflows/deploy.yml').read_text(), Loader=yaml.BaseLoader)
        cls.job = cls.workflow['jobs']['deploy']
        cls.steps = {s['name']: s for s in cls.job['steps'] if 'name' in s}

    def test_only_explicit_manual_main_run(self):
        self.assertEqual(set(self.workflow['on']), {'workflow_dispatch'})
        self.assertEqual(self.job['if'], "github.event_name == 'workflow_dispatch' && github.ref == 'refs/heads/main'")
        inputs = self.workflow['on']['workflow_dispatch']['inputs']
        self.assertEqual(inputs['dry_run']['type'], 'boolean')
        self.assertEqual(inputs['dry_run']['default'], 'true')
        self.assertEqual(inputs['publish_confirmation']['default'], '')
        self.assertEqual(self.job['env']['DRY_RUN'], '${{ inputs.dry_run != false }}')
        self.assertEqual(self.job['steps'][0]['name'], 'Validate manual authorization')
        self.assertEqual(self.workflow['permissions'], {'contents': 'read'})

    def authorize(self, dry_run, confirmation='', enabled=''):
        env = dict(os.environ, DRY_RUN=dry_run, PUBLISH_CONFIRMATION=confirmation, PUBLISH_ENABLED=enabled)
        return subprocess.run(['bash', '-c', self.steps['Validate manual authorization']['run']], env=env, capture_output=True)

    def test_publishing_requires_confirmation_and_enabled_flag(self):
        for dry_run, confirmation, enabled, allowed in [
            ('true', '', '', True), ('true', '', 'true', True),
            ('false', '', 'true', False), ('false', 'PUBLISH neurodelo.pro', '', False),
            ('false', 'PUBLISH neurodelo.pro', 'false', False),
            ('false', 'PUBLISH neurodelo.pro', 'true', True),
            ('false', 'PUBLISH another-domain', 'true', False),
            ('', 'PUBLISH neurodelo.pro', 'true', False),
            ('invalid', 'PUBLISH neurodelo.pro', 'true', False),
        ]:
            with self.subTest(dry_run=dry_run, confirmation=confirmation, enabled=enabled):
                self.assertEqual(self.authorize(dry_run, confirmation, enabled).returncode == 0, allowed)
        self.assertEqual(self.steps['Validate manual authorization']['env']['PUBLISH_CONFIRMATION'], '${{ inputs.publish_confirmation }}')
        with tempfile.TemporaryDirectory() as tmp:
            marker = Path(tmp) / 'injected'
            self.assertNotEqual(self.authorize('false', '$(touch ' + str(marker) + ')', 'true').returncode, 0)
            self.assertFalse(marker.exists())

    def test_shell_syntax(self):
        for step in self.job['steps']:
            if 'run' in step:
                with self.subTest(step=step['name']):
                    subprocess.run(['bash', '-n'], input=step['run'], text=True, check=True)

    def simulate_remote_steps(self, dry_run):
        # This is local contract simulation, not an Actions runner or remote smoke test.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp); log = tmp / 'calls.jsonl'
            stub = '''#!/usr/bin/env python3
import json,os,sys
from pathlib import Path
entry={'command':Path(sys.argv[0]).name,'args':sys.argv[1:]}
if entry['command']=='ssh':entry['script']=sys.stdin.read()
with open(os.environ['WORKFLOW_TEST_LOG'],'a') as f:f.write(json.dumps(entry)+'\\n')
'''
            for name in ['ssh', 'rsync']:
                p = tmp / name; p.write_text(stub); p.chmod(0o700)
            env = dict(os.environ, PATH=str(tmp) + os.pathsep + os.environ['PATH'],
                       DRY_RUN=dry_run, DEPLOY_PATH='/home/n/neurodepro/public_html', WORKFLOW_TEST_LOG=str(log))
            backup = self.steps['Back up current files before publishing']
            self.assertEqual(backup['if'], "env.DRY_RUN != 'true'")
            selected = [self.steps['Verify server and existing installation']]
            if dry_run != 'true': selected.append(backup)
            selected.append(self.steps['Publish or preview files'])
            for step in selected:
                subprocess.run(['bash', '-c', step['run']], env=env, cwd=ROOT, check=True, capture_output=True)
            return [json.loads(line) for line in log.read_text().splitlines()]

    def test_dry_run_never_selects_backup_and_both_syncs_are_dry(self):
        calls = self.simulate_remote_steps('true')
        ssh = [c for c in calls if c['command'] == 'ssh']
        self.assertEqual(len(ssh), 1)
        self.assertNotRegex(ssh[0]['script'], r'\b(mkdir|chmod|rm|mv|cp)\b|tar\s+-c')
        syncs = [c for c in calls if c['command'] == 'rsync']
        self.assertEqual(len(syncs), 2)
        for call in syncs: self.assertIn('--dry-run', call['args'])

    def test_authorized_publishing_retains_backup_and_exclusions(self):
        calls = self.simulate_remote_steps('false')
        ssh = [c for c in calls if c['command'] == 'ssh']
        self.assertEqual(len(ssh), 2)
        self.assertIn('umask 077', ssh[1]['script'])
        self.assertIn('tar -czf', ssh[1]['script'])
        syncs = [c for c in calls if c['command'] == 'rsync']
        self.assertEqual(len(syncs), 2)
        for c in syncs:
            self.assertNotIn('--dry-run', c['args']); self.assertNotIn('--delete', c['args'])
        for exclude in ['--exclude=config.php', '--exclude=config.example.php', '--exclude=privacy-policy.txt']:
            self.assertIn(exclude, syncs[0]['args'])
        for exclude in ['--exclude=setup.php', '--exclude=.user.ini']:
            self.assertIn(exclude, syncs[1]['args'])

    def test_ssh_checks_and_credential_cleanup_preserved(self):
        script = self.steps['Configure SSH']['run']
        for check in ['StrictHostKeyChecking yes', 'BatchMode yes', 'IdentitiesOnly yes',
                      'chmod 600', 'SSH_KNOWN_HOSTS', 'SSH_PRIVATE_KEY']:
            if check.startswith('SSH_'):
                self.assertIn(check, str(self.steps['Configure SSH']['env']))
            else: self.assertIn(check, script)
        self.assertEqual(self.steps['Remove temporary SSH credentials']['if'], 'always()')
        self.assertEqual(self.workflow['concurrency']['cancel-in-progress'], 'false')

if __name__ == '__main__': unittest.main()
