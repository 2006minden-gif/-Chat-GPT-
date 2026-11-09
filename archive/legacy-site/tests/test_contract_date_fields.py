"""The selected document validates only its own dates; real browser restore/generation."""
import copy,json,os,re,subprocess,tempfile
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import test_contract_package as package
class ContractDates(package.ContractPackage):
 def saved_terms(self,oid,legacy,values):
  r=self.ctp('terms',order_id=oid,proposal_id=int(legacy[0]['id']),values=values,approved=True,confirm_terms=True);self.assertEqual(r.status_code,200,r.text);return r.json()['id']
 def test_unselected_dates_do_not_block_agreement_but_required_dates_still_validate(self):
  oid,legacy,g,values,old=self.new_documents();values.update({'spec.date':'','act.date':'not a date','change.date':'2099-02-30','permission.date':'','review.date':''});terms=self.saved_terms(oid,legacy,values);r=self.gen(self.templates[0],terms);self.assertEqual(r.status_code,200,r.text);record=r.json()['record'];self.assertEqual(record['state'],'OWNER_REVIEW');self.assertEqual(json.loads(record['input_snapshot'])['package_fields']['contract.date'],'2099-01-01');self.assertIsNone(self.f.sql('SELECT owner_reviewed_at FROM nd_lc_pdf_assets WHERE binding_id=?',params=[record['id']])[0]['owner_reviewed_at'])
  for bad_date in ['', '2099-02-30', '01.01.2099']:
   invalid=copy.deepcopy(values);invalid['contract.date']=bad_date;r=self.gen(self.templates[0],self.saved_terms(oid,legacy,invalid));self.assertEqual(r.status_code,422,r.text);self.assertIn('Дата договора',r.json()['detail']);self.assertNotIn('contract.date',r.json()['detail'])
  r=self.gen(self.templates[1],terms);self.assertEqual(r.status_code,422,r.text);self.assertIn('Дата ТЗ',r.json()['detail']);self.assertNotIn('spec.date',r.json()['detail'])
 def test_browser_native_dates_restore_saved_terms_and_generate_exact_agreement_pdf(self):
  oid,legacy,g,values,old=self.new_documents();values['spec.date']='';terms=self.saved_terms(oid,legacy,values)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);context=browser.new_context(viewport={'width':768,'height':1000});context.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);page=context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(self.base+'/contract-settings.php?order='+str(oid));template=page.locator('label').filter(has_text='Тип отдельного документа').locator('select');template.wait_for();template.select_option(str(self.templates[1]['id']));self.assertEqual(page.locator('[data-contract-field="spec.date"]').get_attribute('type'),'date');template.select_option(str(self.templates[0]['id']));page.locator('label').filter(has_text='Продолжить условия из версии').locator('select').select_option(str(terms));date=page.locator('[data-contract-field="contract.date"]');self.assertEqual(date.get_attribute('type'),'date');self.assertEqual(date.input_value(),'2099-01-01');self.assertEqual(page.locator('[data-contract-field="spec.date"]').count(),0);page.get_by_role('checkbox',name='Я проверил соответствие всех условий точному предложению',exact=False).check();page.get_by_role('checkbox',name='Документ применим к текущему этапу',exact=False).check();page.screenshot(path='/tmp/neuro-contract-dates-form.png',full_page=False);page.get_by_role('button',name='Подготовить отдельный PDF на проверку',exact=True).click();page.wait_for_url(re.compile(r'.*documents\.php\?mode=owner#document/[1-9][0-9]*$'));download=page.get_by_role('link',name='Скачать PDF',exact=True);download.wait_for()
   with page.expect_download() as got:download.click()
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'agreement.pdf';got.value.save_as(str(path));self.assertTrue(path.read_bytes().startswith(b'%PDF-'));text=subprocess.check_output(['pdftotext',str(path),'-'],text=True);self.assertIn('Договор',text);self.assertIn('2099-01-01',text);self.assertNotIn('{{',text)
   self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);browser.close()
for name in dir(package.ContractPackage):
 if name.startswith('test_'):setattr(ContractDates,name,None)
