"""The deployed one-owner preparation mode cannot bypass agreement gates."""
import unittest,secrets
import test_crm_operations as crm

class SingleOwner(unittest.TestCase):
 setUpClass=classmethod(crm.CrmOperations.setUpClass.__func__)
 setUp=crm.CrmOperations.setUp
 url=crm.CrmOperations.url
 get=crm.CrmOperations.get
 post=crm.CrmOperations.post
 patch=crm.CrmOperations.patch
 create=crm.CrmOperations.create
 def test_owner_only_preparation_and_mandatory_document_gate(self):
  self.f.config.update(single_owner_mode=True,lifecycle_document_gate_ready=False);self.f.write_config()
  settings=self.get('settings').json();self.assertTrue(settings['single_owner']);self.assertNotIn('employees',settings['models'])
  for fields in settings['models'].values():self.assertFalse(set(fields)&{'owner_employee_id','manager_employee_id','assignee_employee_id'})
  self.assertEqual(self.get('employees').status_code,404)
  self.assertEqual(self.post('employees',name='Forbidden',email='test@example.invalid',request_key=secrets.token_hex(32)).status_code,404)
  customer=self.create('customers',name='SYNTHETIC lifecycle',email='test@example.invalid')
  order=self.create('orders',customer_id=int(customer['id']),title='SYNTHETIC draft',total_amount='100.00',currency='RUB')
  blocked=self.patch('orders/'+str(order['id']),version=int(order['version']),status='confirmed');self.assertEqual(blocked.status_code,409,blocked.text)
  project=self.create('projects',customer_id=int(customer['id']),order_id=int(order['id']),title='SYNTHETIC project',description='Требования для ручной оценки без вызова ИИ-провайдера.')
  self.assertEqual(self.patch('projects/'+str(project['id']),version=int(project['version']),status='active').status_code,409)
  self.assertEqual(self.post('projects/'+str(project['id'])+'/members',version=int(project['version']),employee_id=1).status_code,404)
  self.assertNotIn('members',self.get('projects/'+str(project['id'])).json()['related'])
  self.assertEqual(self.post('tasks',request_key=secrets.token_hex(32),title='Forbidden assignment',assignee_employee_id=1).status_code,422)
  # Security is enforced at the API, not just by hiding selectors.
  direct=self.post('orders',request_key=secrets.token_hex(32),customer_id=int(customer['id']),title='Bypass',total_amount='1.00',status='completed');self.assertEqual(direct.status_code,422)

 def test_production_release_flags_never_enable_client_or_paid_services(self):
  import json
  code='require $v["path"]."/private/release-features.php";echo json_encode(nd_release_config(["app_url"=>"https://neurodelo.pro","customer_auth_enabled"=>true,"billing_enabled"=>true,"ai_enabled"=>true]));'
  c=json.loads(self.f.php_eval(code,{'path':str(self.f.path)}))
  for name in ['customer_auth_enabled','catalog_requests_enabled','billing_enabled','ai_enabled','production_enabled','lifecycle_document_gate_ready']:self.assertFalse(c[name])
  self.assertTrue(c['single_owner_mode'])
