"""Isolated integration suite. Creates/drops only a random neuro_test_* database.
Requires NEURO_TEST_DSN=mysql:host=127.0.0.1;port=... and optional test DB
admin credentials NEURO_TEST_USER/PASSWORD; PHP_BIN selects an executable.
Copies the application into a temporary directory; never writes live config.php.
"""
import hashlib, json, os, secrets, shutil, socket, subprocess, tempfile, time, unittest
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
class Prelaunch(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.stage=int(os.environ.get('FIX_STAGE','5'))
  cls.php=os.environ.get('PHP_BIN','php')
  dsn=os.environ.get('NEURO_TEST_DSN','')
  if not dsn.startswith('mysql:host=127.0.0.1;port=') or ';dbname=' in dsn:
   raise RuntimeError('Provide a loopback-only NEURO_TEST_DSN without a database name; never use production credentials')
  cls.dbname='neuro_test_'+secrets.token_hex(8)
  cls.dbargs={'dsn':dsn,'user':os.environ.get('NEURO_TEST_USER','root'),'password':os.environ.get('NEURO_TEST_PASSWORD','')}
  cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
  for name in ['public','private','database','tests']:shutil.copytree(ROOT/name,cls.path/name,ignore=shutil.ignore_patterns('config.php','__pycache__'))
  cls.password=secrets.token_urlsafe(24)
  cls.sql('CREATE DATABASE `'+cls.dbname+'` CHARACTER SET utf8mb4',admin=True)
  cls.addClassCleanup(cls.cleanup)
  schema=(ROOT/'database/schema.sql').read_text();cls.sql(schema)
  cls.sql("INSERT INTO nd_admin VALUES (1, '"+cls.php_eval('echo password_hash($v["password"], PASSWORD_DEFAULT);',{'password':cls.password})+"')")
  sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close();cls.base='http://127.0.0.1:'+str(cls.port)
  cls.config={'db_host':'127.0.0.1','db_port':int(dsn.split('port=')[1]),'db_name':cls.dbname,'db_user':cls.dbargs['user'],'db_password':cls.dbargs['password'],'app_url':cls.base,'setup_key':''}
  if cls.stage>=5:
   cls.config.update(privacy_policy_approved=True,privacy_policy_version='test-policy-v1')
   (cls.path/'private/privacy-policy.txt').write_text('SYNTHETIC TEST FIXTURE ONLY. Not a legal policy.')
  cls.write_config()
  cls.log=(cls.path/'server.log').open('w');cls.proc=subprocess.Popen([cls.php,'-S','127.0.0.1:'+str(cls.port),'-t',str(cls.path/'public'),str(cls.path/'tests/router.php')],stdout=cls.log,stderr=cls.log)
  for _ in range(100):
   try:requests.get(cls.base,timeout=1);break
   except requests.ConnectionError:time.sleep(.1)
  else:raise RuntimeError('PHP server failed to start')
 @classmethod
 def php_eval(cls,code,values):
  r=subprocess.run([cls.php,'-r','$v=json_decode(stream_get_contents(STDIN),true);'+code],input=json.dumps(values),text=True,capture_output=True)
  if r.returncode:raise RuntimeError('Isolated PHP helper failed: '+r.stderr[:150])
  return r.stdout.strip()
 @classmethod
 def sql(cls,sql,admin=False,params=None):
  v=dict(cls.dbargs);v['dsn']+=('' if admin else ';dbname='+cls.dbname);v.update(sql=sql,params=params or [])
  output=cls.php_eval('$p=new PDO($v["dsn"],$v["user"],$v["password"],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]); if($v["params"]){$q=$p->prepare($v["sql"]);$q->execute($v["params"]);}else{$q=$p->query($v["sql"]);}echo json_encode($q->columnCount() ? $q->fetchAll(PDO::FETCH_ASSOC) : []);',v)
  return json.loads(output)
 @classmethod
 def write_config(cls):
  def q(v):
   if isinstance(v,bool):return 'true' if v else 'false'
   return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
  (cls.path/'private/config.php').write_text('<?php return ['+','.join(q(k)+'=>'+q(v) for k,v in cls.config.items())+'];')
 @classmethod
 def cleanup(cls):
  if hasattr(cls,'proc'):cls.proc.terminate();cls.proc.wait(timeout=5);cls.log.close()
  cls.sql('DROP DATABASE `'+cls.dbname+'`',admin=True);cls.tmp.cleanup()
 def setUp(self):self.sql('DELETE FROM nd_limits')
 def api(self,route):return self.base+'/api.php?r='+route
 def lead(self,**changes):
  data={'name':'Тест','contact':'test@example.com','service':'ИИ-агент','idea':'Тестовый проект'}
  if self.stage>=3:data['idempotency_key']=secrets.token_hex(32)
  if self.stage>=5:data.update(consent=True,policy_version='test-policy-v1')
  data.update(changes);return data
 def owner(self):
  s=requests.Session();r=s.post(self.api('login'),json={'password':self.password});self.assertEqual(r.status_code,200);return s,{'X-CSRF-Token':r.json()['csrf']}
 def test_01_confirmed_persistence(self):
  r=requests.post(self.api('leads'),json=self.lead());self.assertEqual(r.status_code,201,r.text);self.assertTrue(r.headers['Content-Type'].startswith('application/json'))
  self.assertTrue(r.json()['ok']);lead_id=r.json()['lead_id'];self.assertTrue(lead_id>0)
  rows=self.sql('SELECT id FROM nd_leads WHERE id=?',params=[lead_id]);self.assertEqual(len(rows),1)
  self.assertEqual(requests.get(self.api('leads')).status_code,401)
 def test_02_atomic_version_conflict(self):
  if self.stage<2:self.skipTest('Fix 2 not enabled')
  lead_id=requests.post(self.api('leads'),json=self.lead()).json()['lead_id'];a,ha=self.owner();b,hb=self.owner()
  patch={'status':'В работе','notes':'Первая вкладка','next_step':'Позвонить','version':1}
  url=self.api('leads/'+str(lead_id))
  first=a.patch(url,json=patch,headers=ha);self.assertEqual(first.status_code,200,first.text);self.assertEqual(first.json()['version'],2)
  patch['notes']='Устаревшая вторая вкладка'
  self.assertEqual(b.patch(url,json=patch,headers=hb).status_code,409)
  row=self.sql('SELECT notes,version FROM nd_leads WHERE id=?',params=[lead_id])[0];self.assertEqual(row['notes'],'Первая вкладка');self.assertEqual(row['version'],2)
  patch['version']=2;self.assertEqual(b.patch(url,json=patch,headers=hb).status_code,200)
  patch.pop('version');self.assertEqual(b.patch(url,json=patch,headers=hb).status_code,422)
  self.assertEqual(a.patch(url,json=patch).status_code,403)
 def test_03_contact_and_idempotency(self):
  if self.stage<3:self.skipTest('Fix 3 not enabled')
  for contact in ['x','broken@','@abc','12345','+1 202 555 0123','+8 495 123-45-67']:
   r=requests.post(self.api('leads'),json=self.lead(contact=contact));self.assertEqual(r.status_code,422,(contact,r.text))
  for contact in ['owner+test@example.com','@minden2006','+7 (999) 123-45-67','8 495 123-45-67']:
   self.assertEqual(requests.post(self.api('leads'),json=self.lead(contact=contact)).status_code,201,contact)
  payload=self.lead();a=requests.post(self.api('leads'),json=payload);b=requests.post(self.api('leads'),json=payload)
  self.assertEqual(a.status_code,201);self.assertEqual(a.json(),b.json())
  rows=self.sql('SELECT id FROM nd_leads WHERE request_key=?',params=[payload['idempotency_key']]);self.assertEqual(len(rows),1)
  payload['idea']='Другая задача';self.assertEqual(requests.post(self.api('leads'),json=payload).status_code,409)
  payload['idempotency_key']=secrets.token_hex(32);c=requests.post(self.api('leads'),json=payload);self.assertEqual(c.status_code,201);self.assertNotEqual(c.json()['lead_id'],a.json()['lead_id'])
  self.assertEqual(requests.post(self.api('leads'),json=self.lead(service='INVALID')).status_code,422)
 def test_04_safe_errors(self):
  if self.stage<4:self.skipTest('Fix 4 not enabled')
  r=requests.post(self.api('leads'),data='broken',headers={'Content-Type':'application/json'});self.assertEqual(r.status_code,400)
  self.assertEqual(requests.post(self.api('leads'),data='x').status_code,415)
  owner,headers=self.owner()
  bad=requests.post(self.api('login'),json={'password':'wrong'});self.assertEqual(bad.status_code,401)
  self.assertNotIn(self.config['db_password']+'password-secret-marker',bad.text)
  self.assertNotIn(str(self.path),bad.text)
  self.config['db_name']=self.dbname+'_absent';self.write_config()
  try:
   failed=owner.get(self.api('leads'));self.assertEqual(failed.status_code,503)
   self.assertIn('X-Request-ID',failed.headers)
   self.assertNotIn(self.dbname,failed.text);self.assertNotIn('PDO',failed.text)
   log=(self.path/'server.log').read_text();self.assertIn('backend_failure',log);self.assertIn('sqlstate',log)
  finally:self.config['db_name']=self.dbname;self.write_config()
 def test_04_browser_conflict_and_draft(self):
  if self.stage<4:self.skipTest('Fix 4 not enabled')
  from playwright.sync_api import sync_playwright
  lead_id=requests.post(self.api('leads'),json=self.lead(name='UI regression')).json()['lead_id']
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(self.base+'/studio.php');page.locator('#password').fill(self.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
   page.locator('#search').fill('UI regression');page.get_by_role('button',name='Открыть →').click();page.locator('#notes').fill('Local draft')
   owner,headers=self.owner();self.assertEqual(owner.patch(self.api('leads/'+str(lead_id)),json={'version':1,'status':'В работе','notes':'Newer server text','next_step':''},headers=headers).status_code,200)
   page.locator('#save').click();page.locator('#reload-current').wait_for(state='visible');self.assertEqual(page.locator('#notes').input_value(),'Local draft')
   page.once('dialog',lambda d:d.accept());page.locator('#reload-current').click();page.wait_for_function("() => document.querySelector('#notes').value==='Newer server text'")
   state={'status':401}
   def failure(route):
    if route.request.method=='PATCH':route.fulfill(status=state['status'],content_type='text/html',body='SQL password=secret /private/config.php')
    else:route.continue_()
   page.route('**/api.php?*',failure)
   page.locator('#notes').fill('Unsaved after expiry');page.locator('#save').click();page.locator('#login-panel').wait_for(state='visible')
   self.assertIn('Войдите',page.locator('#message').inner_text())
   page.locator('#password').fill(self.password);page.locator('#login-form button').click();page.locator('#editor').wait_for(state='visible');self.assertEqual(page.locator('#notes').input_value(),'Unsaved after expiry')
   state['status']=503;page.locator('#save').click();page.wait_for_function("() => document.querySelector('#edit-message').textContent.includes('Сервис временно')")
   self.assertNotIn('secret',page.locator('#edit-message').inner_text());self.assertEqual(page.locator('#notes').input_value(),'Unsaved after expiry')
   page.unroute('**/api.php?*',failure);page.locator('#save').click();page.locator('#editor').wait_for(state='hidden')
   self.assertEqual(self.sql('SELECT notes FROM nd_leads WHERE id=?',params=[lead_id])[0]['notes'],'Unsaved after expiry')
   self.assertEqual(errors,[]);browser.close()
 def test_05_consent(self):
  if self.stage<5:self.skipTest('Fix 5 not enabled')
  for consent in [False,None,'true',1]:
   r=requests.post(self.api('leads'),json=self.lead(consent=consent));self.assertEqual(r.status_code,422,r.text)
  self.assertEqual(requests.post(self.api('leads'),json=self.lead(policy_version='old')).status_code,409)
  before=int(time.time());r=requests.post(self.api('leads'),json=self.lead());self.assertEqual(r.status_code,201,r.text)
  row=self.sql('SELECT consent,consent_at,policy_version,policy_hash FROM nd_leads WHERE id=?',params=[r.json()['lead_id']])[0]
  self.assertEqual(row['consent'],1);self.assertGreaterEqual(row['consent_at'],before);self.assertEqual(row['policy_version'],'test-policy-v1')
  self.assertEqual(row['policy_hash'],hashlib.sha256((self.path/'private/privacy-policy.txt').read_bytes()).hexdigest())
  self.assertEqual(requests.get(self.api('leads')).status_code,401)
  self.config['privacy_policy_approved']=False;self.write_config()
  try:
   self.assertEqual(requests.get(self.base+'/privacy.php').status_code,503)
   self.assertFalse(requests.get(self.api('privacy')).json()['enabled'])
   self.assertEqual(requests.post(self.api('leads'),json=self.lead()).status_code,503)
  finally:self.config['privacy_policy_approved']=True;self.write_config()
 def test_05_browser_consent_and_safe_retry(self):
  if self.stage<5:self.skipTest('Fix 5 not enabled')
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page()
   page.goto(self.base);page.locator('#brief-form button').wait_for(state='visible');page.wait_for_function("() => !document.querySelector('#brief-form button').disabled")
   self.assertFalse(page.locator('#consent').is_checked())
   page.locator('#name').fill('Public retry regression');page.locator('#contact-value').fill('@minden2006');page.locator('#idea').fill('Заявка после потери ответа')
   calls=[]
   def lose_response(route):
    if route.request.method!='POST':route.continue_();return
    calls.append(route.request.post_data_json)
    if len(calls)==1:
     result=route.fetch();self.assertEqual(result.status,201)
     route.fulfill(status=503,content_type='text/html',body='private SQL secret')
    else:route.continue_()
   page.route('**/api.php?r=leads',lose_response)
   page.locator('#brief-form').evaluate('(form)=>form.requestSubmit()');page.wait_for_timeout(100);self.assertEqual(calls,[])
   page.locator('#consent').check()
   page.locator('#brief-form').evaluate('(form)=>{form.requestSubmit();form.requestSubmit();}')
   page.wait_for_function("() => document.querySelector('#form-status').textContent.includes('Сервис временно')")
   self.assertEqual(len(calls),1);self.assertEqual(page.locator('#name').input_value(),'Public retry regression');self.assertNotIn('secret',page.locator('#form-status').inner_text())
   page.locator('#brief-form button').click();page.get_by_text('Заявка сохранена!',exact=False).wait_for()
   self.assertEqual(len(calls),2);self.assertEqual(calls[0]['idempotency_key'],calls[1]['idempotency_key'])
   self.assertEqual(len(self.sql('SELECT id FROM nd_leads WHERE request_key=?',params=[calls[0]['idempotency_key']])),1)
   self.assertFalse(page.locator('#consent').is_checked())
   for width in [320,375,430,768,1024,1440]:
    page.set_viewport_size({'width':width,'height':900});self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'),width)
   self.assertEqual(requests.get(self.base+'/privacy.php').status_code,200)
   self.config['privacy_policy_version']='test-policy-v2';self.write_config()
   try:
    page.locator('#name').fill('Policy changed draft');page.locator('#contact-value').fill('test@example.com');page.locator('#idea').fill('Не терять текст');page.locator('#consent').check();page.locator('#brief-form button').click()
    page.wait_for_function("() => document.querySelector('#form-status').textContent.includes('Документы обновлены')")
    page.wait_for_function("() => !document.querySelector('#consent').disabled")
    self.assertFalse(page.locator('#consent').is_checked());self.assertEqual(page.locator('#idea').input_value(),'Не терять текст')
   finally:self.config['privacy_policy_version']='test-policy-v1';self.write_config()
   browser.close()
 def test_06_additive_migrations_preserve_history(self):
  import zipfile,re
  # Baseline fixture belongs to tests; no live database is migrated.
  old=(ROOT/'tests/legacy_leads.sql').read_text()
  self.sql(old)
  self.sql("INSERT INTO nd_leads_legacy (name,contact,service,idea,notes,created) VALUES ('История','old@example.com','ИИ-агент','Старая запись','Сохранить',1)")
  for file in sorted((ROOT/'database/migrations').glob('*.sql')):
   self.sql(file.read_text().replace('nd_leads','nd_leads_legacy'))
  row=self.sql('SELECT * FROM nd_leads_legacy')[0]
  self.assertEqual(row['notes'],'Сохранить');self.assertEqual(row['version'],1);self.assertIsNone(row['consent']);self.assertIsNone(row['request_key'])
