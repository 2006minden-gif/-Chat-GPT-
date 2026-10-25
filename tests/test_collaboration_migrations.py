"""007 migration safety: random local databases, never production."""
import subprocess
import unittest
import test_prelaunch as fixture
class CollaborationMigration(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for r in ['migrate.php','migrate-customer.php','migrate-crm.php']:self.run_cli(r,'up')
 def run_cli(self,r,op,expected=0):
  x=subprocess.run([self.f.php,str(self.f.path/'scripts'/r),op],text=True,capture_output=True);self.assertEqual(x.returncode,expected,x.stderr);return x
 def test_roundtrip_preserves_leads_admin_and_prior_customer(self):
  self.f.sql("INSERT INTO nd_customers(name) VALUES ('Existing customer')");self.f.sql("INSERT INTO nd_projects(customer_id,title) VALUES (1,'Existing project')")
  old={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_customers','nd_projects']}
  self.run_cli('migrate-collab.php','up');self.run_cli('migrate-collab.php','up');self.run_cli('migrate-collab.php','down')
  for t,rows in old.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
  self.run_cli('migrate-collab.php','up')
 def test_nonempty_refused_checksum_and_dependency_guards(self):
  self.run_cli('migrate-collab.php','up');self.f.sql("INSERT INTO nd_customers(name) VALUES ('Existing')");self.f.sql("INSERT INTO nd_projects(customer_id,title) VALUES (1,'Existing')");self.f.sql("INSERT INTO nd_cc_messages(project_id,actor_type,actor_id,body) VALUES (1,'owner',1,'Keep history')")
  self.assertIn('rollback_refused_nonempty_auth',self.run_cli('migrate-collab.php','down',1).stderr)
  self.assertEqual(self.f.sql('SELECT body FROM nd_cc_messages')[0]['body'],'Keep history')
  p=self.f.path/'database/migrations/007_client_collaboration/up.sql';p.write_text(p.read_text()+'\n-- tampered')
  self.assertIn('migration_checksum_mismatch',self.run_cli('migrate-collab.php','up',1).stderr)
  self.run_cli('migrate-crm.php','down',1);self.assertEqual(self.f.sql("SELECT state FROM nd_schema_migrations WHERE version='006_crm_operations'")[0]['state'],'applied');self.assertEqual(self.f.sql('SELECT body FROM nd_cc_messages')[0]['body'],'Keep history')
 def test_partial_requires_manual_recovery_without_data_adoption(self):
  self.f.sql('CREATE TABLE nd_cc_reads(id INT) ENGINE=InnoDB');self.assertIn('unmanaged_table_collision',self.run_cli('migrate-collab.php','up',1).stderr)
  self.assertFalse(self.f.sql("SELECT * FROM nd_schema_migrations WHERE version='007_client_collaboration'"))
 def test_partial_journal_can_only_roll_back_empty_created_tables(self):
  import hashlib
  folder=self.f.path/'database/migrations/007_client_collaboration';up=(folder/'up.sql').read_text();down=(folder/'down.sql').read_text();self.f.sql(up.split(';')[0])
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state,completed_steps) VALUES ('007_client_collaboration',?,?,'applying',1)",params=[hashlib.sha256(up.encode()).hexdigest(),hashlib.sha256(down.encode()).hexdigest()])
  self.assertIn('partial_migration_requires_empty_rollback',self.run_cli('migrate-collab.php','up',1).stderr);self.run_cli('migrate-collab.php','down');self.assertFalse(self.f.sql("SELECT * FROM nd_schema_migrations WHERE version='007_client_collaboration'"));self.run_cli('migrate-collab.php','up')
