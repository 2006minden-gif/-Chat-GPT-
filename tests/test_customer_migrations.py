"""005 migration safety against actual isolated MySQL, preserving Stage 3 and owner data."""
import hashlib
import json
import re
import subprocess
import unittest
import test_prelaunch as fixture

class CustomerMigrations(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=fixture.Prelaunch;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
  cls.folder=cls.f.path/'database/migrations/005_customer_auth';cls.tables=re.findall(r'CREATE TABLE (nd_[a-z_]+)\s*\(',(cls.folder/'up.sql').read_text())
  r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  cls.f.sql("INSERT INTO nd_customers(name) VALUES ('Stage3 preserved')");cls.f.sql("INSERT INTO nd_customer_accounts(customer_id,email) VALUES (1,'legacy@example.invalid')")
  cls.before={t:cls.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_customers','nd_customer_accounts']}
 def run_cli(self,op,expected=0,runner='migrate-customer.php'):
  r=subprocess.run([self.f.php,str(self.f.path/'scripts'/runner),op],capture_output=True,text=True);self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
 def tearDown(self):
  for t in reversed(self.tables):self.f.sql('DROP TABLE IF EXISTS '+t)
  self.f.sql("DELETE FROM nd_schema_migrations WHERE version='005_customer_auth'")
  for t,rows in self.before.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
 def test_up_idempotence_down_and_parent_guard(self):
  self.assertEqual(json.loads(self.run_cli('status').stdout)['state'],'not_applied');self.run_cli('up');self.run_cli('up')
  self.assertEqual(json.loads(self.run_cli('status').stdout)['state'],'applied');self.assertIn('newer_migration',self.run_cli('down',1,'migrate.php').stderr)
  self.run_cli('down');self.run_cli('down');self.run_cli('up');self.run_cli('down')
 def test_requires_applied_dependency_and_exact_hash(self):
  self.f.sql("UPDATE nd_schema_migrations SET state='applying' WHERE version='004_crm_foundation'")
  try:self.assertIn('migration_004_required',self.run_cli('up',1).stderr)
  finally:self.f.sql("UPDATE nd_schema_migrations SET state='applied' WHERE version='004_crm_foundation'")
  file=self.f.path/'database/migrations/004_crm_foundation/up.sql';original=file.read_bytes()
  try:file.write_bytes(original+b'\n-- altered\n');self.assertIn('migration_004_required',self.run_cli('up',1).stderr)
  finally:file.write_bytes(original)
 def test_partial_ddl_refuses_blind_retry_and_empty_down_recovers(self):
  path=self.folder/'up.sql';original=path.read_bytes()
  try:
   path.write_text(original.decode().replace('REFERENCES nd_admin(id)','REFERENCES nd_missing_admin(id)'))
   self.run_cli('up',1);state=json.loads(self.run_cli('status').stdout);self.assertEqual(state['state'],'applying');self.assertGreater(state['completed_steps'],0)
   self.assertIn('partial_migration',self.run_cli('up',1).stderr);self.run_cli('down')
  finally:path.write_bytes(original)
  self.run_cli('up');self.run_cli('down')
 def test_refuses_nonempty_even_security_events_only(self):
  self.run_cli('up');self.f.sql("INSERT INTO nd_customer_auth_events(event,created_at) VALUES ('test',1)")
  self.assertIn('rollback_refused_nonempty_auth',self.run_cli('down',1).stderr);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_auth_events')[0]['n'],1)
 def test_checksum_and_unmanaged_tables_are_protected(self):
  self.run_cli('up');path=self.folder/'down.sql';original=path.read_bytes()
  try:path.write_bytes(original+b'\n-- changed\n');self.assertIn('checksum',self.run_cli('down',1).stderr)
  finally:path.write_bytes(original)
  self.run_cli('down');self.f.sql('CREATE TABLE nd_customer_auth(account_id BIGINT PRIMARY KEY) ENGINE=InnoDB')
  self.assertIn('unmanaged_table_collision',self.run_cli('up',1).stderr)
 def test_advisory_lock_prevents_parallel_runner(self):
  v=dict(self.f.dbargs,lock='nd_migrate_'+hashlib.sha256(self.f.dbname.encode()).hexdigest()[:40]);v['dsn']+=';dbname='+self.f.dbname
  code='$v=json_decode($argv[1],true);$p=new PDO($v["dsn"],$v["user"],$v["password"]);$q=$p->prepare("SELECT GET_LOCK(?,0)");$q->execute([$v["lock"]]);echo "locked\\n";flush();fgets(STDIN);'
  proc=subprocess.Popen([self.f.php,'-r',code,json.dumps(v)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:self.assertEqual(proc.stdout.readline().strip(),'locked');self.assertIn('migration_busy',self.run_cli('up',1).stderr)
  finally:proc.communicate('\n',timeout=5)

if __name__=='__main__':unittest.main()
