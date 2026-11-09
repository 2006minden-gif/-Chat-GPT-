"""Explicit 006 migration/recovery tests on random loopback MySQL only."""
import subprocess
import unittest
import test_prelaunch as fixture
class OperationsMigration(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php']:self.run_cli(runner,'up')
 def run_cli(self,runner,op,expected=0):
  r=subprocess.run([self.f.php,str(self.f.path/'scripts'/runner),op],capture_output=True,text=True);self.assertEqual(r.returncode,expected,r.stderr);return r
 def test_empty_roundtrip_keeps_original_data_and_checksums(self):
  self.f.sql("INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES ('Legacy','a@example.invalid','ИИ-агент','Existing','',1)")
  before={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_sessions']}
  self.f.sql("INSERT INTO nd_customers(name) VALUES ('Stage 3 legacy')")
  self.run_cli('migrate-crm.php','up');self.run_cli('migrate-crm.php','up')
  self.assertEqual(self.f.sql('SELECT due_on FROM nd_deals LIMIT 1'),[])
  self.run_cli('migrate-crm.php','down')
  for t,rows in before.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
  self.assertEqual(self.f.sql('SELECT name FROM nd_customers')[0]['name'],'Stage 3 legacy')
  self.run_cli('migrate-crm.php','up')
 def test_partial_and_tampered_manifest_fail_closed(self):
  self.run_cli('migrate-crm.php','up')
  folder=self.f.path/'database/migrations/006_crm_operations';p=folder/'up.sql';original=p.read_text();p.write_text(original+'\n-- changed')
  self.run_cli('migrate-crm.php','down',1);p.write_text(original)
  self.f.sql("UPDATE nd_schema_migrations SET state='applying' WHERE version='006_crm_operations'")
  self.run_cli('migrate-crm.php','up',1);self.run_cli('migrate-crm.php','down',1)
 def test_unmanaged_collision_is_not_adopted(self):
  self.f.sql('CREATE TABLE nd_crm_requests(request_key INT) ENGINE=InnoDB')
  self.run_cli('migrate-crm.php','up',1)
  self.assertEqual(self.f.sql("SELECT * FROM nd_schema_migrations WHERE version='006_crm_operations'"),[])
