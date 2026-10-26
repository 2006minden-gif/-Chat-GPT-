"""Release closure and nested-file protection; isolated fixtures only."""
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest.mock import patch
import test_release_pipeline as pipeline
release=pipeline.release
health=pipeline.health
client=pipeline.client
ROOT=pipeline.ROOT

class PackageCompleteness(unittest.TestCase):
 def test_php_and_builder_share_exact_explicit_allowlist(self):
  policy=release.policy_check()
  source=(ROOT/'scripts/deploy/remote.php').read_text()
  literal=re.search(r'function paths\(\):array \{\s*return (\[[^;]+\]);',source).group(1)
  expected=['public_html/'+p for p in policy['public_files']]+['private/'+p for p in policy['private_files']]
  self.assertEqual(ast.literal_eval(literal),expected)
 def test_all_application_modules_and_operators_are_delivered(self):
  with tempfile.TemporaryDirectory() as tmp:
   b=Path(tmp)/'bundle';m=release.build(b,'a'*40);client.validate_bundle(b,'a'*40)
   for p in ['public_html/services.php','public_html/services/guide.js','public_html/services/guide.css','private/services/catalog.php']:
    self.assertIn(p,m['files']);self.assertEqual(release.digest(b/p),release.digest(ROOT/('public/'+p[12:] if p.startswith('public_html/') else p)))
   policy=release.policy_check()
   for entry in policy['migrations']:self.assertIn(entry['operator'],m['tools'])
   self.assertTrue(all(not x['automatic'] and x['required'] for x in m['migrations']))
 def test_missing_unlisted_new_source_blocks_build(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)/'root';shutil.copytree(ROOT/'scripts/deploy',root/'scripts/deploy');shutil.copytree(ROOT/'database',root/'database');shutil.copytree(ROOT/'scripts',root/'scripts',dirs_exist_ok=True);shutil.copytree(ROOT/'tests',root/'tests');shutil.copytree(ROOT/'public',root/'public');shutil.copytree(ROOT/'private',root/'private')
   (root/'private/services/unlisted.php').write_text('<?php // new module')
   with self.assertRaisesRegex(ValueError,'closure'):release.policy_check(root)
 def test_dangerous_paths_are_not_application_files(self):
  for p in ['../app.php','crm/../../config.php','/app.php','crm/config.php','crm/secret.key','crm/a.php~','crm/.hidden.php','crm//core.php','crm/./core.php','setup.php']:
   with self.subTest(p=p):self.assertFalse(release.safe_application_path(p))
  self.assertTrue(release.safe_application_path('crm/routes.php'))
 def test_source_directory_symlink_is_rejected(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'real').mkdir();(root/'real/a.php').write_text('<?php')
   (root/'link').symlink_to(root/'real',target_is_directory=True)
   with self.assertRaisesRegex(ValueError,'non_regular'):release.check_source_path(root/'link/a.php',root)
 def test_migration_chain_covers_every_version_in_order(self):
  entries=release.policy_check()['migrations'];folders=sorted(p.parent.name for p in (ROOT/'database/migrations').glob('*/up.sql'))
  self.assertEqual([e['version'] for e in entries],folders)
  for i,e in enumerate(entries):self.assertEqual(e['depends_on'],entries[i-1]['version'] if i else None)
 def test_new_assets_checked_without_polluting_baseline(self):
  opener=pipeline.HealthTests().opener()
  def added(request,timeout):
   if '/ai.css?' in request.full_url:
    replacement=__import__('urllib.request',fromlist=['Request']).Request(request.full_url.replace('/ai.css?','/styles.css?'))
    r=opener(replacement,timeout);r.url=request.full_url;return r
   return opener(request,timeout)
  baseline=health.snapshot(opener=added)
  after=health.snapshot(opener=added,extra_assets=['/ai.css'])
  self.assertNotIn('/ai.css',baseline['checks']);self.assertTrue(after['checks']['/ai.css']['ok'])
  self.assertTrue(health.require_asset_revision(after,{'/ai.css':hashlib.sha256(b'synthetic asset').hexdigest()})['ok'])
 def test_health_asset_paths_cannot_escape_origin(self):
  for path in ['//evil.invalid/a.js','/../secret.js','/api.php?r=bad.js']:
   with self.assertRaises(ValueError):health.snapshot(extra_assets=[path])

class NestedFilesystem(pipeline.RemoteFilesystemTests):
 def test_new_nested_directories_created_and_rollback_keeps_upload(self):
  shutil.rmtree(self.root/'private/services')
  upload=self.root/'private/customer-files';upload.mkdir();(upload/'keep.bin').write_bytes(b'customer data')
  self.agent('apply');self.assertTrue((self.root/'private/services/catalog.php').is_file())
  self.agent('rollback');self.assertFalse((self.root/'private/services/catalog.php').exists());self.assertEqual((upload/'keep.bin').read_bytes(),b'customer data')
 def test_nested_destination_symlink_blocks_all_writes(self):
  shutil.rmtree(self.root/'private/services');target=self.root/'outside';target.mkdir();(target/'catalog.php').write_text('KEEP')
  (self.root/'private/services').symlink_to(target,target_is_directory=True)
  self.assertEqual(self.agent('apply',1)['error'],'symlink_refused');self.assertEqual((target/'catalog.php').read_text(),'KEEP');self.assert_protected()

# Reuse filesystem fixtures, not inherited duplicate test execution.
for name in list(vars(pipeline.RemoteFilesystemTests)):
 if name.startswith('test_'):setattr(NestedFilesystem,name,None)
