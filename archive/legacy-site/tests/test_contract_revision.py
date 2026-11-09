"""Exact new legal revisions, conditional schedules and owner-only synthetic previews."""
import copy,json,subprocess,tempfile
from pathlib import Path
import test_contract_package as package
class RevisedContract(package.ContractPackage):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-workflow.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)

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
   preview=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+t['kind']);self.assertEqual(preview.status_code,200,preview.text[:80]);self.assertTrue(preview.content.startswith(b'%PDF-'));
   with tempfile.TemporaryDirectory() as tmp:
    f=Path(tmp)/'preview.pdf';f.write_bytes(preview.content);text=subprocess.check_output(['pdftotext',str(f),'-']).decode();self.assertIn(t['title'],text);self.assertNotIn(self.templates[1 if t['kind']=='agreement' else 0]['title'],text)
   self.assertIn(self.stranger.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+t['kind']).status_code,[401,403]);self.assertIn(self.customer.get(self.base+'/lifecycle-api.php?r=contracts/sample/'+t['kind']).status_code,[401,403,503])
  original=self.templates[0]['clauses'];swapped=copy.deepcopy(original);swapped['_package']['paragraphs']=self.templates[1]['clauses']['_package']['paragraphs'];self.f.sql('UPDATE nd_lc_templates SET clauses_json=? WHERE id=?',params=[json.dumps(swapped,ensure_ascii=False),self.templates[0]['id']])
  try:
   self.assertEqual(self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/agreement').status_code,409);self.assertEqual(self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+str(self.templates[0]['id'])).status_code,409)
  finally:self.f.sql('UPDATE nd_lc_templates SET clauses_json=? WHERE id=?',params=[json.dumps(original,ensure_ascii=False),self.templates[0]['id']])
  before=[(t['id'],t['checksum'],t['state']) for t in self.templates];self.assertEqual(self.ctp('import').json()['ids'],[t[0] for t in before]);after=[self.lg('templates/'+str(t[0])).json()['record'] for t in before];self.assertEqual(before,[(t['id'],t['checksum'],t['state']) for t in after])
 def test_browser_structured_fields_and_conditional_stage_editor(self):
  import os
  from playwright.sync_api import sync_playwright,expect
  oid,legacy,g,values,terms=self.new_documents()
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);c=b.new_context(viewport={'width':375,'height':812});p=c.new_page();p.goto(self.base+'/studio.php');p.locator('#password').fill(self.f.password);p.locator('#login-form button').click();p.locator('#dashboard').wait_for(state='visible');p.goto(self.base+'/contract-settings.php?order='+str(oid));p.locator('label').filter(has_text='Тип отдельного документа').locator('select').select_option(str(self.templates[1]['id']));p.get_by_role('button',name='Добавить сценарий',exact=True).click();p.get_by_label('Роль пользователя',exact=True).fill('Тестовый посетитель');p.get_by_role('button',name='Регулярных внешних расходов нет',exact=True).click();self.assertEqual(p.locator('[data-contract-field="spec.recurring_costs"]').input_value(),'[]');self.assertEqual(json.loads(p.locator('[data-contract-field="spec.acceptance_criteria"]').input_value())[0]['role'],'Тестовый посетитель');milestones=p.locator('section.card').filter(has=p.get_by_role('heading',name='Этапы работ',exact=True));milestones.get_by_role('button',name='Добавить этап',exact=True).click();milestones.locator('label').filter(has_text='Расчёт срока этапа').locator('select').select_option('relative');milestones.get_by_label('Объективное условие начала',exact=True).fill('Получены материалы');milestones.get_by_label('Длительность в днях',exact=True).fill('10');milestones.locator('label').filter(has_text='Какие дни').locator('select').select_option('business');row=json.loads(p.locator('[data-contract-field="spec.milestones"]').input_value())[0];self.assertNotIn('due_on',row);self.assertEqual(row['duration_days'],10);self.assertFalse(p.evaluate('document.documentElement.scrollWidth>innerWidth'));b.close()
 def test_cross_site_links_and_distinct_verified_pdf_downloads(self):
  import os
  from playwright.sync_api import sync_playwright,expect
  self.new_documents();texts=[]
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);p=b.new_page(accept_downloads=True);p.goto(self.base+'/studio.php');p.locator('#password').fill(self.f.password);p.locator('#login-form button').click();p.locator('#dashboard').wait_for(state='visible')
   external='https://outside.example.test/'
   def outside(route):route.fulfill(content_type='text/html',body='<a href="'+self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/agreement">Old direct link</a><a href="'+self.base+'/documents.php?mode=owner&preview=agreement">Contract preview</a><a href="'+self.base+'/documents.php?mode=owner&preview=specification">Specification preview</a>')
   p.route(external,outside);p.goto(external)
   with p.expect_response(lambda r:'/lifecycle-api.php?' in r.url) as response:p.get_by_role('link',name='Old direct link',exact=True).click()
   self.assertEqual(response.value.status,401);self.assertIn('Войдите',response.value.text())
   for t,label in zip(self.templates[:2],['Contract preview','Specification preview']):
    p.goto(external);p.get_by_role('link',name=label,exact=True).click();p.get_by_role('heading',name=t['title']+' · v'+str(t['revision_number']),exact=True).wait_for();button=p.get_by_role('button',name='Скачать образец PDF',exact=False)
    with p.expect_download() as download:button.click()
    file=download.value;self.assertEqual(file.suggested_filename,'NeuroDelo-'+t['kind']+'-v'+str(t['revision_number'])+'-sample.pdf');text=subprocess.check_output(['pdftotext',str(file.path()),'-']).decode();self.assertIn(t['title'],text);texts.append(text)
   self.assertNotEqual(texts[0],texts[1]);self.assertNotIn(self.templates[1]['title'],texts[0]);self.assertNotIn(self.templates[0]['title'],texts[1]);
   first=self.templates[0];other=self.templates[1];p.goto(self.base+'/documents.php?mode=owner&preview=agreement');button=p.get_by_role('button',name='Скачать образец PDF',exact=False);button.wait_for();unexpected=[];p.on('download',lambda d:unexpected.append(d));pattern='**/lifecycle-api.php?mode=owner&r=contracts/sample/'+str(first['id']);wrong=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+str(other['id']));headers={k:v for k,v in wrong.headers.items() if k.lower()=='content-type' or k.lower().startswith('x-neuro-')};p.route(pattern,lambda route:route.fulfill(status=200,headers=headers,body=wrong.content));button.click();expect(p.locator('#lc-message')).to_contain_text('другой тип');self.assertEqual(unexpected,[]);p.unroute(pattern);right=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+str(first['id']));headers={k:v for k,v in right.headers.items() if k.lower()=='content-type' or k.lower().startswith('x-neuro-')};p.route(pattern,lambda route:route.fulfill(status=200,headers=headers,body=right.content+b'corrupted'));button.click();expect(p.locator('#lc-message')).to_contain_text('Контрольная сумма');self.assertEqual(unexpected,[]);b.close()
for name in dir(package.ContractPackage):
 if name.startswith('test_'):setattr(RevisedContract,name,None)
