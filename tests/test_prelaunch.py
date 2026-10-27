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
  cls.dbargs={'dsn':dsn+';charset=utf8mb4','user':os.environ.get('NEURO_TEST_USER','root'),'password':os.environ.get('NEURO_TEST_PASSWORD','')}
  cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
  for name in ['public','private','database','tests','scripts']:shutil.copytree(ROOT/name,cls.path/name,ignore=shutil.ignore_patterns('config.php','__pycache__'))
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
  cls.log=(cls.path/'server.log').open('w');cls.proc=subprocess.Popen([cls.php,'-d','opcache.enable=0','-d','opcache.enable_cli=0','-S','127.0.0.1:'+str(cls.port),'-t',str(cls.path/'public'),str(cls.path/'tests/router.php')],stdout=cls.log,stderr=cls.log)
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
   # Privacy has no SQL dependency; a missing database must not break this API.
   privacy=requests.get(self.api('privacy'));self.assertEqual(privacy.status_code,200);self.assertTrue(privacy.json()['enabled'])
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
   self.assertEqual(requests.get(self.base+'/privacy.php').status_code,200)
   self.assertFalse(requests.get(self.api('privacy')).json()['enabled'])
   self.assertEqual(requests.post(self.api('leads'),json=self.lead()).status_code,503)
  finally:self.config['privacy_policy_approved']=True;self.write_config()
 def test_05_release_policy_activation_and_consent_binding(self):
  legal=self.path/'private/legal/privacy-2026-10-27-v2.json';original=legal.read_bytes();old=dict(self.config)
  try:
   self.config.update(privacy_policy_approved=False,privacy_policy_version='');self.write_config()
   doc=json.loads(original);version=doc['version']
   policy=requests.get(self.api('privacy')).json();self.assertTrue(policy['enabled']);self.assertEqual(policy['version'],version)
   page=requests.get(self.base+'/privacy.php');self.assertEqual(page.status_code,200);self.assertIn(doc['owner'],page.text)
   consent=requests.get(self.base+'/consent.php');self.assertEqual(consent.status_code,200);self.assertIn(version,consent.text)
   self.assertEqual(requests.post(self.api('leads'),json=self.lead(policy_version=version,consent=False)).status_code,422)
   result=requests.post(self.api('leads'),json=self.lead(policy_version=version));self.assertEqual(result.status_code,201,result.text)
   row=self.sql('SELECT policy_hash,policy_version FROM nd_leads WHERE id=?',params=[result.json()['lead_id']])[0]
   self.assertEqual(row['policy_version'],version)
   self.assertEqual(row['policy_hash'],hashlib.sha256((doc['policy']+'\nCONSENT\n'+doc['consent']).encode()).hexdigest())
   for changed in [{**doc,'activation_requested':False},{**doc,'consent':''},{**doc,'version':'wrong'}]:
    legal.write_text(json.dumps(changed));self.assertFalse(requests.get(self.api('privacy')).json()['enabled'])
    self.assertEqual(requests.post(self.api('leads'),json=self.lead(policy_version=version)).status_code,503)
   legal.write_bytes(original);self.config['privacy_policy_disabled']=True;self.write_config()
   self.assertFalse(requests.get(self.api('privacy')).json()['enabled'])
  finally:legal.write_bytes(original);self.config.clear();self.config.update(old);self.write_config()
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
 def test_06_privacy_files_fail_closed(self):
  policy=self.path/'private/privacy-policy.txt';original=policy.read_bytes()
  try:
   for content in [b'', b'   \n']:
    policy.write_bytes(content)
    self.assertEqual(requests.get(self.api('privacy')).json()['enabled'],False)
    self.assertEqual(requests.get(self.base+'/privacy.php').status_code,200)
    self.assertEqual(requests.post(self.api('leads'),json=self.lead()).status_code,503)
   policy.unlink()
   self.assertFalse(requests.get(self.api('privacy')).json()['enabled'])
   policy.write_bytes(original);policy.chmod(0)
   if os.access(policy,os.R_OK):self.fail('Run privacy permission regression as an unprivileged user')
   r=requests.get(self.api('privacy'));self.assertEqual(r.status_code,200);self.assertFalse(r.json()['enabled'])
   page=requests.get(self.base+'/privacy.php');self.assertEqual(page.status_code,200)
   self.assertIn('data-privacy-mode="notice"',page.text);self.assertNotIn(str(self.path),page.text)
   self.assertEqual(requests.post(self.api('leads'),json=self.lead()).status_code,503)
   self.assertIn('privacy_policy_unreadable',(self.path/'server.log').read_text())
  finally:policy.chmod(0o600);policy.write_bytes(original)
  policy.write_text('<script>synthetic</script>')
  try:
   page=requests.get(self.base+'/privacy.php');self.assertEqual(page.status_code,200)
   self.assertIn('&lt;script&gt;synthetic&lt;/script&gt;',page.text)
   self.assertNotIn('<script>synthetic',page.text)
   data=requests.get(self.api('privacy')).json();self.assertTrue(data['enabled']);self.assertNotIn('text',data);self.assertNotIn('settings',data)
  finally:policy.write_bytes(original)
 def test_06_browser_disabled_policy(self):
  from playwright.sync_api import sync_playwright
  policy=self.path/'private/privacy-policy.txt'
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   try:
    page=browser.new_page()
    for approved,readable in [(False,True),(True,False)]:
     self.config['privacy_policy_approved']=approved;self.write_config();policy.chmod(0o600 if readable else 0)
     with page.expect_response(lambda r:'api.php?r=privacy' in r.url):page.goto(self.base)
     self.assertTrue(page.locator('#consent').is_disabled())
     self.assertFalse(page.locator('#consent').is_checked())
     self.assertTrue(page.locator('#brief-form button').is_disabled())
   finally:
    policy.chmod(0o600);self.config['privacy_policy_approved']=True;self.write_config();browser.close()
 def test_07_shared_config_failure_and_readonly_diagnostics(self):
  config=self.path/'private/config.php';original=config.read_bytes()
  try:
   config.write_text('<?php return [ BROKEN SYNTAX SECRET_MARKER;')
   ids=[]
   for route in ['/setup.php','/privacy.php','/api.php?r=privacy']:
    r=requests.get(self.base+route);self.assertEqual(r.status_code,503)
    self.assertIn('Сервис временно недоступен',r.json()['detail'])
    self.assertNotIn('SECRET_MARKER',r.text);self.assertNotIn(str(self.path),r.text)
    ids.append(r.headers['X-Request-ID'])
   log=(self.path/'server.log').read_text()
   for request_id in ids:self.assertIn(request_id,log)
   self.assertIn('ParseError',log)
   r=subprocess.run([self.php,str(self.path/'scripts/diagnose.php')],capture_output=True,text=True)
   self.assertEqual(r.returncode,1);self.assertNotIn('SECRET_MARKER',r.stdout+r.stderr)
   self.assertTrue(any(item['check']=='config_load' and item['type']=='ParseError' for item in json.loads(r.stdout)))
  finally:config.write_bytes(original)
  before=self.sql('SELECT COUNT(*) AS n FROM nd_leads')[0]['n']
  r=subprocess.run([self.php,str(self.path/'scripts/diagnose.php')],capture_output=True,text=True)
  data={item['check']:item for item in json.loads(r.stdout)}
  for key in ['config_structure','database_connection','schema_nd_admin','schema_nd_leads','schema_nd_sessions','schema_nd_limits','administrator_exists']:
   self.assertTrue(data[key]['ok'],key)
  self.assertNotIn(self.password,r.stdout+r.stderr)
  self.assertEqual(self.sql('SELECT COUNT(*) AS n FROM nd_leads')[0]['n'],before)
  self.config['db_name']=self.dbname+'_absent';self.write_config()
  try:
   r=subprocess.run([self.php,str(self.path/'scripts/diagnose.php')],capture_output=True,text=True)
   self.assertEqual(r.returncode,1);self.assertNotIn(self.dbname,r.stdout+r.stderr)
   self.assertNotIn(str(self.path),r.stdout+r.stderr)
   self.assertTrue(any(item['check']=='database' and not item['ok'] and 'sqlstate' in item for item in json.loads(r.stdout)))
  finally:self.config['db_name']=self.dbname;self.write_config()
 def test_08_setup_authentication_session_and_logout(self):
  # Only this suite's random database is changed. Restore its synthetic account afterwards.
  original=self.sql('SELECT password_hash FROM nd_admin WHERE id=1')[0]['password_hash']
  self.config['setup_key']=secrets.token_hex(32);self.write_config()
  try:
   self.assertEqual(requests.get(self.base+'/setup.php').status_code,403)
   self.assertEqual(requests.post(self.base+'/setup.php',data={'setup_key':self.config['setup_key'],'password':'do-not-overwrite','repeat':'do-not-overwrite'}).status_code,403)
   self.assertEqual(self.sql('SELECT password_hash FROM nd_admin WHERE id=1')[0]['password_hash'],original)
   self.sql('DELETE FROM nd_admin WHERE id=1')
   self.assertEqual(requests.get(self.base+'/setup.php').status_code,200)
   payload={'setup_key':self.config['setup_key'],'password':self.password,'repeat':self.password}
   self.assertEqual(requests.post(self.base+'/setup.php',data=payload,headers={'Origin':'https://invalid.example'}).status_code,403)
   wrong=dict(payload,setup_key='wrong');self.assertEqual(requests.post(self.base+'/setup.php',data=wrong).status_code,403)
   short=dict(payload,password='short',repeat='short');self.assertEqual(requests.post(self.base+'/setup.php',data=short).status_code,422)
   r=requests.post(self.base+'/setup.php',data=payload,allow_redirects=False);self.assertEqual(r.status_code,303);self.assertEqual(r.headers['Location'],'/studio.php')
   self.assertEqual(requests.post(self.base+'/setup.php',data=payload).status_code,403)
   self.assertEqual(requests.post(self.api('login'),json={'password':'incorrect'}).status_code,401)
   owner=requests.Session();login=owner.post(self.api('login'),json={'password':self.password});self.assertEqual(login.status_code,200)
   cookie=login.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
   csrf={'X-CSRF-Token':login.json()['csrf']}
   self.assertEqual(owner.get(self.api('session')).status_code,200)
   self.assertEqual(owner.post(self.api('logout')).status_code,403)
   self.assertEqual(owner.post(self.api('logout'),headers=dict(csrf,Origin='https://invalid.example')).status_code,403)
   self.assertEqual(owner.get(self.api('session')).status_code,200)
   self.assertEqual(owner.post(self.api('logout'),headers=csrf).status_code,200)
   self.assertEqual(owner.get(self.api('session')).status_code,401)
   owner,csrf=self.owner()
   self.sql('UPDATE nd_sessions SET expires=0 WHERE token=?',params=[hashlib.sha256(owner.cookies['nd_session'].encode()).hexdigest()])
   self.assertEqual(owner.get(self.api('session')).status_code,401)
  finally:
   self.sql('DELETE FROM nd_admin WHERE id=1')
   self.sql('INSERT INTO nd_admin(id,password_hash) VALUES (1,?)',params=[original])
   self.config['setup_key']='';self.write_config()
  self.assertEqual(requests.get(self.base+'/setup.php').status_code,503)
 def test_09_additive_migrations_preserve_history(self):
  import zipfile,re
  # Baseline fixture belongs to tests; no live database is migrated.
  old=(ROOT/'tests/legacy_leads.sql').read_text()
  self.sql(old)
  self.sql("INSERT INTO nd_leads_legacy (name,contact,service,idea,notes,created) VALUES ('История','old@example.com','ИИ-агент','Старая запись','Сохранить',1)")
  for file in sorted((ROOT/'database/migrations').glob('*.sql')):
   self.sql(file.read_text().replace('nd_leads','nd_leads_legacy'))
  row=self.sql('SELECT * FROM nd_leads_legacy')[0]
  self.assertEqual(row['notes'],'Сохранить');self.assertEqual(row['version'],1);self.assertIsNone(row['consent']);self.assertIsNone(row['request_key'])
 def test_10_browser_pending_edits_survive_success(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   try:
    for changed in ['name','contact','service','idea','consent','all']:
     with self.subTest(changed=changed):
      page=browser.new_page();page.goto(self.base)
      page.wait_for_function("() => !document.querySelector('#brief-form button').disabled")
      page.locator('#name').fill('Original '+changed);page.locator('#contact-value').fill('original@example.com')
      page.locator('#idea').fill('Original idea');page.locator('#consent').check()
      calls=[];persisted=[]
      edits={'name':'Edited name','contact':'edited@example.com','service':'Другая идея','idea':'Edited idea','consent':False}
      selectors={'name':'#name','contact':'#contact-value','service':'#service','idea':'#idea','consent':'#consent'}
      expected={key:page.locator(selector).is_checked() if key=='consent' else page.locator(selector).input_value() for key,selector in selectors.items()}
      for key in edits:
       if changed in [key,'all']:expected[key]=edits[key]
      def hold_success(route):
       calls.append(route.request.post_data_json)
       response=route.fetch();self.assertEqual(response.status,201);persisted.append(response.json()['lead_id'])
       if len(calls)==1:
        self.assertTrue(page.locator('#brief-form button').is_disabled())
        for key,selector in selectors.items():
         if changed in [key,'all']:
          page.locator(selector).evaluate('(node,value)=>{if(node.type==="checkbox")node.checked=value;else node.value=value;node.dispatchEvent(new Event("input",{bubbles:true}));}',edits[key])
        # Repeated submission while pending must not create another request.
        page.locator('#brief-form').evaluate('(form)=>form.dispatchEvent(new Event("submit",{bubbles:true,cancelable:true}))')
       route.fulfill(response=response)
      page.route('**/api.php?r=leads',hold_success)
      page.locator('#brief-form button').click()
      page.wait_for_function("() => document.querySelector('#form-status').textContent.includes('Новые правки')")
      self.assertEqual(len(calls),1)
      for key,selector in selectors.items():
       actual=page.locator(selector).is_checked() if key=='consent' else page.locator(selector).input_value()
       self.assertEqual(actual,expected[key],key)
      row=self.sql('SELECT name,contact,service,idea FROM nd_leads WHERE id=?',params=[persisted[0]])[0]
      for key in row:self.assertEqual(row[key],calls[0][key])
      self.assertFalse(page.locator('#brief-form button').is_disabled())
      if changed=='all':
       page.locator('#brief-form button').click();page.wait_for_timeout(50);self.assertEqual(len(calls),1)
       page.locator('#consent').check();page.locator('#brief-form button').click()
       page.wait_for_function("() => document.querySelector('#form-status').textContent.includes('Заявка сохранена!')")
       self.assertEqual(len(calls),2);self.assertNotEqual(calls[0]['idempotency_key'],calls[1]['idempotency_key'])
       self.assertNotEqual(persisted[0],persisted[1])
       for key in ['name','contact','service','idea']:self.assertEqual(calls[1][key],edits[key])
       self.assertEqual(page.locator('#name').input_value(),'');self.assertFalse(page.locator('#consent').is_checked())
      page.close()
   finally:browser.close()
 def test_11_browser_initial_login_and_real_auth_errors(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   try:
    context=browser.new_context();page=context.new_page();page.goto(self.base+'/studio.php');page.wait_for_load_state('networkidle')
    self.assertTrue(page.locator('#login-panel').is_visible());self.assertEqual(page.locator('#message').inner_text(),'')
    page.locator('#password').fill('incorrect');page.locator('#login-form button').click()
    page.wait_for_function("() => document.querySelector('#message').textContent.includes('пароль неверен')")
    page.locator('#password').fill(self.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
    self.assertEqual(page.locator('#message').inner_text(),'')
    restored=context.new_page();restored.goto(self.base+'/studio.php');restored.locator('#dashboard').wait_for(state='visible')
    self.assertEqual(restored.locator('#message').inner_text(),'')
    # A valid initial session followed by leads 401 is a real expiry, not a quiet first visit.
    expired=context.new_page();expired.route('**/api.php?r=leads',lambda route:route.fulfill(status=401,content_type='application/json',body='{}'))
    expired.goto(self.base+'/studio.php')
    expired.wait_for_function("() => document.querySelector('#message').textContent.includes('Срок входа истёк')")
    self.assertTrue(expired.locator('#login-panel').is_visible())
    restored.locator('#logout').click();restored.locator('#login-panel').wait_for(state='visible')
    self.assertEqual(restored.locator('#message').inner_text(),'');context.close()
    for failure in ['server','network']:
     page=browser.new_page()
     def unavailable(route):
      if failure=='network':route.abort()
      else:route.fulfill(status=503,content_type='application/json',body='{}')
     page.route('**/api.php?r=session',unavailable);page.goto(self.base+'/studio.php')
     page.wait_for_function("() => document.querySelector('#message').textContent.length>0")
     message=page.locator('#message').inner_text()
     self.assertIn('Сервис временно' if failure=='server' else 'Не удалось связаться',message)
     page.close()
   finally:browser.close()
