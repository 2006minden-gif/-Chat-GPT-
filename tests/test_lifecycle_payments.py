"""Synthetic bank data in isolated CI DB only; no network banking or fiscal receipt output."""
import json,secrets,subprocess
import test_lifecycle_documents as docs

class LifecyclePayments(docs.LifecycleDocuments):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-finance.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
 def approved_template(self,kind):
  base=self.template_ready();t=self.lp('templates',kind=kind,title='SYNTHETIC '+kind,clauses=base['clauses']).json()['record']
  for action in ['review','approve']:
   r=self.lp('templates/'+str(t['id'])+'/'+action,version=int(t['version']),checksum=t['checksum'],confirm=True,reason='SYNTHETIC test only, not a legal production decision');self.assertEqual(r.status_code,200,r.text);t=r.json()['record']
  return t
 def agreement(self):
  _,q=self.prepare();t=self.approved_template('agreement');r=self.generate(t,q);self.assertEqual(r.status_code,200,r.text);b=r.json()['record'];r=self.action(b,'send');self.assertEqual(r.status_code,200,r.text);b=r.json()['record']
  r=self.customer.post(self.base+'/customer-api.php?r=collab/upload',data={'project_id':str(self.project_id),'request_key':secrets.token_hex(32)},files={'file':('SYNTHETIC-not-real-agreement.pdf',self.pdf(),'application/pdf')});self.assertEqual(r.status_code,200,r.text)
  b=self.action(b,'signed-copy',self.customer,file_id=int(r.json()['file']['id'])).json()['record'];b=self.action(b,'verify').json()['record'];return b
 def activate(self):
  b=self.agreement();t=self.approved_template('invoice');r=self.lp('finance/agreements/'+str(b['id'])+'/activate',invoice_template_id=int(t['id']),confirm=True);self.assertEqual(r.status_code,200,r.text);data=self.lg('finance').json();items=[i for i in data['items'] if int(i['order_id'])==int(b['order_id'])];return b,sorted(items,key=lambda i:int(i['id']))
 def bank(self,i,**extra):
  d=dict(amount='10.00',paid_at='2026-01-10 12:00:00',payer='SYNTHETIC payer',reference='SYNTHETIC bank reference',bank_entry_id='TEST-'+secrets.token_hex(16),method='bank_other',reason='SYNTHETIC test of manual bank attestation, no real transfer',confirm_actual_bank=True,service_description='SYNTHETIC development deposit');d.update(extra);return self.lp('finance/invoices/'+str(i['id'])+'/verify',**d)
 def test_pay_01_report_is_not_payment_partial_duplicate_bank_and_receipt(self):
  b,items=self.activate();i=items[0];claim=dict(amount='10.00',paid_at='2026-01-10 12:00:00',payer='SYNTHETIC payer',reference='SYNTHETIC client claim');r=self.lp('finance/invoices/'+str(i['id'])+'/claim',self.customer,**claim);self.assertEqual(r.status_code,200,r.text);cid=r.json()['id'];self.assertFalse(r.json()['payment_verified']);self.assertEqual(self.lp('finance/invoices/'+str(i['id'])+'/claim',self.customer,**claim).json()['id'],cid)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_payment_transactions t JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?',params=[i['id']])[0]['n'],0)
  self.assertEqual(self.lg('finance',self.stranger).json()['items'],[])
  entry='TEST-'+secrets.token_hex(16);k=secrets.token_hex(32);r=self.bank(i,claim_id=cid,bank_entry_id=entry,request_key=k);self.assertEqual(r.status_code,200,r.text);tx=r.json()['id'];task=r.json()['receipt_task_id'];self.assertFalse(r.json()['independently_verified']);self.assertEqual(self.bank(i,claim_id=cid,bank_entry_id=entry,request_key=k).json()['id'],tx);self.assertEqual(self.bank(i,bank_entry_id=entry).status_code,409)
  after=self.lg('finance').json();updated=next(x for x in after['items'] if x['id']==i['id']);self.assertEqual(updated['balance']['paid_minor'],1000);self.assertEqual(updated['balance']['outstanding_minor'],int(i['total_minor'])-1000);receipt=next(x for x in after['receipts'] if int(x['id'])==task);self.assertEqual(receipt['state'],'MISSING');self.assertEqual(int(receipt['amount_minor']),1000);self.assertEqual(receipt['due_at'],'2026-02-09 21:59:59')
  # A local PDF or a claim cannot self-assert an official FNS receipt.
  self.assertEqual(self.lp('finance/receipts/'+str(task)+'/issue',version=1,reason='Local PDF',external_reference='NOT-A-FISCAL-RECEIPT',file_id=1).status_code,422)
  self.assertEqual(self.lp('finance/receipts/'+str(task)+'/issue',self.customer,version=1,confirm_issued_in_mytax=True,reason='Forbidden').status_code,403)
  self.assertEqual(self.lp('finance/receipts/'+str(task)+'/issue',version=1,confirm_issued_in_mytax=True,reason='Invalid source',external_reference='NOT-A-RECEIPT',issued_at='2026-01-10 12:00:00',official_url='https://lknpd.nalog.ru.evil.invalid/receipt').status_code,422)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_receipt_evidence WHERE task_id=?',params=[task])[0]['n'],0)
 def test_pay_02_deposit_balance_overpayment_refund_and_no_income_recount(self):
  b,items=self.activate();amount=lambda n:f'{n//100}.{n%100:02}';total=0;attempt=None
  for i in items:
   n=int(i['total_minor']);total+=n;r=self.bank(i,amount=amount(n));self.assertEqual(r.status_code,200,r.text);attempt=r.json()['attempt_id']
  data=self.lg('finance').json();own=[x for x in data['items'] if int(x['order_id'])==int(b['order_id'])];self.assertEqual(sum(x['balance']['paid_minor'] for x in own),total);self.assertEqual(sum(int(x['amount_minor']) for x in data['receipts'] if int(x['order_id'])==int(b['order_id'])),total)
  i=items[-1];r=self.bank(i,amount='1.00');self.assertEqual(r.status_code,200,r.text);extra_attempt=r.json()['attempt_id'];updated=next(x for x in self.lg('finance').json()['items'] if x['id']==i['id']);self.assertEqual(updated['overpayment_minor'],100)
  refund=dict(amount='1.00',paid_at='2026-01-11 12:00:00',reference='SYNTHETIC refund',bank_entry_id='REFUND-'+secrets.token_hex(16),reason='SYNTHETIC no real refund, isolated test',confirm_actual_bank=True);k=secrets.token_hex(32);r=self.lp('finance/payments/'+str(extra_attempt)+'/refund',request_key=k,**refund);self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['refund_initiated_by_application']);self.assertEqual(self.lp('finance/payments/'+str(extra_attempt)+'/refund',request_key=k,**refund).json()['id'],r.json()['id']);self.assertEqual(self.lp('finance/payments/'+str(extra_attempt)+'/refund',**refund).status_code,422)
  updated=next(x for x in self.lg('finance').json()['items'] if x['id']==i['id']);self.assertEqual(updated['overpayment_minor'],0);self.assertEqual(updated['balance']['refunded_minor'],100)
  task=self.f.sql('SELECT r.state FROM nd_lc_receipt_tasks r JOIN nd_payment_transactions t ON t.id=r.transaction_id WHERE t.attempt_id=?',params=[extra_attempt])[0];self.assertEqual(task['state'],'CORRECTION_NEEDED')
 def test_pay_03_deadlines_invoice_scope_and_schedule_invariants(self):
  b,items=self.activate();i=items[0];self.assertEqual(self.stranger.get(self.base+'/manual-invoice.php?mode=customer&id='+str(i['id'])).status_code,404);html=self.customer.get(self.base+'/manual-invoice.php?mode=customer&id='+str(i['id']));self.assertEqual(html.status_code,200,html.text);self.assertIn('Не является официальным чеком',html.text)
  self.assertEqual(self.lp('finance/invoices/'+str(i['id'])+'/verify',self.customer,confirm_actual_bank=True).status_code,403)
  for method in ['cash','electronic']:
   r=self.bank(i,method=method);self.assertEqual(r.status_code,200,r.text);task=self.f.sql('SELECT paid_at,due_at FROM nd_lc_receipt_tasks WHERE id=?',params=[r.json()['receipt_task_id']])[0];self.assertEqual(task['paid_at'],task['due_at'])
  # No real receipt is fabricated during this test suite.
  self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_lc_receipt_evidence WHERE action IN ('ISSUANCE_RECORDED','CORRECTION_RECORDED')")[0]['n'],0)

 def test_pay_04_mobile_client_claim_form_and_owner_receipt_tasks(self):
  import os
  from playwright.sync_api import sync_playwright
  self.activate()
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':375,'height':812});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   page.goto(self.base+'/studio.php');page.locator('#password').fill(self.f.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
   page.goto(self.base+'/finance.php?mode=owner');page.get_by_text('Проверка реального поступления',exact=True).first.wait_for();page.get_by_text('Проверка реального поступления',exact=True).first.click();page.locator('input[name=bank_entry_id]').first.wait_for(state='visible');self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);browser.close()

 def test_pay_05_concurrent_independent_bank_verifications_create_one_income(self):
  import subprocess
  _,items=self.activate();invoice=items[0];entry='SYNTHETIC-CONCURRENT-'+secrets.token_hex(16)
  code='$v=json_decode(stream_get_contents(STDIN),true);require $v["root"]."/private/app.php";require $v["root"]."/private/lifecycle/routes.php";$a=["type"=>"owner","id"=>1];$d=$v["data"];try{$r=lc_mutation($a,"lifecycle/finance/invoices/".$v["invoice"]."/verify",$d,fn()=>lc_verify_bank($a,$v["invoice"],$d));echo json_encode(["ok"=>true,"id"=>$r["id"]]);}catch(PDOException $e){echo json_encode(["conflict"=>$e->getCode()==="23000"||$e->getCode()==="40001"]);}catch(CrmFailure $e){echo json_encode(["conflict"=>$e->status===409]);}'
  processes=[]
  for _ in range(2):
   d=dict(request_key=secrets.token_hex(32),amount='1.00',paid_at='2026-01-10 12:00:00',payer='SYNTHETIC payer',reference='SYNTHETIC simultaneous record',bank_entry_id=entry,method='cash',reason='SYNTHETIC concurrency test, no real transfer',confirm_actual_bank=True,service_description='SYNTHETIC deposit')
   p=subprocess.Popen([self.f.php,'-r',code],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True);p.stdin.write(json.dumps({'root':str(self.f.path),'data':d,'invoice':int(invoice['id'])}));p.stdin.close();processes.append(p)
  results=[]
  for p in processes:
   p.wait(timeout=30);self.assertEqual(p.returncode,0);results.append(json.loads(p.stdout.read()));p.stdout.close();p.stderr.close()
  self.assertEqual(sum(r.get('ok',False) for r in results),1);self.assertEqual(sum(r.get('conflict',False) for r in results),1)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_payment_transactions t JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?',params=[invoice['id']])[0]['n'],1)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_receipt_tasks r JOIN nd_payment_transactions t ON t.id=r.transaction_id JOIN nd_payment_attempts p ON p.id=t.attempt_id WHERE p.invoice_id=?',params=[invoice['id']])[0]['n'],1)

for name in dir(docs.LifecycleDocuments):
 if name.startswith('test_'):setattr(LifecyclePayments,name,None)
