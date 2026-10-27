"""011 migration guards on fresh isolated MySQL 5.7 databases."""
import hashlib
import subprocess
import unittest
import test_prelaunch as fixture
class ProductionMigrations(unittest.TestCase):
 def setUp(self):
  class F(fixture.Prelaunch):pass
  self.f=F;F.setUpClass();self.addCleanup(F.doClassCleanups)
  for r in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php','migrate-billing.php','migrate-ai.php','migrate-pricing.php']:self.cli(r,'up')
 def cli(self,r,op,expect=0):
  x=subprocess.run([self.f.php,str(self.f.path/'scripts'/r),op],capture_output=True,text=True);self.assertEqual(x.returncode,expect,x.stderr);return x
 def test_roundtrip_preserves_previous_records(self):
  old={t:self.f.sql('SELECT * FROM '+t) for t in ['nd_admin','nd_leads','nd_orders','nd_ai_tasks','nd_quotations']}
  for op in ['up','up','down','up']:self.cli('migrate-production.php',op)
  for t,rows in old.items():self.assertEqual(self.f.sql('SELECT * FROM '+t),rows)
  self.assertIn('newer_migration_applied',self.cli('migrate-pricing.php','down',1).stderr)
 def test_nonempty_and_checksum_refused(self):
  self.cli('migrate-production.php','up');self.f.sql("INSERT INTO nd_customers(name) VALUES ('Existing')");self.f.sql("INSERT INTO nd_projects(customer_id,title) VALUES (1,'Existing')");self.f.sql("INSERT INTO nd_prod_rate_scopes(rate_id,service_type,active,verified_at,source) SELECT id,'content',1,UTC_TIMESTAMP(),'fixture' FROM nd_cost_rates")
  # A standalone new report row requires its FK parents; use the independent immutable source scope fixture.
  self.f.sql("INSERT INTO nd_cost_registry_keys(category) VALUES ('labor_hour')");self.f.sql("INSERT INTO nd_cost_rates(category,revision_number,value_scaled,currency,source,source_date,valid_from,valid_until) VALUES ('labor_hour',1,0,'RUB','fixture','2026-01-01','2026-01-01','2099-12-31')");self.f.sql("INSERT INTO nd_prod_rate_scopes(rate_id,service_type,active,verified_at,source) VALUES (1,'content',1,UTC_TIMESTAMP(),'fixture')")
  self.assertIn('rollback_refused_nonempty_auth',self.cli('migrate-production.php','down',1).stderr)
  p=self.f.path/'database/migrations/011_ai_production/up.sql';p.write_text(p.read_text()+'\n-- altered');self.assertIn('migration_checksum_mismatch',self.cli('migrate-production.php','up',1).stderr)
 def test_partial_unmanaged_requires_empty_recovery(self):
  p=self.f.path/'database/migrations/011_ai_production';up=(p/'up.sql').read_text();down=(p/'down.sql').read_text();self.f.sql(up[up.index('CREATE TABLE'):].split(';')[0]);self.assertIn('unmanaged_table_collision',self.cli('migrate-production.php','up',1).stderr)
  self.f.sql("INSERT INTO nd_schema_migrations(version,up_checksum,down_checksum,state,completed_steps) VALUES ('011_ai_production',?,?,'applying',1)",params=[hashlib.sha256(up.encode()).hexdigest(),hashlib.sha256(down.encode()).hexdigest()]);self.assertIn('partial_migration_requires_empty_rollback',self.cli('migrate-production.php','up',1).stderr);self.cli('migrate-production.php','down');self.cli('migrate-production.php','up')
