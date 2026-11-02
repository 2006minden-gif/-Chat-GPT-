"""Exact new legal revisions, conditional schedules and owner-only synthetic previews."""
import copy,json,subprocess,tempfile
from pathlib import Path
import test_contract_package as package
class RevisedContract(package.ContractPackage):
 def test_explicit_fields_schedules_preview_and_preserved_source(self):
  oid,legacy,g,values,terms=self.new_documents();spec=self.templates[1]
  def generate(v):
   saved=self.ctp('terms',order_id=oid,proposal_id=int(legacy[0]['id']),values=v,approved=True,confirm_terms=True);self.assertEqual(saved.status_code,200,saved.text);return self.gen(spec,saved.json()['id'])
  for field in ['project.purpose','project.audience','support.response_time','support.defect_procedure','spec.completion_deadline','price.rights_fee']:
   bad=copy.deepcopy(values);del bad[field];self.assertEqual(generate(bad).status_code,422,field)
  for field in ['spec.recurring_costs','spec.acceptance_criteria']:
   bad=copy.deepcopy(values);bad[field]='Unreviewed prose instead of structured agreement';self.assertEqual(generate(bad).status_code,422,field)
  bad=copy.deepcopy(values);bad['price.rights_fee']='999999999.00';self.assertEqual(generate(bad).status_code,422)
  rows=json.loads(values['spec.milestones']);rows[0].update(start_condition='После получения материалов',duration_days=10,day_type='business');bad=copy.deepcopy(values);bad['spec.milestones']=json.dumps(rows);self.assertEqual(generate(bad).status_code,422)
  del rows[0]['start_on'];del rows[0]['due_on'];good=copy.deepcopy(values);good['spec.milestones']=json.dumps(rows);good['spec.recurring_costs']=json.dumps([{'name':'Домен','amount':'1000.00','period':'год','payer':'Заказчик','included':False}]);r=generate(good);self.assertEqual(r.status_code,200,r.text);snapshot=json.loads(r.json()['record']['input_snapshot']);render=snapshot['rendered']['description'];self.assertIn('10 рабочих',render);self.assertIn('не включено в цену',render);self.assertNotIn('{{',render);self.assertIn('первоначальный',render);self.assertIn('окончательный',render);self.assertNotIn('Первый платёж',render);self.assertEqual(snapshot['package_fields']['project.purpose'],values['project.purpose'])
  bad=copy.deepcopy(values);bad['project.purpose']='[Уточнить: цель]';self.assertEqual(generate(bad).status_code,422)
  bad=copy.deepcopy(values);rows=json.loads(bad['spec.milestones']);rows[0]['amount']='0.01';bad['spec.milestones']=json.dumps(rows);self.assertEqual(generate(bad).status_code,422)
  # A historical approved source is still downloadable and never overwritten by import.
  archived=copy.deepcopy(self.templates[0]['clauses']['_package']);archived['sha256']=__import__('hashlib').sha256((self.f.path/'private/lifecycle/package/history/01_contract-r1.docx').read_bytes()).hexdigest();archived.pop('terms_schema',None);clauses=json.dumps({'_package':archived},ensure_ascii=False,separators=(',',':'));checksum=__import__('hashlib').sha256(('SYNTHETIC historic '+clauses).encode()).hexdigest();self.f.sql("INSERT INTO nd_lc_templates(kind,revision_number,title,clauses_json,checksum,state) VALUES ('agreement',999,'SYNTHETIC historical revision',?,?,'APPROVED')",params=[clauses,checksum]);historic=self.f.sql('SELECT id FROM nd_lc_templates WHERE checksum=?',params=[checksum])[0]['id'];source=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/source/'+str(historic));self.assertEqual(source.status_code,200);self.assertEqual(__import__('hashlib').sha256(source.content).hexdigest(),archived['sha256'])
  old=self.f.path/'private/lifecycle/package/history/01_contract-r1.docx';self.assertTrue(old.is_file())
  for t in self.templates[:2]:
   preview=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+t['kind']);self.assertEqual(preview.status_code,200,preview.text[:80]);self.assertTrue(preview.content.startswith(b'%PDF-'));self.assertIn(self.stranger.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+t['kind']).status_code,[401,403]);self.assertIn(self.customer.get(self.base+'/lifecycle-api.php?r=contracts/sample/'+t['kind']).status_code,[401,403,503])
  before=[(t['id'],t['checksum'],t['state']) for t in self.templates];self.assertEqual(self.ctp('import').json()['ids'],[t[0] for t in before]);after=[self.lg('templates/'+str(t[0])).json()['record'] for t in before];self.assertEqual(before,[(t['id'],t['checksum'],t['state']) for t in after])
for name in dir(package.ContractPackage):
 if name.startswith('test_'):setattr(RevisedContract,name,None)
