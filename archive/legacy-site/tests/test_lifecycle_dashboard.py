"""Owner dashboard projects actual lifecycle obligations, never a customer feed."""
import os,requests
import test_order_lifecycle as orders

class LifecycleDashboard(orders.OrderLifecycle):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();cls.f.config["order_lifecycle_enabled"]=True;cls.f.write_config()
 def dashboard(self):
  r=self.owner.get(self.base+'/api.php?r=crm/dashboard');self.assertEqual(r.status_code,200,r.text);return r.json()['lifecycle']
 def test_actual_material_gates_next_action_role_boundary_and_mobile(self):
  oid,items=self.flow_ready();d=self.dashboard();self.assertEqual(d['counts']['payment_claims'],0);self.assertEqual(d['counts']['receipt_tasks'],0);row=next(x for x in d['actions'] if x['order_id']==oid);self.assertEqual(row['next_action'],self.fg(oid).json()['record']['next_action']);self.assertNotIn('audit',row);self.assertNotIn('bank_details',str(d))
  r=self.must(self.fp(oid,'obligations',kind='MATERIAL',title='SYNTHETIC pending material',details='SYNTHETIC next action',required=True));iid=r['id'];self.assertEqual(self.dashboard()['counts']['missing_materials'],1);self.must(self.fp(oid,'obligations/'+str(iid)+'/submit',version=1));self.must(self.fp(oid,'obligations/'+str(iid)+'/verify',version=2));self.assertEqual(self.dashboard()['counts']['missing_materials'],0)
  self.assertEqual(requests.get(self.base+'/api.php?r=crm/dashboard').status_code,401);self.assertEqual(self.customer.get(self.base+'/api.php?r=crm/dashboard').status_code,401)
  from playwright.sync_api import sync_playwright
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':375,'height':812});errors=[];p.on('pageerror',lambda e:errors.append(str(e)));p.goto(self.base+'/studio.php');p.locator('#password').fill(self.f.password);p.locator('#login-form button').click();p.locator('#dashboard').wait_for(state='visible');p.goto(self.base+'/workspace.php');p.get_by_text('Следующие действия по заказам',exact=True).wait_for();self.assertFalse(p.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);b.close()

for name in dir(orders.OrderLifecycle):
 if name.startswith('test_'):setattr(LifecycleDashboard,name,None)
