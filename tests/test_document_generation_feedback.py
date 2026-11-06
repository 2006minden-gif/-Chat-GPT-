"""Owner sees all local errors and server rejections; successful TZ downloads as PDF."""
import json,os,re,tempfile,subprocess
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import test_contract_package as package
class DocumentFeedback(package.ContractPackage):
 def open_form(self,pw,oid,values,legacy):
  saved=self.ctp('terms',order_id=oid,proposal_id=int(legacy[0]['id']),values=values,approved=True,confirm_terms=True);self.assertEqual(saved.status_code,200,saved.text)
  browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);context=browser.new_context(viewport={'width':375,'height':812});context.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);page=context.new_page();page.goto(self.base+'/contract-settings.php?order='+str(oid));page.locator('label').filter(has_text='Тип отдельного документа').locator('select').select_option(str(self.templates[1]['id']));page.locator('label').filter(has_text='Продолжить условия из версии').locator('select').select_option(str(saved.json()['id']));page.get_by_role('checkbox',name='Я проверил соответствие всех условий',exact=False).check();page.get_by_role('checkbox',name='Документ применим',exact=False).check();return browser,page
 def test_all_native_errors_visible_together_without_post_or_lost_fields(self):
  oid,legacy,g,v,terms=self.new_documents();v['spec.date']=''
  with sync_playwright() as pw:
   browser,page=self.open_form(pw,oid,v,legacy);page.get_by_role('button',name='Добавить сценарий',exact=True).wait_for();page.get_by_role('button',name='Добавить сценарий',exact=True).click();posts=[];page.on('request',lambda r:posts.append(r.url) if r.method=='POST' else None);page.get_by_role('button',name='Подготовить отдельный PDF на проверку',exact=True).click();form=page.locator('form').filter(has=page.get_by_role('button',name='Подготовить отдельный PDF на проверку',exact=True));feedback=form.locator('[data-form-feedback]');expect(feedback).to_contain_text('Действие пока не выполнено');self.assertEqual(feedback.get_by_role('button').count(),7);self.assertIn('Дата ТЗ',feedback.inner_text());self.assertIn('Необходимые условия',feedback.inner_text());self.assertTrue(feedback.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0}'));self.assertEqual(posts,[]);self.assertEqual(page.locator('[data-contract-field="project.name"]').input_value(),v['project.name']);feedback.get_by_role('button',name='Дата ТЗ',exact=True).click();self.assertEqual(page.evaluate('document.activeElement.dataset.contractField'),'spec.date');browser.close()
 def test_server_error_stays_near_button_preserves_values_and_retry_generates_real_spec_pdf(self):
  oid,legacy,g,v,terms=self.new_documents();v['spec.completion_deadline']='2099-01-02'
  with sync_playwright() as pw:
   browser,page=self.open_form(pw,oid,v,legacy);submit=page.get_by_role('button',name='Подготовить отдельный PDF на проверку',exact=True);submit.click();feedback=page.locator('form').filter(has=submit).locator('[data-form-feedback]');expect(feedback).not_to_contain_text('Выполняется');expect(feedback).to_be_visible();self.assertIn('Конечный срок раньше срока этапа',feedback.inner_text());self.assertTrue(feedback.evaluate('(e)=>{const r=e.getBoundingClientRect();return r.top<innerHeight&&r.bottom>0}'));expect(submit).to_be_enabled();self.assertEqual(page.locator('[data-contract-field="project.name"]').input_value(),v['project.name']);page.locator('[data-contract-field="spec.completion_deadline"]').fill('2099-02-01');submit.click();page.wait_for_url(re.compile(r'.*documents\.php\?mode=owner#document/[1-9][0-9]*$'))
   with page.expect_download() as got:page.get_by_role('link',name='Скачать PDF',exact=True).click()
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'spec.pdf';got.value.save_as(str(path));self.assertTrue(path.read_bytes().startswith(b'%PDF-'));text=subprocess.check_output(['pdftotext',str(path),'-'],text=True);self.assertIn('Техническое задание',text);self.assertNotIn('{{',text)
   self.assertIsNone(self.f.sql('SELECT owner_reviewed_at FROM nd_lc_pdf_assets WHERE binding_id=?',params=[int(page.url.rsplit('/',1)[1])])[0]['owner_reviewed_at']);browser.close()
for name in dir(package.ContractPackage):
 if name.startswith('test_'):setattr(DocumentFeedback,name,None)
