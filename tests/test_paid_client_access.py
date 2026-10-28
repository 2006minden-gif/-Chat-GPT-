"""Paid invitation, real loopback inbox receipt, no real bank/FNS activity."""
import base64,re,threading,secrets,requests
import test_order_lifecycle as orders
from test_customer_auth import SMTPServer,SMTPHandler

class PaidClientAccess(orders.OrderLifecycle):
 def setUp(self):
  super().setUp();self.smtp=SMTPServer(('127.0.0.1',0),SMTPHandler);self.smtp.messages=[];self.smtp.reject=False;self.smtp.reject_once=0;threading.Thread(target=self.smtp.serve_forever,daemon=True).start();self.addCleanup(self.smtp.server_close);self.addCleanup(self.smtp.shutdown)
  self.f.config.update(customer_registration_enabled=False,paid_client_invitation_required=True,customer_mail_verified=True,customer_mail={'transport':'test-smtp','host':'127.0.0.1','port':self.smtp.server_address[1],'from':'owner@example.invalid','encryption':'none'});self.f.write_config()
 def invite(self,oid,email=None):return self.owner.post(self.base+'/customer-api.php?r=owner/invite',json={'customer_id':self.customer_id,'order_id':oid,'email':email or self.invite_email})
 def token(self):
  body=base64.b64decode(self.smtp.messages[-1][1].split(b'\r\n\r\n',1)[1]).decode();return re.search(r'#token=([a-f0-9]{64})',body).group(1)
 def activate_invite(self,token,s=None):
  s=s or requests.Session();r=s.get(self.base+'/customer-api.php?r=session');s.headers['X-CSRF-Token']=r.json()['csrf'];return s,s.post(self.base+'/customer-api.php?r=invite',json={'token':token,'password':'SYNTHETIC-secret12345','password_confirmation':'SYNTHETIC-secret12345','consent':True,'policy_version':'test-policy-v1'})
 def test_paid_only_single_use_expiry_duplicate_bank_and_existing_login_without_smtp(self):
  oid,items=self.flow_ready();self.invite_email='paid-'+secrets.token_hex(4)+'@example.invalid';self.assertEqual(self.invite(oid).status_code,409)
  bankdata={'bank_entry_id':'SYNTHETIC-'+secrets.token_hex(16)};r=self.bank(items[0],**bankdata);self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.bank(items[0],**bankdata).status_code,409);r=self.invite(oid);self.assertEqual(r.status_code,200,r.text);self.assertTrue(r.json()['smtp_accepted']);self.assertFalse(r.json()['delivery_confirmed']);self.assertEqual(len(self.smtp.messages),1);token=self.token()
  self.f.sql("UPDATE nd_customer_tokens SET expires_at=0 WHERE token_hash=SHA2(?,256)",params=[token]);_,r=self.activate_invite(token);self.assertEqual(r.status_code,422)
  self.assertEqual(self.invite(oid).status_code,200);new=self.token();self.assertNotEqual(new,token);s,r=self.activate_invite(new);self.assertEqual(r.status_code,200,r.text);_,again=self.activate_invite(new);self.assertEqual(again.status_code,422)
  self.f.config['customer_mail_verified']=False;self.f.write_config();r=s.post(self.base+'/customer-api.php?r=login',json={'email':self.invite_email,'password':'SYNTHETIC-secret12345'});self.assertEqual(r.status_code,200,r.text);s.headers['X-CSRF-Token']=r.json()['csrf'];self.assertEqual(s.get(self.base+'/lifecycle-api.php?r=flow/orders/'+str(oid)).status_code,200);self.assertEqual(self.invite(oid).status_code,503)
  self.assertEqual(requests.get(self.base+'/lifecycle-api.php?r=flow/orders/'+str(oid)).status_code,401);self.assertEqual(self.fg(oid,self.stranger).status_code,404)
 def test_no_public_registration_and_failed_smtp_revokes_token(self):
  oid,items=self.flow_ready();self.invite_email='failed-'+secrets.token_hex(4)+'@example.invalid';self.assertEqual(self.bank(items[0]).status_code,200)
  self.smtp.reject=True;r=self.invite(oid);self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['smtp_accepted']);self.assertTrue(r.json()['retry_needed']);self.assertFalse(r.json()['delivery_confirmed']);self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_customer_tokens t JOIN nd_customer_accounts a ON a.id=t.account_id WHERE a.email=? AND t.used_at IS NULL",params=[self.invite_email])[0]['n'],0)
  self.smtp.reject=False;self.assertEqual(self.invite(oid).status_code,200);self.assertEqual(len(self.smtp.messages),1)
  s=requests.Session();r=s.get(self.base+'/customer-api.php?r=session');s.headers['X-CSRF-Token']=r.json()['csrf'];r=s.post(self.base+'/customer-api.php?r=register',json={'email':'no-self@example.invalid'});self.assertEqual(r.status_code,403)

for name in dir(orders.OrderLifecycle):
 if name.startswith('test_'):setattr(PaidClientAccess,name,None)
