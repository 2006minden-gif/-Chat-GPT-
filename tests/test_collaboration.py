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
 def pdf(self):return b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'
 def upload(self,s,name='test.pdf',body=None,**data):
  fields={'project_id':str(self.project_id),'request_key':secrets.token_hex(32),'visibility':'internal'};fields.update(data)
  return s.post(self.url(s,'upload'),data=fields,files={'file':(name,self.pdf() if body is None else body,'application/octet-stream')})
 def test_02_private_files_visibility_download_and_missing_bytes(self):
  key=secrets.token_hex(32);r=self.upload(self.owner,request_key=key);self.assertEqual(r.status_code,200,r.text);fid=r.json()['id'];self.assertNotIn('storage_key',r.text)
  self.assertEqual(self.upload(self.owner,request_key=key).json()['id'],fid)
  url=self.base+'/collab-download.php?mode=customer&id='+str(fid)
  self.assertEqual(self.customer.get(url).status_code,404);self.assertEqual(self.stranger.get(url).status_code,404);self.assertEqual(requests.get(url).status_code,401)
  r=self.post(self.owner,'files/'+str(fid),version=1,visibility='customer',archived=False);self.assertEqual(r.status_code,200,r.text)
  r=self.customer.get(url);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.content,self.pdf());self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff');self.assertIn('attachment',r.headers['Content-Disposition'])
  self.assertEqual(self.stranger.get(url).status_code,404)
  self.assertEqual(self.post(self.customer,f'projects/{self.project_id}/messages',body='Прикреплён файл',file_ids=[fid]).status_code,200)
  row=self.f.sql('SELECT storage_key FROM nd_cc_files WHERE id=?',params=[fid])[0];path=self.f.path/'private/collaboration-files'/row['storage_key'];self.assertEqual(path.stat().st_mode&0o777,0o600);path.unlink()
  r=self.customer.get(url);self.assertEqual(r.status_code,503);self.assertNotIn(str(self.f.path),r.text)
  self.assertEqual(self.customer.get(self.base+'/private/collaboration-files/'+row['storage_key']).status_code,404)
 def test_03_invalid_uploads_quotas_and_clean_failures(self):
  for name,body in [('run.php',b'<?php echo 1;'),('fake.pdf',b'<?php echo 1;'),('active.pdf',b'%PDF-1.4\n/JavaScript x\n%%EOF'),('../evil.pdf',self.pdf()),('fake.png',self.pdf()),('empty.pdf',b''),('page.html',b'<html>x</html>')]:
   r=self.upload(self.owner,name,body);self.assertEqual(r.status_code,422,(name,r.text))
  before=self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'];config=dict(self.f.config)
  try:
   self.f.config['collaboration_file_max_bytes']=1;self.f.write_config();self.assertEqual(self.upload(self.owner).status_code,422)
   self.f.config['collaboration_file_max_bytes']=5242880;self.f.config['collaboration_total_max_bytes']=1;self.f.write_config();self.assertEqual(self.upload(self.owner).status_code,507)
  finally:self.f.config=config;self.f.write_config()
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'],before)
  r=self.owner.post(self.url(self.owner,'upload'),data={'project_id':self.project_id,'request_key':secrets.token_hex(32)});self.assertEqual(r.status_code,422)
  self.assertEqual(self.upload(self.stranger).status_code,404)
 def test_04_office_archive_validation(self):
  import io,zipfile
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:
   z.writestr('[Content_Types].xml','<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');z.writestr('_rels/.rels','<Relationships/>');z.writestr('word/document.xml','<document/>')
  zip_enabled=self.f.php_eval('echo class_exists("ZipArchive")?"yes":"no";',{})=='yes'
  r=self.upload(self.owner,'spec.docx',buf.getvalue());self.assertEqual(r.status_code,200 if zip_enabled else 503,r.text)
  with zipfile.ZipFile(buf,'a') as z:z.writestr('word/vbaProject.bin',b'evil')
  r=self.upload(self.owner,'macro.docx',buf.getvalue());self.assertEqual(r.status_code,422 if zip_enabled else 503,r.text)
