"""Real reviewed migration batch and recovery on a disposable MySQL 5.7 database."""
import json,shutil
from pathlib import Path
import test_release_pipeline as pipeline

class LifecycleRelease(pipeline.unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=pipeline.fixture.Prelaunch;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
 setUp=pipeline.RemoteFilesystemTests.setUp
 agent=pipeline.RemoteFilesystemTests.agent
 finish=pipeline.RemoteFilesystemTests.finish
 assert_protected=pipeline.RemoteFilesystemTests.assert_protected
 def test_exact_batch_preserves_accounts_is_retry_safe_and_recoverable(self):
  before=self.f.sql('SELECT * FROM nd_admin');global_mode=self.f.sql('SELECT @@GLOBAL.sql_mode AS value')[0]['value'];self.agent('apply');self.finish()
  self.id='lifecycle';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id
  m=pipeline.release.build(self.candidate,'b'*40);(self.candidate/'baseline.json').write_text(json.dumps(pipeline.good()))
  # Previously successful database recovery is mandatory, even with green CI.
  proof=self.root/'.neurodelo-deploy/backups/release0/database-recovery/verified.json';original=proof.read_text();proof.write_text('{}')
  self.assertEqual(self.agent('apply',1)['error'],'database_recovery_not_verified')
  self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='nd_schema_migrations'")[0]['n'],0)
  self.agent('rollback');proof.write_text(original)
  old=self.candidate;self.id='lifecycle-retry';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id;shutil.copytree(old,self.candidate)
  result=self.agent('apply');self.assertEqual(result['migrations'],[x['version'] for x in m['migrations']]);self.finish();self.assert_protected()
  self.assertEqual(self.f.sql('SELECT * FROM nd_admin'),before)
  rows=self.f.sql('SELECT version,state,up_checksum,down_checksum FROM nd_schema_migrations ORDER BY version')
  self.assertEqual(len(rows),len(m['migrations']));self.assertTrue(all(x['state']=='applied' for x in rows))
  # Second legitimate delivery skips every applied migration and rehearses the expanded schema.
  self.id='lifecycle-followup';self.candidate=self.root/'.neurodelo-deploy/incoming'/self.id;pipeline.release.build(self.candidate,'c'*40);(self.candidate/'baseline.json').write_text(json.dumps(pipeline.good()))
  backup=self.root/'.neurodelo-deploy/backups/lifecycle-retry';self.assertEqual(json.loads((backup/'database.json').read_text())['format'],'verified-private-jsonl-schema-v1');self.assertFalse((backup/'database.sql').exists());self.assertEqual(self.f.sql('SELECT @@GLOBAL.sql_mode AS value')[0]['value'],global_mode)
  follow=self.agent('apply');self.assertEqual(follow['migrations'],[]);self.assertTrue(follow['database_recovery']['verified']);self.assertTrue(follow['database_recovery']['shadow_tables_removed']);self.assertGreater(follow['database_recovery']['foreign_keys_verified'],20);self.finish()
  self.assertEqual(self.f.sql('SELECT version,state,up_checksum,down_checksum FROM nd_schema_migrations ORDER BY version'),rows);self.assertEqual(self.f.sql('SELECT * FROM nd_admin'),before)
