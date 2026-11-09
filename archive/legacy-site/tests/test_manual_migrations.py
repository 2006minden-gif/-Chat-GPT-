"""012 migration guards on fresh isolated MySQL 5.7 databases."""
import hashlib
import subprocess
import unittest
import test_prelaunch as fixture
class ManualMigrations(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for r in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php','migrate-billing.php','migrate-ai.php','migrate-pricing.php','migrate-production.php']:self.cli(r,'up')
 def cli(self,r,op,expect=0):
  x=subprocess.run([self.f.php,str(self.f.path/'scripts'/r),op],capture_output=True,text=True);self.assertEqual(x.returncode,expect,x.stderr);return x
 def test_roundtrip_preserves_previous_records(self):
  old={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_orders','nd_ai_tasks','nd_quotations']}
  for op in ['up','up','down','up']:self.cli('migrate-manual.php',op)
  for t,rows in old.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
  self.assertIn('newer_migration_applied',self.cli('migrate-production.php','down',1).stderr)
 def test_checksum_refused(self):
  self.cli('migrate-manual.php','up');p=self.f.path/'database/migrations/012_manual_handoff/up.sql';p.write_text(p.read_text()+'\n-- altered');self.assertIn('migration_checksum_mismatch',self.cli('migrate-manual.php','up',1).stderr)
 def test_partial_unmanaged_requires_empty_recovery(self):
  p=self.f.path/'database/migrations/012_manual_handoff';up=(p/'up.sql').read_text();down=(p/'down.sql').read_text();self.f.sql(up[up.index('CREATE TABLE'):].split(';')[0]);self.assertIn('unmanaged_table_collision',self.cli('migrate-manual.php','up',1).stderr)
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state,completed_steps) VALUES ('012_manual_handoff',?,?,'applying',1)",params=[hashlib.sha256(up.encode()).hexdigest(),hashlib.sha256(down.encode()).hexdigest()]);self.assertIn('partial_migration_requires_empty_rollback',self.cli('migrate-manual.php','up',1).stderr);self.cli('migrate-manual.php','down');self.cli('migrate-manual.php','up')
