"""Workflow MAX events: existing owner connection, injected transport, no PII/token output."""
import json,subprocess
import test_max_notifications as max_tests

class WorkflowMax(max_tests.MaxNotifications):
 @classmethod
 def setUpClass(cls):
  super().setUpClass()
  for name in ['migrate.php','migrate-customer.php','migrate-crm.php']:
   r=subprocess.run([cls.php,str(cls.path/'scripts'/name),'up'],capture_output=True,text=True)
   if r.returncode:raise RuntimeError('Synthetic migration setup failed')
  cls.config['max_workflow_notifications_enabled']=True;cls.write_config()
 def setUp(self):
  super().setUp();self.sql('DELETE FROM nd_crm_notifications')
 def test_workflow_ids_are_separate_and_late_lower_commits_are_not_lost(self):
  self.bind();self.sql("INSERT INTO nd_crm_notifications(id,event_key,entity,record_id,message) VALUES (10020,'lc-flow:201:1','orders',201,'PRIVATE_NAME PRIVATE_CONTACT PRIVATE_BODY')")
  result=self.run_php('echo json_encode(max_pump(10,$mock));');self.assertEqual(result['sent'],1);self.assertEqual(self.state()['completed_workflow_ids'],[10020]);self.assertNotIn(10020,self.state()['completed_ids'])
  self.sql("INSERT INTO nd_crm_notifications(id,event_key,entity,record_id,message) VALUES (10019,'lc-claim:101','orders',201,'PRIVATE_LATE_BODY')")
  self.assertEqual(self.run_php('echo json_encode(max_pump(10,$mock));')['sent'],1);self.assertEqual(self.run_php('echo json_encode(max_pump(10,$mock));')['sent'],0)
  calls=json.loads((self.path/'max-calls.json').read_text());text=json.dumps(calls,ensure_ascii=False)
  for marker in ['PRIVATE_NAME','PRIVATE_CONTACT','PRIVATE_BODY','PRIVATE_LATE_BODY','SYNTHETIC_NOT_A_REAL_TOKEN']:self.assertNotIn(marker,text)
  self.assertIn('10019',text);self.assertIn('/orders.php?mode=owner#201',text)
 def test_failed_workflow_message_is_retryable_without_confirmed_ack(self):
  self.bind();self.sql("INSERT INTO nd_crm_notifications(event_key,entity,record_id,message) VALUES ('lc-receipt:1','orders',1,'PRIVATE_BANK_DETAILS')")
  self.assertEqual(self.run_php('echo json_encode(max_pump(10,$mock));',broken=True)['sent'],0);self.assertEqual(self.state().get('completed_workflow_ids',[]),[])
  self.run_php('max_locked(function(){$s=max_read();unset($s["retry_at"]);max_write($s);});echo "{}";')
  self.assertEqual(self.run_php('echo json_encode(max_pump(10,$mock));')['sent'],1);self.assertEqual(self.run_php('echo json_encode(max_pump(10,$mock));')['sent'],0)

for name in dir(max_tests.MaxNotifications):
 if name.startswith('test_'):setattr(WorkflowMax,name,None)
