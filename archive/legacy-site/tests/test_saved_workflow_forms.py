"""A persisted scoped-link form may navigate; errors and newer edits stay guarded."""
import json,os
from urllib.parse import urlsplit
from playwright.sync_api import sync_playwright,expect
import test_unified_workspace as unified
class SavedForms(unified.UnifiedWorkspace):
 def page_form(self,browser,oid):
  page=self.session_page(browser);page.goto(self.base+'/order-workflow.php?order='+str(oid)+'&stage=details');expect(page.locator('body')).to_have_attribute('data-workflow-ready','true');form=page.locator('#po-content>form.card');form.wait_for();form.get_by_role('checkbox',name='Разрешить заполнение данных для договора без регистрации',exact=True).check();form.get_by_role('checkbox',name='Отправить через подтверждённую почту',exact=False).check();form.get_by_role('checkbox',name='Я проверил состав и версии',exact=False).check();form.get_by_label('Срок в часах: 1–168',exact=True).fill('24');return page,form
 def test_successful_email_link_creation_clears_only_the_saved_form_guard(self):
  oid=self.start_order();self.smtp.messages.clear()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page,form=self.page_form(browser,oid);shortcut=page.locator('.owner-shortcuts').get_by_role('link',name='Реквизиты исполнителя',exact=True);shortcut.click();expect(page.locator('#workflow-status')).to_contain_text('Сначала сохраните');self.assertIn('stage=details',page.url);form.get_by_role('button',name='Создать ограниченную ссылку',exact=True).click();expect(page.locator('#po-message')).to_contain_text('SMTP принял письмо');self.assertEqual(len(self.smtp.messages),1);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_prospect_links WHERE order_id=?',params=[oid])[0]['n'],1);shortcut.click();page.wait_for_url(self.base+'/contract-settings.php');self.assertEqual(len(page.context.pages),1);browser.close()
 def test_failed_save_keeps_actual_unsaved_changes_guarded(self):
  oid=self.start_order();self.smtp.messages.clear();before=self.f.sql('SELECT COUNT(*) n FROM nd_lc_prospect_links')[0]['n']
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page,form=self.page_form(browser,oid)
   def fail(route):
    if route.request.method=='POST':route.fulfill(status=422,content_type='application/json',body=json.dumps({'ok':False,'detail':'SYNTHETIC not saved'}))
    else:route.continue_()
   page.route('**/prospect-api.php?mode=owner&r=links',fail);form.get_by_role('button',name='Создать ограниченную ссылку',exact=True).click();expect(page.locator('#po-message')).to_have_text('SYNTHETIC not saved');page.locator('.owner-shortcuts').get_by_role('link',name='Реквизиты исполнителя',exact=True).click();expect(page.locator('#workflow-status')).to_contain_text('Сначала сохраните');self.assertIn('stage=details',page.url);self.assertEqual(len(self.smtp.messages),0);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_prospect_links')[0]['n'],before);browser.close()
 def test_edits_while_save_is_in_flight_are_not_marked_as_saved(self):
  oid=self.start_order();self.smtp.messages.clear()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page,form=self.page_form(browser,oid)
   def edit(route):
    if route.request.method=='POST':form.get_by_label('Срок в часах: 1–168',exact=True).fill('48')
    route.continue_()
   page.route('**/prospect-api.php?mode=owner&r=links',edit);form.get_by_role('button',name='Создать ограниченную ссылку',exact=True).click();expect(page.locator('#po-message')).to_contain_text('SMTP принял письмо');self.assertEqual(len(self.smtp.messages),1);self.assertEqual(form.get_by_label('Срок в часах: 1–168',exact=True).input_value(),'48');page.locator('.owner-shortcuts').get_by_role('link',name='Реквизиты исполнителя',exact=True).click();expect(page.locator('#workflow-status')).to_contain_text('Сначала сохраните');self.assertIn('stage=details',page.url);browser.close()
for name in dir(unified.UnifiedWorkspace):
 if name.startswith('test_'):setattr(SavedForms,name,None)
