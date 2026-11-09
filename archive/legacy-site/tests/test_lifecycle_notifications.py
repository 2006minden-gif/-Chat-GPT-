"""Actual bounded worker -> loopback SMTP; no provider/bank invocation."""
import json,subprocess,threading,email
import test_billing as billing

class LifecycleNotifications(billing.Billing):
 def test_lifecycle_email_worker_uses_available_portal_and_no_private_body(self):
  from test_customer_auth import SMTPServer,SMTPHandler
  smtp=SMTPServer(('127.0.0.1',0),SMTPHandler);smtp.messages=[];smtp.reject=False;smtp.reject_once=0;threading.Thread(target=smtp.serve_forever,daemon=True).start();self.addCleanup(smtp.server_close);self.addCleanup(smtp.shutdown)
  original=dict(self.f.config)
  try:
   self.f.config.update(billing_enabled=False,billing_email_enabled=True,billing_owner_email='owner@example.invalid',customer_mail={'transport':'test-smtp','host':'127.0.0.1','port':smtp.server_address[1],'from':'noreply@example.invalid','encryption':'none'});self.f.write_config()
   self.f.php_eval('require $v["root"]."/private/app.php";require $v["root"]."/private/billing/core.php";require $v["root"]."/private/billing/notifications.php";bill_emit("lc-milestone:synthetic:1","new_deliverable","orders",$v["order"],null);',{'root':str(self.f.path),'order':self.order})
   r=subprocess.run([self.f.php,str(self.f.path/'private/notifications/worker.php')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);result=json.loads(r.stdout);self.assertEqual(result['email_evidence'],'smtp_acceptance_only');self.assertEqual(result['email_jobs_processed'],1);self.assertEqual(len(smtp.messages),1)
   msg=email.message_from_bytes(smtp.messages[0][1]);texts=[p.get_payload(decode=True).decode() for p in msg.walk() if not p.is_multipart()]
   for text in texts:self.assertIn('/orders.php?mode=owner#'+str(self.order),text);self.assertNotIn('/billing.php',text)
   rows=self.f.sql("SELECT channel,state FROM nd_notification_outbox WHERE event_key='lc-milestone:synthetic:1'");self.assertEqual(len(rows),2);self.assertTrue(all(x['state']=='delivered' for x in rows))
   r=subprocess.run([self.f.php,str(self.f.path/'private/notifications/worker.php')],capture_output=True,text=True);self.assertEqual(json.loads(r.stdout)['email_jobs_processed'],0);self.assertEqual(len(smtp.messages),1)
  finally:self.f.config=original;self.f.write_config()

for name in dir(billing.Billing):
 if name.startswith('test_'):setattr(LifecycleNotifications,name,None)
