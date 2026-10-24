"""Stage 6 private collaboration HTTP tests on random loopback-only databases."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import unittest
import requests
import test_prelaunch as fixture

class Collaboration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class F(fixture.Prelaunch):
   @classmethod
   def write_config(c):
    blob=base64.b64encode(json.dumps(c.config).encode()).decode();(c.path/'private/config.php').write_text("<?php return json_decode(base64_decode('"+blob+"'),true);")
  cls.f=F;F.setUpClass();cls.addClassCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php']:
   r=subprocess.run([F.php,str(F.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if r.returncode:raise RuntimeError(r.stderr)
  F.config.update(crm_operations_enabled=True,client_collaboration_enabled=True,customer_auth_enabled=True,customer_auth_privacy_approved=True,customer_auth_test_mode=True);F.write_config();cls.base=F.base
 def setUp(self):
  self.f.sql('DELETE FROM nd_limits');self.owner=requests.Session();r=self.owner.post(self.base+'/api.php?r=login',json={'password':self.f.password});self.assertEqual(r.status_code,200,r.text);self.owner.headers['X-CSRF-Token']=r.json()['csrf']
  self.customer_id=self.insert("INSERT INTO nd_customers(name,email) VALUES ('Синтетический клиент','a@example.invalid')",'nd_customers')
  self.project_id=self.insert("INSERT INTO nd_projects(customer_id,title,status) VALUES (?,'Синтетический проект','active')",'nd_projects',[self.customer_id])
  self.customer=self.account(self.customer_id)
  other=self.insert("INSERT INTO nd_customers(name) VALUES ('Другой клиент')",'nd_customers');self.stranger=self.account(other)
 def insert(self,sql,table,params=None):
  self.f.sql(sql,params=params);return int(self.f.sql('SELECT MAX(id) AS n FROM '+table)[0]['n'])
 def account(self,cid):
  email=secrets.token_hex(8)+'@example.invalid';password=secrets.token_urlsafe(20);h=self.f.php_eval('echo password_hash($v["p"],PASSWORD_DEFAULT);',{'p':password})
  aid=self.insert("INSERT INTO nd_customer_accounts(customer_id,email,password_hash,status) VALUES (?,?,?,'active')",'nd_customer_accounts',[cid,email,h]);policy=hashlib.sha256((self.f.path/'private/privacy-policy.txt').read_bytes()).hexdigest()
  self.f.sql("INSERT INTO nd_customer_auth VALUES (?,'invitation',?,?,?,?)",params=[aid,int(time.time()),int(time.time()),'test-policy-v1',policy])
  s=requests.Session();r=s.get(self.base+'/customer-api.php?r=session');s.headers['X-CSRF-Token']=r.json()['csrf'];r=s.post(self.base+'/customer-api.php?r=login',json={'email':email,'password':password});self.assertEqual(r.status_code,200,r.text);s.headers['X-CSRF-Token']=r.json()['csrf'];return s
 def url(self,s,route):return self.base+('/api.php?r=crm/collab/' if s is self.owner else '/customer-api.php?r=collab/')+route
 def get(self,s,route,**params):return s.get(self.url(s,route),params=params)
 def post(self,s,route,**d):
  d.setdefault('request_key',secrets.token_hex(32));return s.post(self.url(s,route),json=d)
 def test_01_messages_auth_unread_idempotency_and_archive(self):
  route=f'projects/{self.project_id}/messages';payload={'body':'Здравствуйте <script>alert(1)</script>','request_key':secrets.token_hex(32)}
  a=self.post(self.owner,route,**payload);self.assertEqual(a.status_code,200,a.text);self.assertEqual(self.post(self.owner,route,**payload).json()['id'],a.json()['id'])
  self.assertEqual(self.get(self.stranger,route).status_code,404);self.assertEqual(self.post(self.stranger,route,body='Попытка').status_code,404)
  self.assertEqual(self.get(self.customer,'threads').json()['items'][0]['unread'],1)
  self.assertEqual(self.post(self.customer,f'projects/{self.project_id}/read',last_message_id=a.json()['id']).status_code,200);self.assertEqual(self.get(self.customer,'threads').json()['items'][0]['unread'],0)
  b=self.post(self.customer,route,body='Ответ клиента');self.assertEqual(b.status_code,200,b.text);self.assertEqual(len(self.get(self.owner,route).json()['items']),2)
  self.assertEqual(self.post(self.customer,route,body=' ').status_code,422);self.assertEqual(self.post(self.customer,route,body='x'*5001).status_code,422)
  no=requests.Session();no.cookies.update(self.customer.cookies);self.assertEqual(no.post(self.url(self.customer,route),json=payload).status_code,403)
  self.f.sql('UPDATE nd_projects SET archived_at=UTC_TIMESTAMP() WHERE id=?',params=[self.project_id]);self.assertEqual(self.get(self.customer,route).status_code,200);self.assertEqual(self.post(self.customer,route,body='Закрытый').status_code,409)
