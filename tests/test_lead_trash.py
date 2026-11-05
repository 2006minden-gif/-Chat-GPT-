"""Actual owner trash/restore/permanent-delete UI; synthetic isolated leads only."""
import os,secrets,requests
from playwright.sync_api import sync_playwright,expect
import test_unified_workspace as unified
class LeadTrash(unified.UnifiedWorkspace):
 def act(self,lid,action,version,**extra):
  return self.owner.post(self.base+'/api.php?r=leads/'+str(lid)+'/'+action,json={'version':version,'confirm':True,**extra})
 def test_trash_restore_versions_authorization_and_linked_records_survive(self):
  oid=self.start_order();linked=self.f.sql('SELECT lead_id FROM nd_lc_inquiry_orders WHERE order_id=?',params=[oid])[0]['lead_id'];lid=self.lead();url=self.base+'/api.php?r=leads/'+str(lid)
  anon=requests.post(url+'/trash',json={'version':1,'confirm':True});self.assertEqual(anon.status_code,401)
  bad=requests.Session();bad.cookies.update(self.owner.cookies);self.assertEqual(bad.post(url+'/trash',json={'version':1,'confirm':True}).status_code,403)
  self.assertEqual(self.act(lid,'trash',1,confirm=False).status_code,422);self.assertEqual(self.act(lid,'purge',1,confirm_permanent=True).status_code,409)
  self.assertEqual(self.act(lid,'trash',999).status_code,409)
  self.assertEqual(self.act(lid,'trash',1).status_code,200);self.assertEqual(self.act(lid,'trash',1).status_code,409)
  patch=self.owner.patch(url,json={'version':2,'status':'Новая','notes':'','next_step':''});self.assertEqual(patch.status_code,409)
  active=self.owner.get(self.base+'/api.php?r=crm/leads').json()['items'];self.assertNotIn(lid,[int(x['id']) for x in active]);trash=self.owner.get(self.base+'/api.php?r=crm/leads&archived=true').json()['items'];self.assertIn(lid,[int(x['id']) for x in trash])
  self.assertEqual(self.act(lid,'restore',2).status_code,200);self.assertEqual(self.f.sql('SELECT status FROM nd_leads WHERE id=?',params=[lid])[0]['status'],'Новая')
  self.assertEqual(self.act(linked,'trash',1).status_code,200);blocked=self.act(linked,'purge',2,confirm_permanent=True);self.assertEqual(blocked.status_code,409,blocked.text);self.assertEqual(blocked.json()['error_code'],'lead_delete_linked');self.assertEqual(self.fg(oid).status_code,200);self.assertEqual(self.act(linked,'restore',2).status_code,200)
  self.assertEqual(self.act(lid,'trash',3).status_code,200);self.assertEqual(self.act(lid,'purge',4,confirm_permanent=False).status_code,422);self.assertEqual(self.act(lid,'purge',4,confirm_permanent=True).status_code,200);self.assertEqual(self.f.sql('SELECT * FROM nd_leads WHERE id=?',params=[lid]),[]);self.assertGreater(len(self.f.sql("SELECT id FROM nd_activity_history WHERE action='lead_purged'")),0)
 def test_browser_visible_trash_cancel_restore_and_permanent_confirmation(self):
  self.prepare_synthetic_owner();lid=self.lead()
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=self.session_page(browser);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(self.base+'/studio.php');card=page.locator('[data-lead-id="'+str(lid)+'"]');card.get_by_role('button',name='Удалить',exact=True).click();modal=page.locator('#lead-removal');modal.get_by_role('button',name='Отмена',exact=True).click();expect(card).to_be_visible();card.get_by_role('button',name='Удалить',exact=True).click();modal.locator('input[type=checkbox]').check();modal.get_by_role('button',name='В корзину',exact=True).click();expect(card).to_have_count(0);page.get_by_role('button',name='Корзина',exact=False).click();expect(card).to_be_visible();page.reload();expect(card).to_be_visible();card.get_by_role('button',name='Восстановить',exact=True).click();modal.locator('input[type=checkbox]').check();modal.get_by_role('button',name='Восстановить',exact=True).click();expect(card).to_have_count(0);page.get_by_role('button',name='Заявки',exact=True).click();expect(card).to_be_visible();card.get_by_role('button',name='Удалить',exact=True).click();modal.locator('input[type=checkbox]').check();modal.get_by_role('button',name='В корзину',exact=True).click();expect(card).to_have_count(0);page.get_by_role('button',name='Корзина',exact=False).click();card.get_by_role('button',name='Удалить навсегда',exact=True).click();modal.get_by_role('button',name='Удалить навсегда',exact=True).click();expect(modal).to_be_visible();modal.locator('input[type=checkbox]').check();modal.get_by_role('button',name='Удалить навсегда',exact=True).click();expect(card).to_have_count(0);self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);page.screenshot(path='/tmp/neuro-trash-mobile.png',full_page=True);browser.close()
for name in dir(unified.UnifiedWorkspace):
 if name.startswith('test_'):setattr(LeadTrash,name,None)
