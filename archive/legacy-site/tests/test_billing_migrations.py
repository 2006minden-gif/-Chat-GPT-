"""008 migration recovery, exclusively random loopback databases."""
import hashlib
import subprocess
import unittest
import test_prelaunch as fixture
class BillingMigration(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php']:self.run_cli(runner,'up')
 def run_cli(self,runner,op,expected=0):
  r=subprocess.run([self.f.php,str(self.f.path/'scripts'/runner),op],capture_output=True,text=True);self.assertEqual(r.returncode,expected,r.stderr);return r
 def test_roundtrip_empty_preserves_prior_records(self):
  self.f.sql("INSERT INTO nd_customers(name) VALUES ('Existing')");self.f.sql("INSERT INTO nd_orders(customer_id,number,title,total_amount) VALUES (1,'OLD','Existing','10.00')")
  old={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_customers','nd_orders']}
  for op in ['up','up','down','up']:self.run_cli('migrate-billing.php',op)
  for t,rows in old.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
 def test_nonempty_checksum_and_previous_stage_rollback_refused(self):
  self.run_cli('migrate-billing.php','up');self.f.sql("INSERT INTO nd_customers(name) VALUES ('Existing')");self.f.sql("INSERT INTO nd_orders(customer_id,number,title,total_amount) VALUES (1,'OLD','Existing','10.00')");self.f.sql("INSERT INTO nd_invoices(customer_id,order_id,total_minor,due_on) VALUES (1,1,1000,'2026-10-25')")
  self.assertIn('rollback_refused_nonempty_auth',self.run_cli('migrate-billing.php','down',1).stderr);self.assertEqual(len(self.f.sql('SELECT * FROM nd_invoices')),1)
  self.assertIn('newer_migration_applied',self.run_cli('migrate-collab.php','down',1).stderr)
  path=self.f.path/'database/migrations/008_billing_notifications/up.sql';path.write_text(path.read_text()+'\n-- altered')
  self.assertIn('migration_checksum_mismatch',self.run_cli('migrate-billing.php','up',1).stderr)
 def test_partial_recovery_and_unmanaged_collision(self):
  p=self.f.path/'database/migrations/008_billing_notifications';up=(p/'up.sql').read_text();down=(p/'down.sql').read_text();self.f.sql(up.split(';')[1] if ';' in up.split('CREATE TABLE')[0] else up.split(';')[0])
  self.assertIn('unmanaged_table_collision',self.run_cli('migrate-billing.php','up',1).stderr)
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state,completed_steps) VALUES ('008_billing_notifications',?,?,'applying',1)",params=[hashlib.sha256(up.encode()).hexdigest(),hashlib.sha256(down.encode()).hexdigest()])
  self.assertIn('partial_migration_requires_empty_rollback',self.run_cli('migrate-billing.php','up',1).stderr);self.run_cli('migrate-billing.php','down');self.run_cli('migrate-billing.php','up')
