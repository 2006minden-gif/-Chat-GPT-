"""009/010 migration recovery without production access."""
import hashlib
import subprocess
import unittest
import test_prelaunch as fixture
class AiMigrations(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for r in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php','migrate-billing.php']:self.run_cli(r,'up')
 def run_cli(self,r,op,expected=0):
  x=subprocess.run([self.f.php,str(self.f.path/'scripts'/r),op],capture_output=True,text=True);self.assertEqual(x.returncode,expected,x.stderr);return x
 def test_ai_roundtrip_preserves_old_data_and_newer_guard(self):
  old={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_customers','nd_orders','nd_invoices']}
  for op in ['up','up','down','up']:self.run_cli('migrate-ai.php',op)
  self.run_cli('migrate-pricing.php','up');self.assertIn('newer_migration_applied',self.run_cli('migrate-ai.php','down',1).stderr)
  for op in ['up','down','up']:self.run_cli('migrate-pricing.php',op)
  for t,records in old.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),records)
 def test_nonempty_refused_for_ai_and_cost_tables(self):
  self.run_cli('migrate-ai.php','up');self.f.sql("INSERT INTO nd_ai_agents(agent_id) VALUES ('consultant')");self.assertIn('rollback_refused_nonempty_auth',self.run_cli('migrate-ai.php','down',1).stderr)
  self.run_cli('migrate-pricing.php','up');self.f.sql("INSERT INTO nd_cost_registry_keys(category) VALUES ('labor_hour')");self.assertIn('rollback_refused_nonempty_auth',self.run_cli('migrate-pricing.php','down',1).stderr);self.assertEqual(len(self.f.sql('SELECT * FROM nd_ai_agents')),1)
 def test_partial_checksum_and_collision_guards(self):
  folder=self.f.path/'database/migrations/009_ai_automation';up=(folder/'up.sql').read_text();down=(folder/'down.sql').read_text();self.f.sql(up.split(';')[0]);self.assertIn('unmanaged_table_collision',self.run_cli('migrate-ai.php','up',1).stderr)
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state,completed_steps) VALUES ('009_ai_automation',?,?,'applying',1)",params=[hashlib.sha256(up.encode()).hexdigest(),hashlib.sha256(down.encode()).hexdigest()]);self.assertIn('partial_migration_requires_empty_rollback',self.run_cli('migrate-ai.php','up',1).stderr);self.run_cli('migrate-ai.php','down');self.run_cli('migrate-ai.php','up')
  path=self.f.path/'database/migrations/009_ai_automation/up.sql';path.write_text(path.read_text()+'\n-- altered');self.assertIn('migration_checksum_mismatch',self.run_cli('migrate-ai.php','up',1).stderr)
