"""Single-owner capacity, real CRM dependencies, unknown estimates and immutable commercial dates."""
import json,secrets,subprocess,requests
import test_manual_qr as qr
class OwnerPlanning(qr.ManualQr):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-planning.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
 def pa(self,r,d=None):
  u=self.base+'/planning-api.php?r='+r
  if d is None:return self.owner.get(u)
  d.setdefault('request_key',secrets.token_hex(32));return self.owner.post(u,json=d)
 def test_capacity_dependencies_cycle_holidays_staleness_and_protected_term_source(self):
  self.assertEqual(requests.get(self.base+'/planning-api.php?r=state').status_code,401)
  for t in ['nd_workload_plans','nd_task_planning','nd_work_calendars']:self.f.sql('DELETE FROM '+t)
  oid=int(self.must(self.owner.post(self.base+'/api.php?r=crm/orders',json={'request_key':secrets.token_hex(32),'customer_id':self.customer_id,'title':'SYNTHETIC planning order','total_amount':'0.00','currency':'RUB'}))['record']['id']);self.project_id=int(self.must(self.owner.post(self.base+'/api.php?r=crm/projects',json={'request_key':secrets.token_hex(32),'customer_id':self.customer_id,'order_id':oid,'title':'SYNTHETIC planning project'}))['record']['id']);ids=[]
  for title,priority,due in [('A SYNTHETIC first','urgent','2030-01-04 10:00:00'),('B SYNTHETIC depends','high','2030-01-07 10:00:00'),('C SYNTHETIC third','normal','2030-01-20 10:00:00')]:
   r=self.owner.post(self.base+'/api.php?r=crm/tasks',json={'request_key':secrets.token_hex(32),'title':title,'project_id':self.project_id,'priority':priority,'due_at':due});self.assertEqual(r.status_code,200,r.text);ids.append(int(r.json()['record']['id']))
  tasks_before=self.f.sql('SELECT id,due_at,version FROM nd_tasks ORDER BY id');self.assertIsNone(self.pa('state').json()['calendar']);self.assertEqual(self.pa('calendar',{'version':0,'daily_minutes':120,'weekdays':[1,2,3,4,5],'exceptions':['2030-01-07'],'confirm':True}).status_code,200)
  def build():
   state=self.pa('state').json();r=self.pa('build',{'source_hash':state['source_hash'],'start_on':'2030-01-04'});self.assertEqual(r.status_code,200,r.text);return r.json()
  unknown=build();self.assertEqual(len(unknown['plan']['blocked']),3);self.assertEqual(self.pa('apply',{'plan_id':unknown['plan_id'],'checksum':self.pa('plan&id='+str(unknown['plan_id'])).json()['plan']['checksum'],'confirm':True}).status_code,409)
  def task(id,minutes=120,deps=None):
   state=self.pa('state').json();t=next(x for x in state['tasks'] if int(x['id'])==id);return self.pa('task',{'task_id':id,'task_version':int(t['task_version']),'version':int(t['version']),'estimate_minutes':minutes,'earliest_on':None,'dependencies':deps or []})
  for id in ids:self.assertEqual(task(id,deps=[ids[0]] if id==ids[1] else []).status_code,200)
  self.assertEqual(task(ids[0],deps=[ids[1]]).status_code,422);draft=build();rows=draft['plan']['rows'];self.assertEqual([r['task_id'] for r in rows],ids);self.assertEqual(rows[0]['end_on'],'2030-01-04');self.assertEqual(rows[1]['start_on'],'2030-01-08');self.assertEqual(rows[2]['end_on'],'2030-01-09');self.assertTrue(rows[1]['deadline_conflict']);pid=draft['plan_id'];checksum=self.pa('plan&id='+str(pid)).json()['plan']['checksum'];self.assertEqual(task(ids[0],180).status_code,200);self.assertEqual(self.pa('apply',{'plan_id':pid,'checksum':checksum,'confirm':True}).status_code,409);self.assertEqual(task(ids[0],120).status_code,200);draft=build();pid=draft['plan_id'];checksum=self.pa('plan&id='+str(pid)).json()['plan']['checksum'];self.assertEqual(self.pa('apply',{'plan_id':pid,'checksum':checksum,'confirm':False}).status_code,422);r=self.pa('apply',{'plan_id':pid,'checksum':checksum,'confirm':True});self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['commercial_dates_changed']);self.assertEqual(self.f.sql('SELECT id,due_at,version FROM nd_tasks ORDER BY id'),tasks_before);self.assertFalse(self.pa('plan&id='+str(pid)).json()['plan']['stale']);source=self.pa('terms&id='+str(pid)+'&order='+str(oid));self.assertEqual(source.status_code,200,source.text);self.assertEqual(len(source.json()['source']['rows']),3);self.assertEqual(self.pa('terms&id='+str(pid)+'&order=99999999').status_code,422)
  import os
  from playwright.sync_api import sync_playwright
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':375,'height':812});p.goto(self.base+'/studio.php');p.locator('#password').fill(self.f.password);p.locator('#login-form button').click();p.locator('#dashboard').wait_for(state='visible');p.goto(self.base+'/planning.php');p.get_by_label('Доступных рабочих часов в день',exact=True).wait_for();self.assertEqual(p.get_by_label('Доступных рабочих часов в день',exact=True).input_value(),'2');p.get_by_role('link',name='Подготовить условия заказа по проверенному плану',exact=True).first.wait_for();self.assertFalse(p.evaluate('document.documentElement.scrollWidth>innerWidth'));
   if os.environ.get('NEURO_GUIDE_SHOTS'):p.set_viewport_size({'width':1000,'height':850});p.evaluate('window.scrollTo(0,0)');p.screenshot(path=str(__import__('pathlib').Path(os.environ['NEURO_GUIDE_SHOTS'])/'planning.png'),full_page=False)
   b.close()
for name in dir(qr.ManualQr):
 if name.startswith('test_'):setattr(OwnerPlanning,name,None)
