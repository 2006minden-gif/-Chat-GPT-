"""Stage 4 HTTP/SMTP/browser tests. Only random loopback databases; no production mail."""
import base64
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import socketserver
import subprocess
import threading
import time
import unittest
import requests
import test_prelaunch as fixture

class SMTPHandler(socketserver.StreamRequestHandler):
 def handle(self):
  self.wfile.write(b'220 synthetic SMTP\r\n');self.wfile.flush();recipient=''
  while True:
   line=self.rfile.readline(8192)
   if not line:return
   if line.startswith(b'EHLO'):reply=b'250 synthetic\r\n'
   elif line.startswith(b'MAIL FROM:'):reply=b'250 OK\r\n'
   elif line.startswith(b'RCPT TO:'):recipient=line.decode().strip();reply=b'250 OK\r\n'
   elif line==b'DATA\r\n':
    if self.server.reject or getattr(self.server,'reject_once',0)>0:
     self.server.reject_once=max(0,getattr(self.server,'reject_once',0)-1);reply=b'451 synthetic failure\r\n'
    else:
     self.wfile.write(b'354 send\r\n');self.wfile.flush();data=b''
     while True:
      chunk=self.rfile.readline(8192)
      if chunk in [b'.\r\n',b'']:break
      data+=chunk
     self.server.messages.append((recipient,data));reply=b'250 accepted\r\n'
   elif line.startswith(b'QUIT'):self.wfile.write(b'221 bye\r\n');return
   else:reply=b'500 unsupported\r\n'
   self.wfile.write(reply);self.wfile.flush()
class SMTPServer(socketserver.ThreadingTCPServer):
 allow_reuse_address=True
 daemon_threads=True

