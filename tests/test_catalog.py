"""Stage9 dependency repair: real MySQL/PHP/customer approvals, optional mocked AI only."""
import json
import secrets
import subprocess
import unittest
from datetime import datetime,timedelta,timezone
from test_pricing import Pricing

class Catalog(Pricing):
 @classmethod
 def setUpClass(cls):
  super().setUpClass()
  for runner in ['migrate-production.php','migrate-manual.php','migrate-catalog.php']:
   r=subprocess.run([cls.f.php,str(cls.f.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if r.returncode:raise RuntimeError(runner+': '+r.stderr)
  cls.f.config.update(catalog_enabled=True,catalog_requests_enabled=True,catalog_privacy_approved=True,production_enabled=True,production_execution_enabled=True);cls.f.write_config()
  for role in ['production_coordinator','production_website','production_application','production_agent','production_design','production_content','production_integration','production_qa']:cls.f.sql('INSERT INTO nd_ai_agents(agent_id,enabled) VALUES (?,1)',params=[role])
 def setUp(self):
  super().setUp();self.approved_price();self.template_id=self.manage('templates',body=self.template())['id'];t=self.owner_detail('templates',self.template_id);self.manage('templates',self.template_id,'publish',version=int(t['version']),checksum=t['versions'][0]['checksum'],confirm=True);self.template_version=t['versions'][0]['id'];self.service_id=self.manage('services',slug='test-'+secrets.token_hex(5),template_version_id=int(self.template_version),body=self.service())['id'];s=self.owner_detail('services',self.service_id);self.manage('services',self.service_id,'publish',version=int(s['version']),checksum=s['versions'][0]['checksum'],confirm=True);self.service_version=s['versions'][0]['id']
 def cu(self,s,route):return self.base+('/api.php?r=crm/catalog/' if s is self.owner else '/customer-api.php?r=catalog/')+route
 def cg(self,route,s=None):return (s or self.owner).get(self.cu(s or self.owner,route))
 def cp(self,route,s=None,**d):
  s=s or self.owner;d.setdefault('request_key',secrets.token_hex(32));return s.post(self.cu(s,route),json=d)
 def manage(self,kind,id=0,action='save',**d):
  r=self.cp(kind+('/'+str(id) if id else '')+'/'+action,**d);self.assertEqual(r.status_code,200,r.text);return r.json()
 def owner_detail(self,kind,id):return self.cg(kind+'/'+str(id)).json()['record']
 def template(self):
  def q(id,label,type='text',required=True,semantic='goal',options=None,when=None):return {'id':id,'label':label,'type':type,'semantic':semantic,'required':required,'options':options or [],'min':1,'max':200 if type!='number' else 100,'when':when}
  return {'title':'Синтетическая анкета агента','steps':[{'title':'Задача','questions':[q('goal','Задача клиента'),q('channel','Нужна интеграция','choice',semantic='integrations',options=['Да','Нет'])]},{'title':'Детали','questions':[q('system','Название системы',semantic='integrations',when={'field':'channel','equals':'Да'}),q('review_hours','Время проверки владельцем','number',semantic='other')]}]}
 def service(self):return {'name':'Синтетический агент','description':'Только тестовые документы агента','category':'ai_agent','scope':['Согласованная схема'],'deliverables':['Схема агента'],'pricing_type':'estimate','packages':[{'id':'basic','name':'Тестовый пакет','description':'Синтетические условия','price':None,'work_packages':self.packages(),'quantity_rules':[{'question':'review_hours','package_index':0,'quantity':'testing_hours'}]}],'consultation_url':'https://t.me/minden2006'}
 def consent(self):return {'consent':True,'policy_version':'test-policy-v1'}
 def request(self,answers=None):
  r=self.cp('requests',s=self.customer,service_version_id=int(self.service_version),package_key='basic',**self.consent());self.assertEqual(r.status_code,200,r.text);id=r.json()['id'];d=self.cg('requests/'+str(id),self.customer).json()['record'];r=self.cp(f'requests/{id}/save',s=self.customer,version=int(d['version']),answers=answers or {'goal':'Нужна схема помощника для проверки документов','channel':'Нет','review_hours':1},file_ids=[],**self.consent());self.assertEqual(r.status_code,200,r.text);return self.cg('requests/'+str(id),self.customer).json()['record']
 def submitted(self):
  r=self.request();x=self.cp(f'requests/{r["id"]}/submit',s=self.customer,version=int(r['version']),**self.consent());self.assertEqual(x.status_code,200,x.text);return self.cg('requests/'+str(r['id'])).json()['record']
 def offer(self):
  r=self.submitted();q=self.get(self.owner,'pricing/quotes/'+str(r['quotation']['id'])).json()['record'];a=self.approve(q);self.assertEqual(a.status_code,200,a.text);x=self.cp(f'requests/{r["id"]}/offer',version=int(r['version']),terms='Синтетические условия, проверены владельцем.',expires_at=(datetime.now(timezone.utc)+timedelta(days=3)).strftime('%Y-%m-%d %H:%M:%S'),due_on=None);self.assertEqual(x.status_code,200,x.text);o=self.cg('requests/'+str(r['id'])).json()['record']['offers'][0];x=self.cp(f'offers/{o["id"]}/publish',version=int(o['version']),checksum=o['checksum'],confirm=True);self.assertEqual(x.status_code,200,x.text);r=self.cg('requests/'+str(r['id']),self.customer).json()['record'];return r,r['offers'][0]
 def test_01_publication_no_cost_leak_and_owner_versions(self):
  x=self.customer.get(self.base+'/catalog-api.php?r=services/'+str(self.service_id));self.assertEqual(x.status_code,200,x.text);self.assertEqual(x.json()['record']['name'],'Синтетический агент');self.assertNotIn('work_packages',x.text);self.assertNotIn('quantity_rules',x.text)
  s=self.owner_detail('services',self.service_id);self.manage('services',self.service_id,body=self.service(),version=int(s['version']),template_version_id=int(self.template_version));x=self.customer.get(self.base+'/catalog-api.php?r=services/'+str(self.service_id));self.assertEqual(int(x.json()['record']['revision']),1)
  r=self.cp('services/'+str(self.service_id)+'/unpublish',s=self.customer,version=1,confirm=True);self.assertEqual(r.status_code,403,r.text)
 def test_02_conditional_validation_drafts_and_immutable_brief(self):
  r=self.request({'goal':'Нужен помощник для документов','channel':'Да','review_hours':1});x=self.cp(f'requests/{r["id"]}/submit',s=self.customer,version=int(r['version']),**self.consent());self.assertEqual(x.status_code,422,x.text);self.assertIn('Название системы',x.text)
  x=self.cp(f'requests/{r["id"]}/save',s=self.customer,version=int(r['version']),answers={'goal':'Нужен помощник','channel':'Нет','system':'Скрытый ответ','review_hours':1},file_ids=[],**self.consent());self.assertEqual(x.status_code,422)
  r=self.submitted();b=r['briefs'][0];self.assertIn('Нужна схема',b['structured_json']);self.assertEqual(r['state'],'PRICING');self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lead_customers WHERE lead_id=?',params=[r['lead_id']])[0]['n'],1)
 def test_03_full_quote_accept_order_and_real_stage10_source(self):
  r,o=self.offer();self.assertNotIn('cost_pool_minor',json.dumps(r));x=self.cp(f'offers/{o["id"]}/accept',s=self.customer,version=int(o['version']),checksum=o['checksum'],confirm=True);self.assertEqual(x.status_code,200,x.text);r=self.cg('requests/'+str(r['id']),self.customer).json()['record'];self.assertEqual(r['state'],'ACCEPTED');x=self.cp(f'requests/{r["id"]}/confirm',s=self.customer,version=int(r['version']),confirm=True);self.assertEqual(x.status_code,200,x.text);oid=x.json()['order_id'];x2=self.cp(f'requests/{r["id"]}/confirm',s=self.customer,version=int(r['version']),confirm=True);self.assertEqual(x2.status_code,200,x2.text);self.assertEqual(x2.json()['order_id'],oid)
  owner=self.cg('requests/'+str(r['id'])).json()['record'];q=self.get(self.owner,'pricing/quotes/'+str(owner['quotation']['id'])).json()['record'];self.assertTrue(q['fresh']);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_orders WHERE deal_id=?',params=[owner['deal_id']])[0]['n'],1)
  for rate in q['calculation']['rates'].values():
   x=self.post(self.owner,'production/rates/scope',rate_id=int(rate['id']),service_type='agent_spec',active=True,verified_at='2026-01-01 00:00:00',source='Синтетическая проверка применимости');self.assertEqual(x.status_code,200,x.text)
  body={'title':'Проверенный план','steps':[{'key':'draft','title':'Схема','agent':'production_agent','depends_on':[],'files':['agent.md','installation.md','limitations.md'],'requirement_ids':['R1']}],'requirements':[{'id':'R1','description':'Схема агента','file':'agent.md','method':'contains','expected':'Схема агента'}],'budget_micro':100000,'cost_currency':'RUB','max_revisions':2,'limitations':['Только документы']};spec=json.loads(owner['offers'][0]['body'])['spec_revision_id'];x=self.post(self.owner,'production/plans',project_id=int(owner['project_id']),spec_revision_id=int(spec),plan=body);self.assertEqual(x.status_code,200,x.text);src=json.loads(x.json()['record']['source_json']);self.assertEqual(src['upstream']['adapter'],'catalog_customer_acceptance')
 def test_04_stale_prices_and_cross_customer_rejected(self):
  r,o=self.offer();self.assertEqual(self.cg('requests/'+str(r['id']),self.stranger).status_code,404);self.assertEqual(self.cp(f'offers/{o["id"]}/accept',s=self.stranger,version=int(o['version']),checksum=o['checksum'],confirm=True).status_code,404);self.rate('labor_hour','150.00');x=self.cp(f'offers/{o["id"]}/accept',s=self.customer,version=int(o['version']),checksum=o['checksum'],confirm=True);self.assertEqual(x.status_code,409,x.text);self.assertEqual(self.cg('requests/'+str(r['id']),self.customer).json()['record']['state'],'AWAITING_ACCEPTANCE')

for name in dir(Pricing):
 if name.startswith('test_'):setattr(Catalog,name,None)
del Pricing
