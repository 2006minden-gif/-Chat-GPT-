"""First owner provisioning in a disposable loopback database; no live credentials."""
import concurrent.futures
import hashlib
import json
import secrets
import time
from pathlib import Path
import requests
import test_prelaunch as fixture

class OwnerBootstrap(fixture.Prelaunch):
 def setUp(self):
  self.sql('DELETE FROM nd_admin');self.sql('DELETE FROM nd_limits')
  self.token=secrets.token_hex(32)
  self.grant=self.path/'private/owner-bootstrap.json'
  self.grant.write_text(json.dumps({'enabled':True,'expires_at':int(time.time())+3600,'token_sha256':hashlib.sha256(self.token.encode()).hexdigest()}))
 def payload(self,**changes):
  return {'token':self.token,'password':'Synthetic-passphrase-123','repeat':'Synthetic-passphrase-123',**changes}
 def setup_post(self,**changes):
  return requests.post(self.base+'/owner-setup.php',json=self.payload(**changes),headers={'Origin':self.base})
 def test_invalid_and_expired_capability_never_create_owner(self):
  for token in ['', 'a'*64, self.token+'a',None]:self.assertEqual(self.setup_post(token=token).status_code,403)
  self.grant.write_text(json.dumps({'enabled':True,'expires_at':int(time.time())-1,'token_sha256':hashlib.sha256(self.token.encode()).hexdigest()}))
  self.assertEqual(self.setup_post().status_code,403)
  self.grant.write_text('{bad json');self.assertEqual(self.setup_post().status_code,403)
  self.assertEqual(self.sql('SELECT id FROM nd_admin'),[])
 def test_create_login_and_replay_cannot_replace_password(self):
  page=requests.get(self.base+'/owner-setup.php');self.assertEqual(page.status_code,200)
  self.assertIn('no-store',page.headers['Cache-Control']);self.assertIn('noindex',page.headers['X-Robots-Tag'])
  self.assertNotIn(self.token,page.text)
  for value in ['short','я'*37]:self.assertEqual(self.setup_post(password=value,repeat=value).status_code,422)
  self.assertEqual(self.setup_post(repeat='different').status_code,422)
  cross=requests.post(self.base+'/owner-setup.php',json=self.payload(),headers={'Origin':'https://evil.invalid'})
  self.assertEqual(cross.status_code,403)
  self.assertEqual(requests.post(self.base+'/owner-setup.php',data=self.payload()).status_code,415)
  result=self.setup_post();self.assertEqual(result.status_code,201,result.text)
  original=self.sql('SELECT password_hash FROM nd_admin WHERE id=1')[0]['password_hash']
  self.assertNotEqual(original,'Synthetic-passphrase-123')
  self.assertEqual(self.setup_post(password='Replacement-passphrase',repeat='Replacement-passphrase').status_code,409)
  self.assertEqual(self.sql('SELECT password_hash FROM nd_admin WHERE id=1')[0]['password_hash'],original)
  session=requests.Session();login=session.post(self.api('login'),json={'password':'Synthetic-passphrase-123'})
  self.assertEqual(login.status_code,200);self.assertIn('HttpOnly',login.headers['Set-Cookie'])
  self.assertEqual(session.get(self.api('session')).status_code,200)
  self.assertEqual(requests.get(self.api('leads')).status_code,401)
 def test_concurrent_claim_only_one_owner(self):
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   results=list(pool.map(lambda _:self.setup_post(),range(2)))
  self.assertEqual(sorted(r.status_code for r in results),[201,409])
  self.assertEqual(len(self.sql('SELECT id FROM nd_admin')),1)
 def test_browser_fragment_removed_and_password_stays_private(self):
  from playwright.sync_api import sync_playwright
  import os
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   try:
    page=browser.new_page(viewport={'width':375,'height':812});urls=[]
    page.on('request',lambda request:urls.append(request.url))
    page.goto(self.base+'/owner-setup.php#token='+self.token)
    self.assertTrue(page.locator('#owner-setup-form').is_visible());self.assertNotIn(self.token,page.url)
    page.locator('#owner-password').fill('Synthetic-passphrase-123');page.locator('#owner-repeat').fill('Synthetic-passphrase-123')
    page.locator('#owner-setup-form button').click();page.wait_for_url('**/studio.php')
    page.locator('#password').fill('Synthetic-passphrase-123');page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
    self.assertFalse(any(self.token in url or 'Synthetic-passphrase' in url for url in urls))
    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   finally:browser.close()

# Reuse fixture infrastructure, not unrelated inherited test execution.
for name in vars(fixture.Prelaunch):
 if name.startswith('test_') and name not in vars(OwnerBootstrap):setattr(OwnerBootstrap,name,None)
