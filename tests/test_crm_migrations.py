"""Migration tests: isolated random DB only; same loopback safeguards as prelaunch suite."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import unittest
import test_prelaunch as fixture

class CRMFoundation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.f=fixture.Prelaunch
  cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
  cls.directory=cls.f.path/'database/migrations/004_crm_foundation'
  cls.tables=re.findall(r'CREATE TABLE (nd_[a-z_]+)\s*\(', (cls.directory/'up.sql').read_text())
  cls.f.sql("INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES ('История','history@example.invalid','ИИ-агент','Сохранить','Original notes',1)")
  cls.legacy_admin=cls.f.sql('SELECT * FROM nd_admin');cls.legacy_leads=cls.f.sql('SELECT * FROM nd_leads')
 def run_migration(self,operation,expected=0):
  r=subprocess.run([self.f.php,str(self.f.path/'scripts/migrate.php'),operation],capture_output=True,text=True)
  self.assertEqual(r.returncode,expected,r.stdout+r.stderr);return r
 def tearDown(self):
  # Only synthetic tables in the suite's random loopback database.
  for table in reversed(self.tables):self.f.sql('DROP TABLE IF EXISTS '+table)
  self.f.sql('DROP TABLE IF EXISTS nd_schema_migrations')
  self.assertEqual(self.f.sql('SELECT * FROM nd_admin'),self.legacy_admin)
  self.assertEqual(self.f.sql('SELECT * FROM nd_leads WHERE id=1'),self.legacy_leads)
 def error_number(self,sql):
  values=dict(self.f.dbargs);values['dsn']+=';dbname='+self.f.dbname;values['sql']=sql
  return int(self.f.php_eval('try{$p=new PDO($v["dsn"],$v["user"],$v["password"],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);$p->exec($v["sql"]);echo 0;}catch(PDOException $e){echo $e->errorInfo[1];}',values))
 def test_01_up_preserves_legacy_and_existing_api(self):
  self.assertEqual(json.loads(self.run_migration('status').stdout)['state'],'not_applied')
  self.assertEqual(self.f.sql("SELECT COUNT(*) AS n FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name='nd_schema_migrations'")[0]['n'],0)
  self.run_migration('up');self.run_migration('up')
  self.assertEqual(json.loads(self.run_migration('status').stdout)['state'],'applied')
  for table in self.tables:self.assertEqual(self.f.sql('SELECT COUNT(*) AS n FROM '+table)[0]['n'],0)
  self.assertEqual(self.f.sql('SELECT * FROM nd_leads'),self.legacy_leads)
  client=self.f('test_01_confirmed_persistence');owner,headers=client.owner()
  self.assertEqual(owner.get(client.api('session')).status_code,200)
  self.assertEqual(owner.get(client.api('leads')).json()[0]['notes'],'Original notes')
  self.assertEqual(owner.post(client.api('logout'),headers=headers).status_code,200)
 def test_02_constraints_and_valid_graph(self):
  self.run_migration('up')
  for name in ['A','B']:self.f.sql("INSERT INTO nd_customers(name) VALUES (?)",params=[name])
  self.f.sql("INSERT INTO nd_employees(name,email) VALUES ('Test','staff@example.invalid')")
  self.f.sql("INSERT INTO nd_customer_accounts(customer_id,email) VALUES (1,'portal@example.invalid')")
  self.f.sql('INSERT INTO nd_lead_customers(lead_id,customer_id) VALUES (1,1)')
  self.f.sql("INSERT INTO nd_deals(customer_id,lead_id,title,owner_employee_id) VALUES (1,1,'Deal',1)")
  self.f.sql("INSERT INTO nd_orders(customer_id,deal_id,number,title,total_amount) VALUES (1,1,'TEST-001','Order',100.25)")
  self.f.sql("INSERT INTO nd_projects(customer_id,order_id,title,manager_employee_id) VALUES (1,1,'Project',1)")
  self.f.sql("INSERT INTO nd_projects(customer_id,title) VALUES (2,'Other project')")
  self.f.sql("INSERT INTO nd_project_stages(project_id,position,title) VALUES (1,1,'Stage')")
  self.f.sql('INSERT INTO nd_project_members(project_id,employee_id) VALUES (1,1)')
  self.f.sql("INSERT INTO nd_tasks(title,assignee_employee_id) VALUES ('Task',1)")
  self.f.sql('INSERT INTO nd_task_projects(task_id,project_id,stage_id) VALUES (1,1,1)')
  self.f.sql("INSERT INTO nd_activity_history(actor_admin_id,customer_id,lead_id,deal_id,order_id,project_id,stage_id,task_id,action,summary) VALUES (1,1,1,1,1,1,1,1,'test','Synthetic event')")
  for sql in ["INSERT INTO nd_deals(customer_id,lead_id,title) VALUES (2,1,'Wrong customer')", "INSERT INTO nd_orders(customer_id,deal_id,number,title,total_amount) VALUES (2,1,'WRONG','Mismatch',10)", "INSERT INTO nd_projects(customer_id,order_id,title) VALUES (2,1,'Mismatch')", 'UPDATE nd_task_projects SET project_id=2 WHERE task_id=1', 'INSERT INTO nd_project_members(project_id,employee_id) VALUES (1,999)', 'UPDATE nd_customer_accounts SET customer_id=999 WHERE id=1']:
   with self.subTest(sql=sql):self.assertEqual(self.error_number(sql),1452)
  for sql in ["INSERT INTO nd_customer_accounts(customer_id,email) VALUES (2,'portal@example.invalid')", "INSERT INTO nd_project_stages(project_id,position,title) VALUES (1,1,'Duplicate')",'INSERT INTO nd_lead_customers VALUES (1,2,NOW())']:
   self.assertEqual(self.error_number(sql),1062)
  for sql in ['DELETE FROM nd_admin WHERE id=1','DELETE FROM nd_leads WHERE id=1','DELETE FROM nd_customers WHERE id=1','DELETE FROM nd_employees WHERE id=1']:
   self.assertEqual(self.error_number(sql),1451)
  self.assertNotEqual(self.error_number("UPDATE nd_tasks SET status='invented' WHERE id=1"),0)
  self.assertNotEqual(self.error_number('UPDATE nd_orders SET total_amount=-1 WHERE id=1'),0)
  refused=self.run_migration('down',1);self.assertIn('rollback_refused_nonempty_crm',refused.stderr)
  self.assertEqual(self.f.sql('SELECT summary FROM nd_activity_history')[0]['summary'],'Synthetic event')
 def test_03_empty_down_and_reapply_preserve_legacy(self):
  self.run_migration('up');self.run_migration('down');self.run_migration('down')
  self.assertEqual(json.loads(self.run_migration('status').stdout)['state'],'not_applied')
  self.run_migration('up');self.run_migration('down')
 def test_04_unmanaged_table_is_never_adopted(self):
  self.f.sql('CREATE TABLE nd_customers(id INT PRIMARY KEY) ENGINE=InnoDB')
  r=self.run_migration('up',1);self.assertIn('unmanaged_table_collision',r.stderr)
  self.assertEqual(len(self.f.sql('SHOW COLUMNS FROM nd_customers')),1)
 def test_05_checksum_protects_rollback(self):
  self.run_migration('up');path=self.directory/'down.sql';original=path.read_bytes()
  try:
   path.write_bytes(original+b'\n-- changed\n');r=self.run_migration('down',1)
   self.assertIn('migration_checksum_mismatch',r.stderr)
  finally:path.write_bytes(original)
  self.run_migration('down')
 def test_06_partial_ddl_is_visible_and_empty_recovery_is_safe(self):
  path=self.directory/'up.sql';original=path.read_bytes()
  try:
   # Valid SQL but invalid FK: simulates a later DDL failure, not a transaction rollback.
   path.write_text(original.decode().replace('REFERENCES nd_employees(id)','REFERENCES nd_missing_employees(id)',1))
   self.run_migration('up',1)
   state=json.loads(self.run_migration('status').stdout);self.assertEqual(state['state'],'applying');self.assertGreater(state['completed_steps'],0)
   self.assertIn('partial_migration',self.run_migration('up',1).stderr)
   self.run_migration('down')
  finally:path.write_bytes(original)
  self.run_migration('up');self.run_migration('down')
 def test_07_advisory_lock_blocks_second_runner(self):
  code='$p=new PDO($v["dsn"],$v["user"],$v["password"]);$q=$p->prepare("SELECT GET_LOCK(?,0)");$q->execute([$v["lock"]]);echo "locked\\n";flush();fgets(STDIN);'
  config=dict(self.f.dbargs);config['dsn']+=';dbname='+self.f.dbname;config['lock']='nd_migrate_'+hashlib.sha256(self.f.dbname.encode()).hexdigest()[:40]
  # PHP receives config as an argument JSON, containing only this isolated fixture's credentials.
  proc=subprocess.Popen([self.f.php,'-r','$v=json_decode($argv[1],true);'+code,json.dumps(config)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
  try:
   self.assertEqual(proc.stdout.readline().strip(),'locked')
   self.assertIn('migration_busy',self.run_migration('up',1).stderr)
  finally:proc.communicate('\n',timeout=5)
  self.run_migration('up');self.run_migration('down')

 def test_08_history_only_still_blocks_rollback(self):
  self.run_migration('up')
  self.f.sql("INSERT INTO nd_activity_history(action,summary) VALUES ('system_test','Synthetic system event')")
  self.assertIn('rollback_refused_nonempty_crm',self.run_migration('down',1).stderr)
  self.assertEqual(self.f.sql('SELECT COUNT(*) AS n FROM nd_activity_history')[0]['n'],1)
 def test_09_interrupted_empty_down_can_resume(self):
  self.run_migration('up')
  self.f.sql("UPDATE nd_schema_migrations SET state='rolling_back'")
  self.f.sql('DROP TABLE nd_activity_history')
  self.run_migration('down')
  self.assertEqual(json.loads(self.run_migration('status').stdout)['state'],'not_applied')
  self.run_migration('up');self.run_migration('down')

 def test_10_newer_version_blocks_old_runner(self):
  self.run_migration('up')
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state) VALUES ('005_future',REPEAT('0',64),REPEAT('0',64),'applied')")
  self.assertIn('newer_migration_applied',self.run_migration('down',1).stderr)
  self.assertIn('newer_migration_applied',self.run_migration('up',1).stderr)
  self.assertEqual(json.loads(self.run_migration('status').stdout)['state'],'applied')

if __name__=='__main__':unittest.main()
