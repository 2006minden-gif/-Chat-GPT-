"""Stage 5: isolated MySQL 5.7 / PHP HTTP tests; never production writes."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import unittest
import requests
import test_prelaunch as fixture

class CrmOperations(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class F(fixture.Prelaunch):pass
  cls.f=F;F.setUpClass();cls.addClassCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php','migrate-crm.php']:
   p=subprocess.run([F.php,str(F.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if p.returncode:raise RuntimeError(p.stderr)
  F.config['crm_operations_enabled']=True;F.write_config();cls.base=F.base
 def setUp(self):
  self.f.sql('DELETE FROM nd_limits');self.s=requests.Session()
  r=self.s.post(self.base+'/api.php?r=login',json={'password':self.f.password});self.assertEqual(r.status_code,200,r.text);self.s.headers['X-CSRF-Token']=r.json()['csrf']
 def url(self,r):return self.base+'/api.php?r=crm/'+r
 def get(self,r,**params):return self.s.get(self.url(r),params=params)
 def post(self,r,**d):return self.s.post(self.url(r),json=d)
 def patch(self,r,**d):return self.s.patch(self.url(r),json=d)
 def create(self,kind,**d):
  d.setdefault('request_key',secrets.token_hex(32));r=self.s.post(self.url(kind),json=d);self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def test_01_dashboard_auth_gate_and_real_counts(self):
  self.assertEqual(requests.get(self.url('dashboard')).status_code,401)
  self.f.config['crm_operations_enabled']=False;self.f.write_config()
  try:self.assertEqual(self.get('dashboard').status_code,503)
  finally:self.f.config['crm_operations_enabled']=True;self.f.write_config()
  r=self.get('dashboard');self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(r.json()['kpi']['projects'],int(self.f.sql("SELECT COUNT(*) n FROM nd_projects WHERE archived_at IS NULL AND status NOT IN ('completed','cancelled')")[0]['n']))
  self.assertEqual(self.post('notifications/sync').status_code,200)
  self.assertEqual(self.get('notifications').status_code,200)
  no_csrf=requests.Session();no_csrf.cookies.update(self.s.cookies)
  self.assertEqual(no_csrf.post(self.url('notifications/sync'),json={}).status_code,403)
 def customer(self,**d):return self.create('customers',name='Клиент '+secrets.token_hex(3),email='synthetic@example.invalid',**d)
 def test_02_customer_lifecycle_and_lead_ownership(self):
  a=self.customer();b=self.customer();lead=self.s.post(self.base+'/api.php?r=leads',json={'name':'Исходная заявка','contact':'lead@example.invalid','service':'ИИ-агент','idea':'Синтетический тест','consent':True,'policy_version':'test-policy-v1','idempotency_key':secrets.token_hex(32)}).json()['lead_id']
  first=self.patch('customers/'+str(a['id']),version=1,phone='+79991234567');self.assertEqual(first.status_code,200,first.text)
  self.assertEqual(self.patch('customers/'+str(a['id']),version=1,name='Устаревшее изменение').status_code,409)
  linked=self.post('customers/'+str(a['id'])+'/link',version=2,lead_id=lead);self.assertEqual(linked.status_code,200,linked.text)
  self.assertEqual(self.post('customers/'+str(b['id'])+'/link',version=1,lead_id=lead).status_code,409)
  detail=self.get('customers/'+str(a['id'])).json();self.assertEqual(detail['related']['leads']['items'][0]['id'],lead)
  self.assertGreaterEqual(len(detail['related']['history']),3)
  self.assertEqual(self.f.sql('SELECT name FROM nd_leads WHERE id=?',params=[lead])[0]['name'],'Исходная заявка')
  ar=self.post('customers/'+str(a['id'])+'/archive',version=3);self.assertEqual(ar.status_code,200,ar.text)
  self.assertEqual(self.post('customers/'+str(a['id'])+'/restore',version=4).status_code,200)
  self.assertGreaterEqual(len(self.get('customers',search='Клиент').json()['items']),2)
  for data in [{'email':'bad@'}, {'phone':'+12025550123'},{'telegram':'@abc'}]:self.assertEqual(self.patch('customers/'+str(a['id']),version=5,**data).status_code,422)
 def test_03_deals_transitions_idempotent_explicit_conversion(self):
  a=self.customer();d=self.create('deals',customer_id=int(a['id']),title='Разработка',estimated_amount='123.45',currency='RUB')
  self.assertEqual(self.patch('deals/'+str(d['id']),version=1,status='won').status_code,422)
  for version,status in enumerate(['qualified','proposal','won'],1):
   r=self.patch('deals/'+str(d['id']),version=version,status=status);self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_orders WHERE deal_id=?',params=[d['id']])[0]['n'],0)
  key=secrets.token_hex(32);payload={'version':4,'confirm':True,'request_key':key}
  r=self.post('deals/'+str(d['id'])+'/convert',**payload);self.assertEqual(r.status_code,200,r.text);oid=r.json()['record']['id']
  self.assertEqual(self.post('deals/'+str(d['id'])+'/convert',**payload).json()['record']['id'],oid)
  payload['request_key']=secrets.token_hex(32);self.assertEqual(self.post('deals/'+str(d['id'])+'/convert',**payload).json()['record']['id'],oid)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_orders WHERE deal_id=?',params=[d['id']])[0]['n'],1)
  for amount in ['1e3','-1','NaN','0.001',12.4]:self.assertEqual(self.post('deals',request_key=secrets.token_hex(32),customer_id=int(a['id']),title='Недопустимая сумма',estimated_amount=amount).status_code,422)
  self.assertEqual(self.get('orders/'+str(oid)).json()['record']['total_amount'],'123.45')
 def test_04_orders_projects_stages_tasks_relationships(self):
  a=self.customer();b=self.customer();o=self.create('orders',customer_id=int(a['id']),title='Сайт',total_amount='500.00')
  self.assertEqual(self.post('projects',request_key=secrets.token_hex(32),customer_id=int(b['id']),order_id=int(o['id']),title='Чужой заказ').status_code,422)
  p=self.create('projects',customer_id=int(a['id']),order_id=int(o['id']),title='Рабочий проект',due_on='2030-01-01');pid=p['id']
  self.assertIsNone(self.get('projects/'+str(pid)).json()['record']['progress']['percent'])
  stage=self.create('stages',project_id=int(pid),title='Разработка',position=1)
  employee=self.create('employees',name='Сотрудник',email=secrets.token_hex(8)+'@example.invalid',position='Разработчик')
  r=self.patch('employees/'+str(employee['id']),version=1,status='active');self.assertEqual(r.status_code,200,r.text)
  task=self.create('tasks',title='Сделать',project_id=int(pid),stage_id=int(stage['id']),assignee_employee_id=int(employee['id']),due_at='2020-01-01 00:00:00',priority='high')
  other=self.create('projects',title='Другой',customer_id=int(a['id']))
  self.assertEqual(self.post('tasks',request_key=secrets.token_hex(32),title='Чужой этап',project_id=int(other['id']),stage_id=int(stage['id'])).status_code,422)
  for version,status in enumerate(['active','completed'],1):self.assertEqual(self.patch('stages/'+str(stage['id']),version=version,status=status).status_code,200)
  self.assertEqual(self.get('projects/'+str(pid)).json()['record']['progress']['percent'],100)
  current=self.get('projects/'+str(pid)).json()['record'];self.assertEqual(self.post('projects/'+str(pid)+'/members',version=int(current['version']),employee_id=int(employee['id'])).status_code,200)
  current=self.get('projects/'+str(pid)).json()['record'];self.assertEqual(self.post('projects/'+str(pid)+'/reorder',version=int(current['version']),stage_ids=[int(stage['id'])]).status_code,200)
  for version,status in enumerate(['in_progress','done'],1):self.assertEqual(self.patch('tasks/'+str(task['id']),version=version,status=status).status_code,200)
  for status in ['active','completed']:
   current=self.get('projects/'+str(pid)).json()['record'];r=self.patch('projects/'+str(pid),version=int(current['version']),status=status);self.assertEqual(r.status_code,200,r.text)
  self.assertIsNotNone(self.get('projects/'+str(pid)).json()['record']['completed_at'])
  self.assertEqual(self.get('employees/'+str(employee['id'])).json()['related']['tasks']['total'],1)
 def test_05_notifications_and_security(self):
  a=self.customer();d=self.create('deals',customer_id=int(a['id']),title='<script>alert(1)</script>')
  self.assertEqual(self.post('notifications/sync').status_code,200);n=self.get('notifications').json()['total'];self.assertEqual(self.post('notifications/sync').status_code,200);self.assertEqual(self.get('notifications').json()['total'],n)
  self.assertEqual(self.post('notifications/all/read').status_code,200);self.assertEqual(self.get('notifications',unread='true').json()['total'],0)
  self.assertEqual(self.get('customers',search="' OR 1=1 --").json()['total'],0)
  no=requests.Session();no.cookies.update(self.s.cookies);self.assertEqual(no.patch(self.url('deals/'+str(d['id'])),json={'version':1,'title':'X'}).status_code,403)
  self.assertEqual(self.s.patch(self.url('deals/'+str(d['id'])),headers={'Origin':'https://attacker.invalid'},json={'version':1,'title':'X'}).status_code,403)
  self.assertEqual(self.get('customers/99999999').status_code,404)
  self.assertNotIn('request_hash',self.get('activity').text)
 def test_06_creation_retries_do_not_merge_customers(self):
  key=secrets.token_hex(32);data={'request_key':key,'name':'Дубликат имени допустим','email':'same@example.invalid'}
  a=self.post('customers',**data);b=self.post('customers',**data);self.assertEqual(a.status_code,200,a.text);self.assertEqual(a.json()['record']['id'],b.json()['record']['id'])
  data['name']='Иное содержимое';self.assertEqual(self.post('customers',**data).status_code,409)
  data['request_key']=secrets.token_hex(32);self.assertNotEqual(self.post('customers',**data).json()['record']['id'],a.json()['record']['id'])