class CustomerAuth(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  # Nested class is not discovered as another copy of Prelaunch's tests.
  class AuthFixture(fixture.Prelaunch):
   @classmethod
   def write_config(c):
    payload=base64.b64encode(json.dumps(c.config).encode()).decode()
    (c.path/'private/config.php').write_text("<?php return json_decode(base64_decode('"+payload+"'), true);")
  cls.f=AuthFixture;cls.f.setUpClass();cls.addClassCleanup(cls.f.doClassCleanups)
  cls.smtp=SMTPServer(('127.0.0.1',0),SMTPHandler);cls.smtp.messages=[];cls.smtp.reject=False
  cls.thread=threading.Thread(target=cls.smtp.serve_forever,daemon=True);cls.thread.start()
  cls.addClassCleanup(cls.smtp.server_close);cls.addClassCleanup(cls.smtp.shutdown)
  for runner in ['migrate.php','migrate-customer.php']:
   r=subprocess.run([cls.f.php,str(cls.f.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if r.returncode:raise RuntimeError(r.stderr)
  cls.f.config.update(customer_auth_enabled=True,customer_auth_privacy_approved=True,customer_auth_test_mode=True,customer_mail={'transport':'test-smtp','host':'127.0.0.1','port':cls.smtp.server_address[1],'from':'noreply@example.invalid','encryption':'none'})
  cls.f.write_config();cls.base=cls.f.base
 def setUp(self):
  self.smtp.messages.clear();self.smtp.reject=False;self.smtp.reject_once=0
  for table in ['nd_customer_consents','nd_customer_auth_events','nd_customer_sessions','nd_customer_tokens','nd_customer_auth','nd_customer_accounts','nd_customers','nd_limits']:self.f.sql('DELETE FROM '+table)
  self.f.config.update(customer_auth_enabled=True,customer_auth_privacy_approved=True,privacy_policy_approved=True,privacy_policy_version='test-policy-v1')
  self.f.config['customer_mail'].update(transport='test-smtp',host='127.0.0.1',encryption='none');self.f.write_config()
  self.s=requests.Session();self.bootstrap(self.s)
 def url(self,route):return self.base+'/customer-api.php?r='+route
 def bootstrap(self,s):
  r=s.get(self.url('session'));self.assertEqual(r.status_code,200,r.text);s.headers['X-CSRF-Token']=r.json()['csrf'];return r.json()
 def post(self,route,data=None,s=None):return (s or self.s).post(self.url(route),json=data if data is not None else {})
 def payload(self,**changes):
  p={'name':'Тестовый клиент','email':'Customer@Example.invalid','password':'LongTestPassword123!','password_confirmation':'LongTestPassword123!','consent':True,'policy_version':'test-policy-v1'};p.update(changes);return p
 def link(self,purpose=None):
  message=self.smtp.messages[-1][1];text=base64.b64decode(message.split(b'\r\n\r\n',1)[1]).decode()
  link=re.search(r'http://[^\s]+',text).group()
  if purpose:self.assertIn('?view='+purpose,link)
  token=link.split('#token=')[1];self.assertRegex(token,r'^[a-f0-9]{64}$');return link,token
 def register(self,verify=False,email='Customer@Example.invalid'):
  r=self.post('register',self.payload(email=email));self.assertEqual(r.status_code,202,r.text)
  _,token=self.link('verify')
  if verify:self.assertEqual(self.post('verify',self.payload(token=token)).status_code,200)
  return token
 def login(self,s=None):
  r=self.post('login',{'email':'customer@example.invalid','password':'LongTestPassword123!'},s=s);self.assertEqual(r.status_code,200,r.text)
  (s or self.s).headers['X-CSRF-Token']=r.json()['csrf'];return r
 def account(self):return self.f.sql('SELECT * FROM nd_customer_accounts ORDER BY id LIMIT 1')[0]
 def owner(self):
  s=requests.Session();r=s.post(self.base+'/api.php?r=login',json={'password':self.f.password});self.assertEqual(r.status_code,200);s.headers['X-CSRF-Token']=r.json()['csrf'];return s
 def test_registration_verification_login_and_separate_sessions(self):
  old=self.s.cookies.get('nd_customer');raw=self.register();a=self.account();self.assertEqual(a['email'],'customer@example.invalid');self.assertEqual(a['status'],'invited');self.assertNotIn('LongTestPassword',a['password_hash'])
  self.assertEqual(self.post('login',{'email':a['email'],'password':'LongTestPassword123!'}).status_code,401)
  self.assertEqual(self.post('verify',self.payload(token=raw)).status_code,200);self.login();self.assertNotEqual(old,self.s.cookies.get('nd_customer'))
  session=self.s.get(self.url('session')).json();self.assertTrue(session['authenticated']);self.assertEqual(session['account']['name'],'Тестовый клиент')
  self.assertEqual(self.s.get(self.base+'/api.php?r=leads').status_code,401)
  owner=self.owner();self.assertFalse(owner.get(self.url('session')).json()['authenticated'])
  self.assertEqual(owner.get(self.base+'/api.php?r=session').status_code,200)
 def test_invalid_email_and_confirmation_and_weak_password(self):
  for changes in [{'email':'bad@'},{'email':'a\r\n@example.invalid'},{'password':'short','password_confirmation':'short'},{'password':'NoNumbersInPassword','password_confirmation':'NoNumbersInPassword'},{'password':'A1'+'я'*40,'password_confirmation':'A1'+'я'*40},{'password_confirmation':'different'}]:
   with self.subTest(changes=list(changes)):self.assertEqual(self.post('register',self.payload(**changes)).status_code,422)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_accounts')[0]['n'],0)
 def test_duplicate_registration_is_neutral_and_never_changes_password(self):
  self.register();a=self.account();r=self.post('register',self.payload(name='Other',email='CUSTOMER@example.invalid',password='DifferentPassword123',password_confirmation='DifferentPassword123'))
  self.assertEqual(r.status_code,202);self.assertEqual(self.account(),a);self.assertEqual(len(self.smtp.messages),1)
 def test_consent_and_approval_are_fail_closed(self):
  for consent in [False,'true',1,None]:self.assertEqual(self.post('register',self.payload(consent=consent)).status_code,422)
  self.assertEqual(self.post('register',self.payload(policy_version='old')).status_code,409)
  for flag in ['privacy_policy_approved','customer_auth_enabled','customer_auth_privacy_approved']:
   self.f.config[flag]=False;self.f.write_config()
   self.assertFalse(self.s.get(self.url('settings')).json()['enabled']);self.assertEqual(self.post('register',self.payload()).status_code,503)
   self.f.config[flag]=True;self.f.write_config()
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customers')[0]['n'],0)
 def test_consent_audit_is_private(self):
  self.register();row=self.f.sql('SELECT * FROM nd_customer_consents')[0];self.assertEqual(row['consent'],1);self.assertEqual(row['policy_version'],'test-policy-v1');self.assertEqual(row['policy_hash'],hashlib.sha256((self.f.path/'private/privacy-policy.txt').read_bytes()).hexdigest())
  self.assertEqual(requests.get(self.url('owner/accounts')).status_code,401)
 def test_csrf_and_cross_origin(self):
  self.s.headers['X-CSRF-Token']='wrong';self.assertEqual(self.post('register',self.payload()).status_code,403)
  self.bootstrap(self.s);self.s.headers['Origin']='https://evil.invalid';self.assertEqual(self.post('register',self.payload()).status_code,403)
  self.s.headers.pop('Origin');self.assertEqual(requests.post(self.url('register'),json=self.payload()).status_code,401)
 def test_token_hashes_and_single_use_verification(self):
  token=self.register();rows=self.f.sql('SELECT token_hash FROM nd_customer_tokens');self.assertEqual(rows[0]['token_hash'],hashlib.sha256(token.encode()).hexdigest());self.assertNotIn(token,json.dumps(rows))
  self.assertEqual(self.post('verify',self.payload(token=token)).status_code,200);self.assertEqual(self.post('verify',self.payload(token=token)).status_code,422)
 def test_expired_verify_and_resend(self):
  token=self.register();self.f.sql('UPDATE nd_customer_tokens SET expires_at=1');self.assertEqual(self.post('verify',self.payload(token=token)).status_code,422)
  self.assertEqual(self.post('resend',{'email':'customer@example.invalid'}).status_code,202);_,new=self.link('verify');self.assertNotEqual(token,new)
  self.assertEqual(self.post('verify',self.payload(token=new)).status_code,200)
 def test_invitation_existing_customer_and_no_automatic_merge(self):
  self.f.sql("INSERT INTO nd_customers(name) VALUES ('Same name')");id=self.f.sql('SELECT id FROM nd_customers')[0]['id'];owner=self.owner()
  self.assertEqual(self.post('owner/invite',{'customer_id':id,'email':'invite@example.invalid'},s=owner).status_code,202);_,token=self.link('invite')
  r=self.post('invite',self.payload(token=token));self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.account()['customer_id'],id)
  self.assertEqual(self.post('invite',self.payload(token=token)).status_code,422)
  self.assertEqual(self.post('owner/invite',{'name':'Same name','email':'another@example.invalid'},s=owner).status_code,202)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customers')[0]['n'],2)
 def test_invitation_expired_and_missing_consent(self):
  owner=self.owner();self.assertEqual(self.post('owner/invite',{'name':'Invited','email':'invite@example.invalid'},s=owner).status_code,202);_,token=self.link()
  self.assertEqual(self.post('invite',self.payload(token=token,consent=False)).status_code,422);self.f.sql('UPDATE nd_customer_tokens SET expires_at=1');self.assertEqual(self.post('invite',self.payload(token=token)).status_code,422)
 def test_customer_cannot_invite_or_manage_accounts(self):
  self.register(True);self.login()
  self.assertEqual(self.post('owner/invite',{'name':'Other','email':'x@example.invalid'}).status_code,401)
  self.assertEqual(self.post('owner/lifecycle',{'account_id':self.account()['id'],'version':1,'action':'disable'}).status_code,401)
 def test_inviting_existing_email_never_reassigns_identity(self):
  self.register(True);a=self.account();self.f.sql("INSERT INTO nd_customers(name) VALUES ('Another')");other=self.f.sql('SELECT MAX(id) id FROM nd_customers')[0]['id'];owner=self.owner();count=len(self.smtp.messages)
  r=self.post('owner/invite',{'customer_id':other,'email':'CUSTOMER@example.invalid'},s=owner);self.assertEqual(r.status_code,202);self.assertEqual(self.account(),a);self.assertEqual(len(self.smtp.messages),count)
 def test_reset_changes_password_and_revokes_all_sessions(self):
  self.register(True);self.login();second=requests.Session();self.bootstrap(second);self.login(second)
  self.assertEqual(self.post('forgot',{'email':'customer@example.invalid'}).status_code,202);_,token=self.link('reset')
  self.assertEqual(self.post('reset',self.payload(token=token,password='NewLongPassword123',password_confirmation='NewLongPassword123')).status_code,200)
  self.assertFalse(self.bootstrap(second)['authenticated']);self.bootstrap(self.s)
  self.assertEqual(self.post('login',{'email':'customer@example.invalid','password':'LongTestPassword123!'}).status_code,401)
  r=self.post('login',{'email':'customer@example.invalid','password':'NewLongPassword123'});self.assertEqual(r.status_code,200);self.s.headers['X-CSRF-Token']=r.json()['csrf']
  self.assertEqual(self.post('reset',self.payload(token=token)).status_code,422)
 def test_expired_reset_and_reissue_invalidates_previous(self):
  self.register(True);self.post('forgot',{'email':'customer@example.invalid'});_,old=self.link();self.post('forgot',{'email':'customer@example.invalid'});_,new=self.link()
  self.assertEqual(self.post('reset',self.payload(token=old)).status_code,422);self.f.sql('UPDATE nd_customer_tokens SET expires_at=1');self.assertEqual(self.post('reset',self.payload(token=new)).status_code,422)
 def test_account_enumeration_responses(self):
  self.register(True)
  for route in ['forgot','resend']:
   a=self.post(route,{'email':'customer@example.invalid'});b=self.post(route,{'email':'absent@example.invalid'});self.assertEqual((a.status_code,a.json()),(b.status_code,b.json()))
  a=self.post('login',{'email':'customer@example.invalid','password':'WrongPassword123'});b=self.post('login',{'email':'absent@example.invalid','password':'WrongPassword123'});self.assertEqual((a.status_code,a.json()),(b.status_code,b.json()))
 def test_session_expiry_logout_and_no_crm_regression(self):
  self.register(True);self.login();self.f.sql('UPDATE nd_customer_sessions SET expires_at=1');self.assertFalse(self.bootstrap(self.s)['authenticated']);self.login()
  self.assertEqual(self.post('logout').status_code,200);self.assertFalse(self.bootstrap(self.s)['authenticated']);owner=self.owner()
  self.assertEqual(owner.get(self.base+'/api.php?r=session').status_code,200);self.assertEqual(owner.post(self.base+'/api.php?r=logout',json={}).status_code,200)
 def test_rate_limit_login_registration_invite_verify_reset(self):
  for route in ['register','login','owner/invite','verify','reset','resend','forgot']:
   self.f.sql('DELETE FROM nd_limits');kind='owner' if route.startswith('owner/') else route;bucket=hashlib.sha256(('customer:'+kind+':127.0.0.1').encode()).hexdigest();self.f.sql('INSERT INTO nd_limits(bucket,attempts,expires) VALUES (?,?,?)',params=[bucket,30,int(time.time())+900]);s=self.owner() if kind=='owner' else self.s
   self.assertEqual(self.post(route,self.payload(token='0'*64),s=s).status_code,429,route)
 def test_disable_reenable_and_stale_owner_update(self):
  self.register(True);self.login();a=self.account();owner=self.owner()
  r=self.post('owner/lifecycle',{'account_id':a['id'],'version':a['version'],'action':'disable'},s=owner);self.assertEqual(r.status_code,200,r.text)
  self.assertFalse(self.bootstrap(self.s)['authenticated']);self.assertEqual(self.post('login',{'email':a['email'],'password':'LongTestPassword123!'}).status_code,401)
  self.assertEqual(self.post('owner/lifecycle',{'account_id':a['id'],'version':a['version'],'action':'enable'},s=owner).status_code,409)
  self.assertEqual(self.post('owner/lifecycle',{'account_id':a['id'],'version':r.json()['version'],'action':'enable'},s=owner).status_code,200);self.login()
 def test_unverified_cannot_be_activated_by_lifecycle(self):
  self.register();a=self.account();self.assertEqual(self.post('owner/lifecycle',{'account_id':a['id'],'version':a['version'],'action':'enable'},s=self.owner()).status_code,422)
 def test_archived_customer_cannot_login(self):
  self.register(True);self.f.sql("UPDATE nd_customers SET status='archived'");self.assertEqual(self.post('login',{'email':'customer@example.invalid','password':'LongTestPassword123!'}).status_code,401)
 def test_legal_change_requires_new_explicit_consent(self):
  self.register(True);self.login();self.f.config['privacy_policy_version']='test-policy-v2';self.f.write_config();session=self.s.get(self.url('session')).json();self.assertFalse(session['authenticated']);self.assertTrue(session['needs_consent'])
  r=self.post('login',{'email':'customer@example.invalid','password':'LongTestPassword123!'});self.assertEqual(r.status_code,422)
  r=self.post('login',self.payload(policy_version='test-policy-v2'));self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_consents')[0]['n'],2)
 def test_mail_failure_does_not_claim_delivery_and_resend_recovers(self):
  self.smtp.reject=True;r=self.post('register',self.payload());self.assertEqual(r.status_code,202);self.assertEqual(len(self.smtp.messages),0)
  self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_customer_auth_events WHERE event='mail_failed'")[0]['n'],1)
  self.assertEqual(self.account()['status'],'invited');self.smtp.reject=False;self.post('resend',{'email':'customer@example.invalid'});_,token=self.link();self.assertEqual(self.post('verify',self.payload(token=token)).status_code,200)
 def test_non_test_insecure_smtp_is_rejected(self):
  self.f.config['customer_mail']['transport']='smtp';self.f.config['customer_mail']['encryption']='none';self.f.write_config()
  self.assertEqual(self.post('register',self.payload()).status_code,202);self.assertEqual(len(self.smtp.messages),0)
  self.f.config['customer_mail']['encryption']='none'
 def test_no_secrets_in_responses_or_php_logs(self):
  token=self.register();self.assertEqual(self.post('verify',self.payload(token='a'*64)).status_code,422)
  logs=(self.f.path/'server.log').read_text();self.assertNotIn(token,logs);self.assertNotIn('LongTestPassword123!',logs)
  old=self.f.config['db_name'];self.f.config['db_name']=old+'_missing';self.f.write_config()
  try:
   r=self.s.get(self.url('session'));self.assertEqual(r.status_code,503);self.assertNotIn(old,r.text);self.assertNotIn(str(self.f.path),r.text);self.assertNotIn('PDO',r.text)
  finally:self.f.config['db_name']=old;self.f.write_config()
 def test_missing_migration_disables_endpoints(self):
  self.f.sql("UPDATE nd_schema_migrations SET state='applying' WHERE version='005_customer_auth'")
  try:self.assertEqual(self.post('register',self.payload()).status_code,503)
  finally:self.f.sql("UPDATE nd_schema_migrations SET state='applied' WHERE version='005_customer_auth'")
 def test_browser_registration_verify_login_logout_mobile(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':390,'height':844});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(self.base+'/customer.php?view=register');page.locator('#auth-fields').wait_for(state='visible');page.wait_for_function("() => !document.querySelector('#auth-fields').disabled")
   self.assertFalse(page.locator('#customer-consent').is_checked());page.locator('#customer-name').fill('Мобильный клиент');page.locator('#customer-email').fill('customer@example.invalid');page.locator('#customer-password').fill('LongTestPassword123!');page.locator('#customer-repeat').fill('LongTestPassword123!');page.locator('#toggle-password').click();self.assertEqual(page.locator('#customer-password').get_attribute('type'),'text');page.locator('#customer-consent').check();page.locator('#customer-submit').click();page.wait_for_function("() => document.querySelector('#customer-message').textContent.includes('Если действие')")
   link,_=self.link('verify');page.goto(link);page.wait_for_function("() => !document.querySelector('#auth-fields').disabled");self.assertEqual(page.evaluate('location.hash'),'');page.locator('#customer-consent').check();page.locator('#customer-submit').click();page.wait_for_function("() => document.querySelector('#customer-message').textContent.includes('Email подтверждён')")
   page.goto(self.base+'/customer.php');page.wait_for_function("() => !document.querySelector('#auth-fields').disabled");page.locator('#customer-email').fill('customer@example.invalid');page.locator('#customer-password').fill('LongTestPassword123!');page.locator('#customer-submit').click();page.locator('#customer-home').wait_for(state='visible');self.assertIn('Мобильный клиент',page.locator('#customer-identity').inner_text());self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'),390)
   page.locator('#customer-logout').click();page.wait_for_function("() => document.querySelector('#customer-form') && !document.querySelector('#auth-fields').disabled");self.assertEqual(errors,[]);browser.close()
 def test_browser_preserves_input_on_unexpected_html_failure(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page();page.goto(self.base+'/customer.php?view=register');page.wait_for_function("() => !document.querySelector('#auth-fields').disabled")
   for id,value in [('customer-name','Keep draft'),('customer-email','keep@example.invalid'),('customer-password','LongTestPassword123!'),('customer-repeat','LongTestPassword123!')]:page.locator('#'+id).fill(value)
   page.locator('#customer-consent').check();page.route('**/customer-api.php?r=register',lambda r:r.fulfill(status=200,content_type='text/html',body='unrelated page'))
   page.locator('#customer-submit').click();page.wait_for_function("() => document.querySelector('#customer-message').textContent.includes('не удалось') || document.querySelector('#customer-message').textContent.includes('Не удалось')")
   self.assertEqual(page.locator('#customer-name').input_value(),'Keep draft');self.assertEqual(page.locator('#customer-password').input_value(),'LongTestPassword123!');self.assertFalse(page.locator('#customer-submit').is_disabled());browser.close()

 def test_parallel_token_consumption_has_exactly_one_winner(self):
  token=self.register()
  code="require $v['root'].'/private/app.php';require $v['root'].'/private/customer-auth.php';try{ca_consume($v['data'],'verify',null,privacy_settings());echo 'ok';}catch(CustomerFailure $e){echo $e->errorCode;}"
  values={'root':str(self.f.path),'data':self.payload(token=token)}
  with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.f.php_eval(code,values),range(2)))
  self.assertEqual(sorted(results),['invalid_token','ok'])
 def test_verification_legal_change_requires_current_checkbox(self):
  token=self.register();self.f.config['privacy_policy_version']='test-policy-v2';self.f.write_config()
  self.assertEqual(self.post('verify',self.payload(token=token)).status_code,409)
  self.assertEqual(self.post('verify',self.payload(token=token,policy_version='test-policy-v2',consent=False)).status_code,422)
  self.assertEqual(self.post('verify',self.payload(token=token,policy_version='test-policy-v2')).status_code,200)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_consents')[0]['n'],2)
 def test_secure_cookie_flags_and_https_only_outside_test(self):
  original=self.f.config['app_url'];self.f.config['app_url']='https://neurodelo.pro';self.f.write_config()
  try:
   r=requests.get(self.url('session'));self.assertEqual(r.status_code,200);cookie=r.headers['Set-Cookie'];self.assertIn('__Host-nd_customer=',cookie);self.assertIn('secure',cookie.lower());self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie);self.assertIn('path=/',cookie.lower());self.assertNotIn('domain=',cookie.lower())
  finally:self.f.config['app_url']=original;self.f.config['customer_auth_test_mode']=False;self.f.write_config()
  try:self.assertFalse(requests.get(self.url('settings')).json()['enabled'])
  finally:self.f.config['customer_auth_test_mode']=True;self.f.write_config()
 def test_browser_owner_invitation_controls(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(self.base+'/studio.php');page.locator('#password').fill(self.f.password);page.locator('#login-form button').click();page.locator('#customer-management').wait_for(state='visible');page.locator('#customer-management summary').click()
   page.locator('#invite-name').fill('Приглашённый клиент');page.locator('#invite-email').fill('browser-invite@example.invalid');page.locator('#customer-invite-form button').click();page.wait_for_function("() => document.querySelector('#customer-accounts').textContent.includes('browser-invite@example.invalid')")
   self.link('invite');page.locator('#logout').click();page.locator('#login-panel').wait_for(state='visible');self.assertEqual(page.locator('#customer-accounts').inner_text(),'');self.assertEqual(errors,[]);browser.close()

 def test_smtp_transient_failure_retries_without_duplicate_account(self):
  self.smtp.reject_once=1;self.register();self.assertEqual(len(self.smtp.messages),1);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_accounts')[0]['n'],1)
  self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_customer_auth_events WHERE event='mail_accepted'")[0]['n'],1)

if __name__=='__main__':unittest.main()
