"""Stage 5: isolated MySQL 5.7 / PHP HTTP tests; never production writes."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import unittest
import requests
import test_prelaunch as fixture

class CrmOperations(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class F(fixture.Prelaunch):pass
  cls.f=F;F.setUpClass();cls.addClassCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php','migrate-crm.php']:
   p=subprocess.run([F.php,str(F.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if p.returncode:raise RuntimeError(p.stderr)
  F.config['crm_operations_enabled']=True;F.write_config();cls.base=F.base
 def setUp(self):
  self.f.sql('DELETE FROM nd_limits');self.s=requests.Session()
  r=self.s.post(self.base+'/api.php?r=login',json={'password':self.f.password});self.assertEqual(r.status_code,200,r.text);self.s.headers['X-CSRF-Token']=r.json()['csrf']
 def url(self,r):return self.base+'/api.php?r=crm/'+r
 def get(self,r,**params):return self.s.get(self.url(r),params=params)
 def post(self,r,**d):return self.s.post(self.url(r),json=d)
 def patch(self,r,**d):return self.s.patch(self.url(r),json=d)
 def create(self,kind,**d):
  d.setdefault('request_key',secrets.token_hex(32));r=self.s.post(self.url(kind),json=d);self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def test_01_dashboard_auth_gate_and_real_counts(self):
  self.assertEqual(requests.get(self.url('dashboard')).status_code,401)
  self.f.config['crm_operations_enabled']=False;self.f.write_config()
  try:self.assertEqual(self.get('dashboard').status_code,503)
  finally:self.f.config['crm_operations_enabled']=True;self.f.write_config()
  r=self.get('dashboard');self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['kpi']['projects'],int(self.f.sql("SELECT COUNT(*) n FROM nd_projects WHERE archived_at IS NULL AND status NOT IN ('completed','cancelled')")[0]['n']))
  self.assertEqual(self.post('notifications/sync').status_code,200)
  self.assertEqual(self.get('notifications').status_code,200)
  no_csrf=requests.Session();no_csrf.cookies.update(self.s.cookies)
  self.assertEqual(no_csrf.post(self.url('notifications/sync'),json={}).status_code,403)
