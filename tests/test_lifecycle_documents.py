"""Synthetic documents only: no real legal approvals, fiscal receipts or payments."""
import json,secrets,subprocess
import test_catalog as catalog

class LifecycleDocuments(catalog.Catalog):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-documents.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
 def lp(self,route,s=None,**data):
  s=s or self.owner;data.setdefault('request_key',secrets.token_hex(32));return s.post(self.base+'/lifecycle-api.php?mode='+('owner' if s is self.owner else 'customer')+'&r='+route,json=data)
 def lg(self,route,s=None):
  s=s or self.owner;return s.get(self.base+'/lifecycle-api.php?mode='+('owner' if s is self.owner else 'customer')+'&r='+route)
 def template_ready(self):
  r=self.lp('templates/initial');self.assertEqual(r.status_code,200,r.text);tid=r.json()['id'];t=self.lg('templates/'+str(tid)).json()['record'];
  if t['state']=='APPROVED':return t
  self.assertEqual(t['state'],'NEEDS_LEGAL_REVIEW')
  r=self.lp('templates/'+str(tid)+'/approve',version=int(t['version']),checksum=t['checksum'],confirm=True,reason='SYNTHETIC TEST approval, not a production legal decision');self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def inputs(self):
  labels=self.lg('settings').json()['fields'];d={k:'SYNTHETIC TEST '+v for k,v in labels.items()};prefix='9900000000';digit=lambda text,w:str(sum(int(a)*b for a,b in zip(text,w))%11%10);inn=prefix+digit(prefix,[7,2,4,10,3,5,9,4,6,8]);inn+=digit(inn,[3,7,2,4,10,3,5,9,4,6,8]);d.update(owner_inn=inn,client_type='person',client_inn='',bank_account='9'*20,bank_bik='9'*9,bank_corr='8'*20,owner_name='SYNTHETIC owner',client_name='TEST <script>alert(1)</script>');
  rows=self.f.sql("SELECT calculation_json FROM nd_quotations WHERE project_id=? AND state='APPROVED' ORDER BY id DESC LIMIT 1",params=[self.project_id]);total=int(json.loads(rows[0]['calculation_json'])['selling_minor']) if rows else 28875;deposit=total//2
  d['payment_schedule']=json.dumps([{'label':'SYNTHETIC deposit','amount':f'{deposit//100}.{deposit%100:02}','due_on':'2099-01-01','gate':'production','stage_id':None},{'label':'SYNTHETIC balance','amount':f'{(total-deposit)//100}.{(total-deposit)%100:02}','due_on':'2099-02-01','gate':'handover','stage_id':None}]);return d
 def prepare(self):
  t=self.template_ready();q=self.approved_price();minor=int(q['calculation']['selling_minor']);oid=self.insert("INSERT INTO nd_orders(customer_id,number,title,total_amount,currency) VALUES (?,?,'SYNTHETIC order',?,'RUB')",'nd_orders',[self.customer_id,'TEST-'+secrets.token_hex(8),f'{minor//100}.{minor%100:02}']);self.f.sql('UPDATE nd_projects SET order_id=?,version=version+1 WHERE id=?',params=[oid,self.project_id]);q=self.approved_price();return t,q
 def generate(self,t,q,**extra):
  return self.lp('documents',template_id=int(t['id']),project_id=self.project_id,quotation_id=int(q['id']),fields=self.inputs(),owner_reviewed=True,**extra)
 def action(self,b,action,s=None,**extra):return self.lp('documents/'+str(b['id'])+'/'+action,s,version=int(b['version']),checksum=b['generated_hash'],reason='SYNTHETIC verification evidence',confirm=True,**extra)
 def test_lc_01_unapproved_price_template_missing_fields_and_roles(self):
  t,q=self.prepare();self.assertEqual(self.lp('templates/initial',self.customer).status_code,403);self.assertEqual(self.lg('templates',self.customer).status_code,403)
  d=self.inputs();del d['subject'];r=self.lp('documents',template_id=int(t['id']),project_id=self.project_id,quotation_id=int(q['id']),fields=d,owner_reviewed=True);self.assertEqual(r.status_code,422,r.text)
  draft=self.lp('templates',kind=t['kind'],title='SYNTHETIC draft',clauses=t['clauses']).json()['record'];self.assertEqual(self.generate(draft,q).status_code,409)
  self.f.sql("UPDATE nd_quotations SET state='DRAFT' WHERE id=?",params=[q['id']]);self.assertEqual(self.generate(t,q).status_code,409)
 def test_lc_02_immutable_signed_copy_scoped_print_and_idempotency(self):
  t,q=self.prepare();payload=dict(template_id=int(t['id']),project_id=self.project_id,quotation_id=int(q['id']),fields=self.inputs(),owner_reviewed=True,request_key=secrets.token_hex(32));r=self.lp('documents',**payload);self.assertEqual(r.status_code,200,r.text);b=r.json()['record'];self.assertEqual(self.lp('documents',**payload).json()['id'],b['id']);self.assertEqual(self.lg('documents/'+str(b['id']),self.customer).status_code,404)
  sent=self.action(b,'send');self.assertEqual(sent.status_code,200,sent.text);b=sent.json()['record'];self.assertEqual(self.lg('documents/'+str(b['id']),self.stranger).status_code,404);url=self.base+'/collab-print.php?mode=customer&id='+str(b['revision_id']);html=self.customer.get(url);self.assertEqual(html.status_code,200,html.text);self.assertIn('&lt;script&gt;',html.text);self.assertNotIn('<script>alert(1)',html.text);self.assertEqual(self.stranger.get(url).status_code,404)
  rev=self.f.sql('SELECT document_id FROM nd_cc_revisions WHERE id=?',params=[b['revision_id']])[0];self.assertEqual(self.owner.post(self.base+'/api.php?r=crm/collab/documents/'+str(rev['document_id'])+'/revise',json={'version':1,'request_key':secrets.token_hex(32)}).status_code,409)
  self.assertEqual(self.action(b,'verify').status_code,409);b=self.action(b,'response',self.customer).json()['record'];self.assertEqual(b['state'],'CLIENT_RESPONSE');self.assertIsNone(b['verified_at'])
  # The upload is deliberately marked synthetic; it is not a real signed agreement.
  r=self.customer.post(self.base+'/customer-api.php?r=collab/upload',data={'project_id':str(self.project_id),'request_key':secrets.token_hex(32)},files={'file':('SYNTHETIC-not-a-real-signature.pdf',self.pdf(),'application/pdf')});self.assertEqual(r.status_code,200,r.text);fid=int(r.json()['file']['id']);b=self.action(b,'signed-copy',self.customer,file_id=fid).json()['record'];self.assertEqual(b['state'],'SIGNED_COPY_SUBMITTED');self.assertEqual(self.action(b,'verify',self.customer).status_code,403)
  b=self.action(b,'verify').json()['record'];self.assertEqual(b['state'],'AGREED');self.assertIsNotNone(b['verified_at']);self.assertEqual(self.action(b,'reject').status_code,409)
  self.assertEqual(self.lg('documents/'+str(b['id']),self.customer).json()['record']['generated_hash'],b['generated_hash'])
  self.assertEqual(self.owner.post(self.base+'/api.php?r=crm/collab/files/'+str(fid),json={'request_key':secrets.token_hex(32),'version':1,'visibility':'internal','archived':True}).status_code,409)
  self.f.sql('UPDATE nd_cc_revisions SET body=? WHERE id=?',params=[json.dumps({'title':'TAMPERED'}),b['revision_id']]);self.assertEqual(self.customer.get(url).status_code,503)
 def test_lc_03_template_injection_csrf_and_stale_approval(self):
  t=self.template_ready();clauses=t['clauses'].copy();clauses['subject']='{{unknown}}';self.assertEqual(self.lp('templates',kind=t['kind'],title='Bad',clauses=clauses).status_code,422)
  csrf=self.owner.headers.pop('X-CSRF-Token')
  try:self.assertEqual(self.lp('templates/initial').status_code,403)
  finally:self.owner.headers['X-CSRF-Token']=csrf
  self.assertEqual(self.lp('templates/'+str(t['id'])+'/retire',version=1,checksum=t['checksum'],confirm=True,reason='SYNTHETIC').status_code,409)

 def test_lc_04_mobile_browser_owner_library(self):
  import os
  from playwright.sync_api import sync_playwright
  t=self.template_ready()
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':375,'height':812});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(self.base+'/studio.php');page.locator('#password').fill(self.f.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
   page.goto(self.base+'/documents.php?mode=owner#template/'+str(t['id']));page.get_by_role('button',name='Сохранить как новую версию-черновик').wait_for();self.assertEqual(errors,[]);self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));browser.close()

 def test_lc_05_corrupt_historical_retry_never_repeats_mutation(self):
  k=secrets.token_hex(32);self.assertEqual(self.lp('templates/initial',request_key=k).status_code,200);before=self.f.sql('SELECT COUNT(*) n FROM nd_lc_templates')[0]['n'];self.f.sql('UPDATE nd_crm_requests SET result=? WHERE request_key=?',params=['{',k]);r=self.lp('templates/initial',request_key=k);self.assertEqual(r.status_code,409,r.text);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_templates')[0]['n'],before)

for name in dir(catalog.Catalog):
 if name.startswith('test_'):setattr(LifecycleDocuments,name,None)
