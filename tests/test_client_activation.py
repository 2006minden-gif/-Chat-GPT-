"""Owner-approved scoped privacy + actual loopback SMTP challenge. No production mail."""
import base64,json,re,shutil,secrets,os
import requests
import test_customer_auth as auth

class ClientActivation(auth.CustomerAuth):
 def setUp(self):
  self.f.config['customer_settings_test_mode']=False;self.f.write_config();super().setUp();self.owner_session=self.owner();runtime=self.f.path/'private/runtime'
  if runtime.exists():shutil.rmtree(runtime)
  self.f.config['customer_settings_test_mode']=True;self.f.write_config()
 def settings(self):return self.owner_session.get(self.base+'/api.php?r=owner/customer-settings')
 def change(self,route,**d):
  d.setdefault('version',self.settings().json()['version']);return self.owner_session.post(self.base+'/api.php?r=owner/customer-settings/'+route,json=d)
 def draft(self):
  r=self.change('policy/draft',operator_name='SYNTHETIC operator',operator_address='SYNTHETIC test address',contact='SYNTHETIC owner contact',legal_basis='SYNTHETIC test-only basis, not a production legal decision',retention='SYNTHETIC test duration, no real personal data',processors='SYNTHETIC local SMTP fixture only');self.assertEqual(r.status_code,200,r.text);return r.json()['policy']
 def approve_policy(self):
  p=self.draft();r=self.change('policy/approve',hash=p['hash'],confirm_reviewed=True,reason='SYNTHETIC owner legal review in isolated tests only');self.assertEqual(r.status_code,200,r.text);return p
 def probe(self):
  r=self.change('mail/probe',**{'from':'owner@example.invalid','recipient':'owner@example.invalid','password':'SyntheticPrivateSmtpPassword!'});self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['inbox_confirmation_pending']);self.assertFalse(r.json()['mail_verified']);self.assertNotIn('SyntheticPrivateSmtpPassword',r.text);self.assertNotIn('probe_hash',r.text)
  message=self.smtp.messages[-1][1];body=base64.b64decode(message.split(b'\r\n\r\n',1)[1]).decode();code=re.search(r'Код: ([0-9]{6})',body).group(1);self.assertNotIn(code,r.text);return code
 def open(self):
  p=self.approve_policy();self.assertEqual(self.change('enable-preparation',confirm=True).status_code,200);code=self.probe();r=self.change('mail/confirm',code=code);self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['mail_verified']);r=self.change('open',confirm=True);self.assertEqual(r.status_code,200,r.text);return p
 def test_activation_01_explicit_policy_and_received_mail_code_required(self):
  self.assertFalse(requests.get(self.url('settings')).json()['enabled']);self.assertEqual(self.change('open',confirm=True).status_code,422);p=self.draft();self.assertEqual(requests.get(self.base+'/customer-privacy.php?version='+p['version']).status_code,503);self.assertEqual(self.change('policy/approve',hash='0'*64,confirm_reviewed=True,reason='SYNTHETIC').status_code,422);self.assertFalse(requests.get(self.url('settings')).json()['enabled'])
  r=self.change('policy/approve',hash=p['hash'],confirm_reviewed=True,reason='SYNTHETIC explicit review');self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.change('enable-preparation',confirm=True).status_code,200);self.assertEqual(self.change('open',confirm=True).status_code,422);code=self.probe();self.assertEqual(self.change('mail/confirm',code='000000').status_code,200);self.assertFalse(self.settings().json()['mail_verified']);self.assertEqual(self.change('open',confirm=True).status_code,422);self.assertEqual(self.change('mail/confirm',code=code).status_code,200);self.assertEqual(self.change('open',confirm=True).status_code,200);self.assertTrue(requests.get(self.url('settings')).json()['enabled'])
  self.assertEqual((self.f.path/'private/runtime/customer-settings.json').stat().st_mode&0o777,0o600);self.assertNotIn('SyntheticPrivateSmtpPassword',self.settings().text)
 def test_activation_02_scoped_policy_does_not_open_public_registration(self):
  p=self.open();s=requests.Session();r=s.get(self.url('session'));s.headers['X-CSRF-Token']=r.json()['csrf'];r=self.post('register',self.payload(policy_version=p['version']),s);self.assertEqual(r.status_code,403,r.text);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_accounts')[0]['n'],0)
  self.assertFalse(requests.get(self.url('settings')).json()['registration_enabled']);self.assertEqual(requests.get(self.base+'/api.php?r=privacy').json()['version'],'test-policy-v1')
  self.assertEqual(requests.get(self.base+'/customer-privacy.php?version='+p['version']).status_code,200);self.assertIn('Отдельное согласие',requests.get(self.base+'/customer-privacy.php?document=consent&version='+p['version']).text)
 def test_activation_04_opt_in_and_audit_failure_preserve_closed_access(self):
  self.assertEqual(self.change('notifications',confirm=True,email_notifications_enabled=True).status_code,422)
  self.approve_policy();self.assertEqual(self.change('notifications',confirm=True,email_notifications_enabled=True).status_code,422)
  code=self.probe();self.assertEqual(self.change('mail/confirm',code=code).status_code,200)
  # Existing auth fixture has no billing queue migration: channel activation must fail closed.
  self.assertEqual(self.change('notifications',confirm=True,email_notifications_enabled=True).status_code,503)
  audit=self.f.path/'private/runtime/customer-settings-audit.jsonl';audit.write_text(audit.read_text()+'SYNTHETIC partial write')
  before=self.settings().json()['version'];self.assertEqual(self.change('enable-preparation',confirm=True).status_code,503)
  self.assertEqual(self.settings().json()['version'],before);self.assertFalse(self.settings().json()['prep_enabled']);self.assertFalse(requests.get(self.url('settings')).json()['enabled'])
 def test_activation_03_owner_only_csrf_stale_updates_no_secret_leak_and_mobile(self):
  self.assertEqual(requests.get(self.base+'/api.php?r=owner/customer-settings').status_code,401);csrf=self.owner_session.headers.pop('X-CSRF-Token')
  try:self.assertEqual(self.change('open',confirm=True).status_code,403)
  finally:self.owner_session.headers['X-CSRF-Token']=csrf
  p=self.approve_policy();self.assertEqual(self.change('enable-preparation',version=0,confirm=True).status_code,409)
  from playwright.sync_api import sync_playwright
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':375,'height':812});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(self.base+'/studio.php');page.locator('#password').fill(self.f.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible');page.goto(self.base+'/client-settings.php');page.get_by_text('Проверить почту SpaceWeb',exact=True).wait_for();self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);browser.close()

for name in dir(auth.CustomerAuth):
 if name.startswith('test_'):setattr(ClientActivation,name,None)
