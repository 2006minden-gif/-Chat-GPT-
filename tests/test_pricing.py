"""Cost-based pricing: synthetic rates, owner-only quotes, no production financial actions."""
import json
import secrets
import subprocess
import unittest
from test_ai import Ai,AiTransport

class Pricing(Ai):
 def packages(self,**changes):
  p={'name':'Синтетический пакет','development_hours':'1','testing_hours':'1','ai_input_tokens':'0','ai_output_tokens':'0','hosting_months':'0','tool_units':'0','external_units':'0','other_units':'0','risk':'medium','uncertain':True,'basis':'Явные данные тестового брифа'};p.update(changes);return [p]
 def estimate(self,packages=None):
  r=self.post(self.owner,f'pricing/projects/{self.project_id}/estimate',packages=packages or self.packages());self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def rate(self,category,value,**extra):
  r=self.post(self.owner,'pricing/rates',category=category,value=value,currency='RUB',source='Синтетическая ставка теста',source_date='2026-01-01',valid_from='2026-01-01',valid_until='2099-12-31',**extra);self.assertEqual(r.status_code,200,r.text);return r.json()['id']
 def approve(self,q):return self.post(self.owner,f'pricing/quotes/{q["id"]}/approve',checksum=q['checksum'],confirm=True,accept_estimates=True,reason='Владелец проверил расчёт')
 def test_60_unknown_inputs_explicit_zero_and_rates(self):
  q=self.estimate(self.packages(development_hours=None));self.assertEqual(q['state'],'NEEDS_COST_REVIEW');self.assertIsNone(q['calculation']['selling_minor']);self.assertEqual(self.approve(q).status_code,409)
  self.approved_price();q=self.estimate(self.packages(development_hours='0',testing_hours='0'));self.assertEqual(q['calculation']['direct_minor'],0);self.assertEqual(q['calculation']['selling_minor'],0);self.assertEqual(q['state'],'DRAFT');self.assertEqual(self.approve(q).status_code,200)
  self.f.sql("UPDATE nd_projects SET description='' WHERE id=?",params=[self.project_id]);q=self.estimate(self.packages());self.assertEqual(q['state'],'NEEDS_COST_REVIEW');self.assertTrue(any('требований' in x for x in q['calculation']['missing']))
 def test_61_exact_profit_rates_material_changes_and_proposal_binding(self):
  q=self.approved_price();r=q['calculation'];self.assertEqual(r['direct_minor'],20000);self.assertEqual(r['overhead_minor'],1000);self.assertEqual(r['contingency_minor'],2100);self.assertEqual(r['recommended_minor'],28875);self.assertEqual(r['contribution_minor'],5775)
  response=self.post(self.owner,'tasks',agent='proposal',question='Подготовьте предложение',project_id=self.project_id);tid=response.json()['id'];t=self.run_task(tid);p=t['approvals'][0];body=json.loads(p['proposal_json']);self.assertEqual(body['quotation']['id'],q['id']);self.assertIn('288.75 RUB',body['result']['body'])
  self.assertEqual(self.post(self.owner,f'approvals/{p["id"]}/decide',checksum=p['proposal_hash'],version=int(p['version']),decision='approved',confirm=True).status_code,200)
  self.rate('labor_hour','120.00');old=self.get(self.owner,f'pricing/quotes/{q["id"]}').json()['record'];self.assertFalse(old['fresh']);self.assertEqual(old['calculation'],r)
  p=self.get(self.owner,f'tasks/{tid}').json()['record']['approvals'][0];self.assertEqual(self.post(self.owner,f'approvals/{p["id"]}/apply',checksum=p['proposal_hash'],version=int(p['version']),confirm=True).status_code,409)
  response=self.post(self.owner,'tasks',agent='proposal',question='Ещё одно предложение',project_id=self.project_id);before=len(AiTransport.calls);t=self.run_task(response.json()['id']);self.assertEqual(t['state'],'NEEDS_HUMAN');self.assertEqual(t['last_error'],'NEEDS_COST_REVIEW');self.assertEqual(len(AiTransport.calls),before)
  new=self.post(self.owner,f'pricing/quotes/{q["id"]}/recalculate',checksum=q['checksum']);self.assertEqual(new.status_code,200,new.text);new=new.json()['record'];self.assertGreater(int(new['revision_number']),int(q['revision_number']));self.assertEqual(new['state'],'DRAFT');self.assertEqual(self.approve(new).status_code,200)
 def test_62_owner_override_below_threshold_and_no_mutation(self):
  q=self.approved_price();r=self.post(self.owner,f'pricing/quotes/{q["id"]}/edit',checksum=q['checksum'],price='1.00');self.assertEqual(r.status_code,200,r.text);low=r.json()['record'];self.assertEqual(low['state'],'NEEDS_COST_REVIEW');self.assertEqual(low['calculation']['profitability'],'LOSS');self.assertEqual(self.approve(low).status_code,409)
  old=self.get(self.owner,f'pricing/quotes/{q["id"]}').json()['record'];self.assertEqual(old['state'],'APPROVED');self.assertEqual(old['calculation']['selling_minor'],28875)
  for actor in [self.customer,self.stranger]:self.assertEqual(self.get(actor,'pricing/quotes').status_code,403);self.assertEqual(self.post(actor,f'pricing/quotes/{q["id"]}/approve',checksum=q['checksum'],confirm=True).status_code,403)
  self.assertEqual(self.post(self.owner,f'pricing/quotes/{q["id"]}/edit',checksum='0'*64,price='300').status_code,409)
 def test_63_ai_estimates_and_actual_comparison_owner_controlled(self):
  self.approved_price();self.rate('ai_input_1000','1.00');self.rate('ai_output_1000','2.00');self.rate('hosting_month','10.00')
  t=self.run_task(self.create('cost_estimator'));self.assertEqual(t['state'],'COMPLETED');artifact=t['artifacts'][0];self.assertEqual(artifact['effect_entity'],'quotations');q=self.get(self.owner,'pricing/quotes/'+str(artifact['effect_id'])).json()['record'];self.assertEqual(q['state'],'DRAFT');self.assertEqual(self.approve(q).status_code,200)
  self.f.sql("UPDATE nd_projects SET status='completed',version=version+1 WHERE id=?",params=[self.project_id]);r=self.post(self.owner,f'pricing/quotes/{q["id"]}/actuals',checksum=q['checksum'],actual_cost='330',development_hours='3',testing_hours='1',source='Синтетический итог владельца',confirm=True);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['actual_cost_minor'],33000);self.assertEqual(r.json()['contribution_after_actual_minor'],int(q['calculation']['selling_minor'])-33000)
  insight=self.get(self.owner,'pricing/insights').json();self.assertEqual(insight['sample_count'],1);self.assertFalse(insight['applied']);self.assertEqual(insight['suggested_effort_factor_bp'],13334);self.assertEqual(self.get(self.owner,f'pricing/quotes/{q["id"]}').json()['record']['calculation'],q['calculation'])
 def test_64_periodic_pricing_off_and_idempotent_auto_queue(self):
  c=json.loads(json.dumps(self.f.config))
  try:
   self.f.config['ai_pricing_auto_enabled']=True;self.f.write_config();before=self.f.sql("SELECT COUNT(*) n FROM nd_ai_tasks WHERE project_id=? AND agent_id='cost_estimator'",params=[self.project_id])[0]['n']
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/ai/routes.php";echo pricing_automatic_projects();'
   for _ in range(3):self.f.php_eval(code,{'root':str(self.f.path)})
   after=self.f.sql("SELECT COUNT(*) n FROM nd_ai_tasks WHERE project_id=? AND agent_id='cost_estimator'",params=[self.project_id])[0]['n'];self.assertEqual(after,before+1)
  finally:self.f.config=c;self.f.write_config()

 def test_65_fee_tax_and_effort_rules_do_not_use_float(self):
  self.approved_price();self.rate('payment_fee_percent','2.50');r=self.post(self.owner,'pricing/policy',name='Проверка процентов',contingency='10',margin='20',minimum='10',overhead='5',effort_factor='150',tax='6',tax_method='included_percent',source='Синтетическая проверка, не налоговый режим владельца',approved=True);self.assertEqual(r.status_code,200,r.text)
  q=self.estimate();c=q['calculation'];self.assertEqual(c['direct_minor'],30000);self.assertGreaterEqual(c['contribution_minor']*10000,c['selling_minor']*2000);self.assertEqual(c['tax_minor'],(c['selling_minor']*600+9999)//10000);self.assertEqual(c['payment_fee_minor'],(c['selling_minor']*250+9999)//10000);self.assertEqual(self.approve(q).status_code,200)
  self.f.sql('UPDATE nd_projects SET version=version+1 WHERE id=?',params=[self.project_id]);old=self.get(self.owner,f'pricing/quotes/{q["id"]}').json()['record'];self.assertFalse(old['fresh']);new=self.post(self.owner,f'pricing/quotes/{q["id"]}/recalculate',checksum=q['checksum']);self.assertEqual(new.status_code,200,new.text);self.assertEqual(new.json()['record']['state'],'NEEDS_COST_REVIEW')

 def test_66_foreign_rate_is_not_silently_converted_to_rubles(self):
  q=self.approved_price();r=self.post(self.owner,'pricing/rates',category='labor_hour',value='10',currency='USD',source='Синтетическая ставка USD без утверждённого пересчёта',source_date='2026-01-01',valid_from='2026-01-01',valid_until='2099-12-31');self.assertEqual(r.status_code,200,r.text);new=self.estimate();self.assertEqual(new['state'],'NEEDS_COST_REVIEW');self.assertIsNone(new['calculation']['selling_minor']);self.assertEqual(self.get(self.owner,f'pricing/quotes/{q["id"]}').json()['record']['calculation']['selling_minor'],28875)

for _name in dir(Ai):
 if _name.startswith('test_'):setattr(Pricing,_name,None)
del Ai
