"""Stage 7: isolated MySQL 5.7, actual HTTP, deterministic provider transport (NOT real sandbox)."""
import base64
import hashlib
import json
import secrets
import subprocess
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import requests
from test_collaboration import Collaboration

class ProviderFixture(BaseHTTPRequestHandler):
 payments={};refunds={};keys={};mode='pending';calls=[]
 def log_message(self,*args):pass
 def respond(self,obj,status=200):
  self.send_response(status);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(obj).encode())
 def do_POST(self):
  data=json.loads(self.rfile.read(int(self.headers['Content-Length'])));key=self.headers.get('Idempotence-Key');self.calls.append((self.path,key))
  if self.mode=='unavailable':return self.respond({'type':'error'},503)
  if self.path=='/payments':
   if key not in self.keys:
    pid='pay_'+secrets.token_hex(10);self.keys[key]=pid;self.payments[pid]={'id':pid,'test':True,'status':'pending','amount':data['amount'],'metadata':data['metadata'],'confirmation':{'confirmation_url':'https://yookassa.ru/checkout/'+pid}}
   return self.respond(self.payments[self.keys[key]])
  if self.path=='/refunds':
   if key not in self.keys:
    rid='ref_'+secrets.token_hex(10);self.keys[key]=rid;self.refunds[rid]={'id':rid,'payment_id':data['payment_id'],'amount':data['amount'],'status':'pending'}
   return self.respond(self.refunds[self.keys[key]])
  self.respond({},404)
 def do_GET(self):
  obj=(self.payments if self.path.startswith('/payments/') else self.refunds).get(self.path.rsplit('/',1)[-1]);self.respond(obj or {},200 if obj else 404)

class Billing(Collaboration):
 # Inherit setup helpers, not the Stage 6 tests (discovery methods removed below).
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-billing.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  cls.provider=ThreadingHTTPServer(('127.0.0.1',0),ProviderFixture);threading.Thread(target=cls.provider.serve_forever,daemon=True).start();cls.addClassCleanup(cls.provider.server_close);cls.addClassCleanup(cls.provider.shutdown)
  cls.f.config.update(billing_enabled=True,billing_merchant={'approved':True,'legal_name':'Синтетический исполнитель','registration':'Только тест','address':'Тестовый адрес','tax_treatment':'Проверяется только тестом','payment_instructions':'Тестовые условия','retention_policy':'Тестовый срок','number_prefix':'TEST'},billing_test_mode=True,billing_test_transport='http://127.0.0.1:'+str(cls.provider.server_port),billing_provider={'enabled':True,'sandbox_approved':True,'name':'yookassa','mode':'sandbox','shop_id':'fixture-shop','secret_key':'test_fixture_transport_only'})
  cls.f.write_config()
 def setUp(self):
  super().setUp();ProviderFixture.mode='pending';self.order=self.insert("INSERT INTO nd_orders(customer_id,number,title,total_amount,status) VALUES (?,?,'Синтетическая услуга','1000.00','confirmed')",'nd_orders',[self.customer_id,'FIX-'+secrets.token_hex(6)])
 def url(self,s,route):return self.base+('/api.php?r=crm/billing/' if s is self.owner else '/customer-api.php?r=billing/')+route
 def invoice(self,amount='100.00',issue=True):
  r=self.post(self.owner,'invoices',customer_id=self.customer_id,order_id=self.order,due_on='2026-01-01',lines=[{'description':'Разработка <script>alert(1)</script>','quantity':'1','unit_price':amount}]);self.assertEqual(r.status_code,200,r.text);i=r.json()['record']
  if issue:
   r=self.post(self.owner,f'invoices/{i["id"]}/issue',version=int(i['version']),confirm=True);self.assertEqual(r.status_code,200,r.text);i=r.json()['record']
  return i
 def detail(self,i,s=None):
  r=self.get(s or self.owner,'invoices/'+str(i['id']));self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def pay(self,i):
  r=self.post(self.customer,f'invoices/{i["id"]}/pay',confirm=True);self.assertEqual(r.status_code,200,r.text);return r.json()
 def settle(self,p):
  row=self.f.sql('SELECT * FROM nd_payment_attempts WHERE id=?',params=[p['id']])[0];o=ProviderFixture.payments[row['provider_id']];o.update(status='succeeded',paid=True,captured_at='2026-10-25T00:00:00Z');return row,o
 def callback(self,row,**extra):
  data={'type':'notification','event':'payment.succeeded','object':{'id':row['provider_id'],'status':'succeeded',**extra}};return requests.post(self.base+'/payment-webhook.php',json=data)
 def test_20_invoice_lifecycle_decimal_snapshot_correction(self):
  i=self.invoice(issue=False);self.assertEqual(self.get(self.customer,'invoices/'+str(i['id'])).status_code,404)
  payload={'version':int(i['version']),'confirm':True,'request_key':secrets.token_hex(32)};r=self.post(self.owner,f'invoices/{i["id"]}/issue',**payload);self.assertEqual(r.status_code,200,r.text);number=r.json()['record']['number'];self.assertEqual(self.post(self.owner,f'invoices/{i["id"]}/issue',**payload).json()['record']['number'],number)
  i=self.detail(i);self.assertEqual(int(i['total_minor']),10000);self.assertTrue(i['snapshot_hash']);old=i['snapshot'];self.f.sql("UPDATE nd_customers SET name='Переименован' WHERE id=?",params=[self.customer_id]);self.assertEqual(self.detail(i)['snapshot'],old)
  self.assertEqual(self.post(self.owner,f'invoices/{i["id"]}/save',version=int(i['version'])).status_code,409)
  r=self.post(self.owner,f'invoices/{i["id"]}/adjust',version=int(i['version']),confirm=True,amount='10.01',reason='Согласованное уменьшение');self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['record']['balance']['outstanding_minor'],8999)
  self.assertEqual(self.detail(i)['snapshot'],old)
  self.assertEqual(self.post(self.owner,f'invoices/{i["id"]}/adjust',version=int(i['version']),confirm=True,amount='1',reason='Старый запрос').status_code,409)
  q=self.f.php_eval('require $v["root"]."/private/billing/routes.php";echo json_encode(bill_lines(["lines"=>[["description"=>"x","quantity"=>"1.005","unit_price"=>"1.00"]]]));',{'root':str(self.f.path)})
  self.assertEqual(json.loads(q)[1],101)
 def test_21_payment_authority_duplicate_webhooks_reconcile(self):
  i=self.invoice();p=self.pay(i);self.assertEqual(p['state'],'pending');self.assertEqual(self.detail(i)['balance']['paid_minor'],0)
  row=self.f.sql('SELECT * FROM nd_payment_attempts WHERE id=?',params=[p['id']])[0]
  self.assertEqual(self.callback(row).status_code,200);self.assertEqual(self.detail(i)['balance']['paid_minor'],0) # forged succeeded hint is ignored
  # Different click/idempotency key reuses the same pending payment.
  self.assertEqual(self.pay(i)['id'],p['id']);row,o=self.settle(p)
  from concurrent.futures import ThreadPoolExecutor
  with ThreadPoolExecutor(max_workers=3) as pool:rs=list(pool.map(lambda _:self.callback(row),range(3)))
  self.assertTrue(all(r.status_code==200 for r in rs),[r.text for r in rs]);self.assertEqual(self.detail(i)['balance']['paid_minor'],10000)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_payment_transactions WHERE attempt_id=?',params=[p['id']])[0]['n'],1)
  self.assertEqual(self.post(self.customer,f'invoices/{i["id"]}/pay',confirm=True).status_code,409)
  second=self.invoice();p2=self.pay(second);self.settle(p2);r=self.post(self.owner,f'payments/{p2["id"]}/reconcile');self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.detail(second)['balance']['status'],'paid')
 def test_22_mismatch_live_bad_redirect_and_unknown_hook(self):
  i=self.invoice();p=self.pay(i);row,o=self.settle(p);original=dict(o)
  for change in [{'test':False},{'amount':{'value':'999.00','currency':'RUB'}},{'amount':{'value':'100.00','currency':'USD'}},{'metadata':{'nd_attempt':'wrong'}},{'confirmation':{'confirmation_url':'https://evil.invalid/'}}]:
   o.clear();o.update(original);o.update(change);r=self.callback(row);self.assertIn(r.status_code,[409,422],r.text);self.assertEqual(self.detail(i)['balance']['paid_minor'],0)
  o.clear();o.update(original);self.assertEqual(requests.post(self.base+'/payment-webhook.php',json={'object':{'id':'unknown'},'event':'payment.succeeded'}).status_code,404)
  self.assertEqual(requests.post(self.base+'/payment-webhook.php',data='x'*9000,headers={'Content-Type':'application/json'}).status_code,413)
  chunked=requests.post(self.base+'/payment-webhook.php',data=iter([b'x'*4500,b'x'*4500]),headers={'Content-Type':'application/json'});self.assertEqual(chunked.status_code,413,chunked.text)
  self.assertEqual(requests.post(self.base+'/payment-webhook.php',data='{',headers={'Content-Type':'application/json'}).status_code,400)
  o['status']='pending';o['paid']=False;self.assertEqual(self.post(self.owner,f'invoices/{i["id"]}/cancel',version=int(self.detail(i)['version']),confirm=True).status_code,409)
 def test_23_refunds_reservations_duplicate_failed_and_balance(self):
  i=self.invoice();p=self.pay(i);row,o=self.settle(p);self.assertEqual(self.callback(row).status_code,200)
  payload={'amount':'25.00','reason':'Тестовый возврат','confirm':True,'request_key':secrets.token_hex(32)};r=self.post(self.owner,f'payments/{p["id"]}/refund',**payload);self.assertEqual(r.status_code,200,r.text);rid=r.json()['id'];self.assertEqual(r.json()['state'],'pending');self.assertEqual(self.detail(i)['balance']['refunded_minor'],0)
  self.assertEqual(self.post(self.owner,f'payments/{p["id"]}/refund',**payload).json()['id'],rid)
  rr=self.f.sql('SELECT * FROM nd_refunds WHERE id=?',params=[rid])[0];ProviderFixture.refunds[rr['provider_id']]['status']='succeeded';r=self.post(self.owner,f'refunds/{rid}/reconcile');self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.detail(i)['balance']['refunded_minor'],2500)
  self.assertEqual(self.post(self.owner,f'payments/{p["id"]}/refund',amount='76',reason='Лишний возврат',confirm=True).status_code,409)
  r=self.post(self.owner,f'payments/{p["id"]}/refund',amount='75',reason='Полный остаток',confirm=True);self.assertEqual(r.status_code,200,r.text);rid2=r.json()['id'];rr=self.f.sql('SELECT * FROM nd_refunds WHERE id=?',params=[rid2])[0];ProviderFixture.refunds[rr['provider_id']]['status']='canceled';self.assertEqual(self.post(self.owner,f'refunds/{rid2}/reconcile').status_code,200);self.assertEqual(self.detail(i)['balance']['refunded_minor'],2500)
 def test_24_authorization_csrf_privacy_html_and_csv(self):
  i=self.invoice();p=self.pay(i)
  for route in ['invoices/'+str(i['id'])]:self.assertEqual(self.get(self.stranger,route).status_code,404)
  self.assertEqual(self.post(self.stranger,f'payments/{p["id"]}/reconcile').status_code,404)
  self.assertEqual(self.post(self.customer,f'payments/{p["id"]}/refund',amount='1',reason='Нет доступа',confirm=True).status_code,403)
  self.assertEqual(self.get(self.customer,'report').status_code,403);self.assertEqual(self.get(self.customer,'export').status_code,403)
  r=self.owner.post(self.url(self.owner,f'invoices/{i["id"]}/cancel'),json={'confirm':True},headers={'X-CSRF-Token':'wrong'});self.assertEqual(r.status_code,403)
  url=self.base+'/invoice-document.php?id='+str(i['id']);self.assertEqual(self.stranger.get(url).status_code,404);r=self.customer.get(url+'&download=1');self.assertEqual(r.status_code,200);self.assertIn('attachment',r.headers['Content-Disposition']);self.assertIn('&lt;script&gt;',r.text);self.assertNotIn('<script>',r.text)
  self.f.sql("UPDATE nd_customers SET name='=HYPERLINK(1)' WHERE id=?",params=[self.customer_id]);r=self.get(self.owner,'export');self.assertEqual(r.status_code,200,r.text);self.assertIn("'=HYPERLINK",r.text)
  c=dict(self.f.config)
  try:
   self.f.config['billing_enabled']=False;self.f.write_config();self.assertEqual(self.get(self.owner,'invoices').status_code,503)
  finally:self.f.config=c;self.f.write_config()
 def test_25_notification_durable_dedupe_preferences_retry(self):
  i=self.invoice();rows=self.f.sql("SELECT * FROM nd_notification_outbox WHERE event_key=?",params=['invoice:'+str(i['id'])+':issued']);self.assertEqual(len(rows),4);self.assertEqual(self.get(self.customer,'notifications').status_code,200)
  self.assertFalse(any(r['record_id']==i['id'] for r in self.get(self.stranger,'notifications').json()['items']))
  self.assertEqual(self.post(self.customer,'preferences',optional_email=True).status_code,200);self.assertTrue(self.get(self.customer,'preferences').json()['optional_email'])
  r=self.post(self.owner,f'invoices/{i["id"]}/send',version=int(i['version']),confirm=True);self.assertEqual(r.status_code,200,r.text);self.assertEqual(len(self.f.sql('SELECT * FROM nd_notification_outbox WHERE event_key=?',params=['invoice:'+str(i['id'])+':issued'])),4)
  c=dict(self.f.config)
  try:
   self.f.config['billing_email_enabled']=True;self.f.write_config();self.f.sql("UPDATE nd_notification_outbox SET state='pending' WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued'])
   r=subprocess.run([self.f.php,str(self.f.path/'scripts/billing-worker.php')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr)
   notices=self.f.sql("SELECT * FROM nd_notification_outbox WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued']);self.assertTrue(all(n['attempts']==1 and n['state']=='pending' for n in notices))
   self.f.sql("UPDATE nd_notification_outbox SET attempts=4,next_attempt=UTC_TIMESTAMP() WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued']);r=subprocess.run([self.f.php,str(self.f.path/'scripts/billing-worker.php')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(all(n['state']=='failed' for n in self.f.sql("SELECT * FROM nd_notification_outbox WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued'])))
  finally:self.f.config=c;self.f.write_config()
 def test_26_timeout_retries_same_attempt_not_duplicate(self):
  i=self.invoice();ProviderFixture.mode='unavailable';payload={'request_key':secrets.token_hex(32),'confirm':True};r=self.post(self.customer,f'invoices/{i["id"]}/pay',**payload);self.assertEqual(r.status_code,503,r.text)
  row=self.f.sql('SELECT * FROM nd_payment_attempts WHERE invoice_id=?',params=[i['id']])[0];self.assertEqual(row['state'],'creating');ProviderFixture.mode='pending';r=self.post(self.customer,f'invoices/{i["id"]}/pay',**payload);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['id'],row['id']);self.assertEqual(len(self.f.sql('SELECT * FROM nd_payment_attempts WHERE invoice_id=?',params=[i['id']])),1)
 def test_27_reports_and_validation(self):
  i=self.invoice();r=self.get(self.owner,'report',customer_id=self.customer_id);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.json()['totals']['invoiced_minor'],10000);self.assertEqual(r.json()['totals']['confirmed_minor'],0)
  for value in ['-1','1e2','1,00',1.25,'0','100000000']:
   r=self.post(self.owner,'invoices',customer_id=self.customer_id,order_id=self.order,due_on='2026-01-01',lines=[{'description':'bad','quantity':'1','unit_price':value}]);self.assertEqual(r.status_code,422,(value,r.text))
  self.assertEqual(self.post(self.customer,'invoices',customer_id=self.customer_id,order_id=self.order).status_code,403)

 def test_28_browser_desktop_mobile_invoice_report_and_error(self):
  import os
  from pathlib import Path
  from playwright.sync_api import sync_playwright
  i=self.invoice();errors=[]
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   owner_context=browser.new_context(viewport={'width':1440,'height':1000});owner_context.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);pg=owner_context.new_page();pg.on('pageerror',lambda e:errors.append(str(e)));pg.on('dialog',lambda d:d.accept())
   pg.goto(self.base+'/billing.php?mode=owner#invoices/'+str(i['id']));pg.get_by_text('История платежей',exact=True).wait_for();self.assertEqual(pg.locator('#billing-error').inner_text(),'')
   pg.locator('[name=amount]').fill('10');pg.locator('[name=reason]').fill('Проверка корректировки')
   pg.route('**/api.php?r=crm/billing/invoices/*/adjust',lambda route:route.fulfill(status=200,content_type='text/html',body='<html>wrong</html>'));pg.get_by_role('button',name='Создать корректировку',exact=True).click();pg.wait_for_function("() => document.querySelector('#billing-error').textContent.includes('не подтверждено')");self.assertEqual(pg.locator('[name=reason]').input_value(),'Проверка корректировки');pg.unroute('**/api.php?r=crm/billing/invoices/*/adjust')
   pg.goto(self.base+'/billing.php?mode=owner#new');pg.get_by_role('heading',name='Создать счёт',exact=True).wait_for();pg.get_by_role('combobox',name='Клиент',exact=True).select_option(str(self.customer_id));pg.get_by_role('combobox',name='Заказ',exact=True).select_option(str(self.order));pg.locator('[name=unit_price]').fill('33.33');pg.get_by_role('button',name='Сохранить черновик',exact=True).click();pg.wait_for_function("() => location.hash.startsWith('#invoices/')")
   pg.get_by_role('button',name='Выставить счёт',exact=True).click();pg.get_by_text('История платежей',exact=True).wait_for();pg.wait_for_load_state('networkidle')
   pg.goto(self.base+'/billing.php?mode=owner#report');pg.get_by_text('Подтверждённые поступления по месяцам',exact=True).wait_for();self.assertEqual(pg.locator('#billing-error').inner_text(),'')
   evidence=Path('/tmp/neuro-stage7-ux');evidence.mkdir(exist_ok=True);pg.screenshot(path=str(evidence/'owner-report.png'),full_page=True)
   ctx=browser.new_context(viewport={'width':390,'height':844});ctx.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.customer.cookies]);client=ctx.new_page();client.on('pageerror',lambda e:errors.append(str(e)));client.on('dialog',lambda d:d.accept());client.goto(self.base+'/billing.php#invoices/'+str(i['id']));client.get_by_role('button',name='Оплатить в тестовом режиме').wait_for();self.assertEqual(client.locator('script:not([src])').count(),0);self.assertTrue(client.evaluate('document.documentElement.scrollWidth<=innerWidth'));client.screenshot(path=str(evidence/'customer-invoice-mobile.png'),full_page=True)
   p=self.pay(i);client.reload();client.get_by_role('button',name='Проверить платёж').wait_for();self.assertEqual(self.detail(i)['balance']['paid_minor'],0);client.screenshot(path=str(evidence/'customer-pending-mobile.png'),full_page=True)
   row,o=self.settle(p);self.callback(row);client.reload();client.get_by_text('Оплачен · 100,00 RUB',exact=True).wait_for();self.assertTrue(client.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   client.goto(self.base+'/billing.php#notifications');client.get_by_text('Оплата подтверждена',exact=True).wait_for();self.assertTrue(client.evaluate('document.documentElement.scrollWidth<=innerWidth'));client.screenshot(path=str(evidence/'customer-notifications-mobile.png'),full_page=True)
   client.wait_for_load_state('networkidle');pg.wait_for_load_state('networkidle');self.assertEqual(errors,[]);browser.close()
 def test_29_events_existing_smtp_and_interrupted_leases(self):
  from test_customer_auth import SMTPServer,SMTPHandler
  smtp=SMTPServer(('127.0.0.1',0),SMTPHandler);smtp.messages=[];smtp.reject=False;smtp.reject_once=0;threading.Thread(target=smtp.serve_forever,daemon=True).start();self.addCleanup(smtp.server_close);self.addCleanup(smtp.shutdown)
  c=dict(self.f.config)
  try:
   self.f.config.update(billing_email_enabled=True,billing_owner_email='owner@example.invalid',customer_mail={'transport':'test-smtp','host':'127.0.0.1','port':smtp.server_address[1],'from':'noreply@example.invalid','encryption':'none'});self.f.write_config();i=self.invoice()
   r=self.owner.post(self.base+'/api.php?r=crm/collab/projects/'+str(self.project_id)+'/messages',json={'body':'Проверка сообщения','request_key':secrets.token_hex(32)});self.assertEqual(r.status_code,200,r.text)
   rows=self.f.sql("SELECT * FROM nd_notification_outbox WHERE template='new_message' AND record_id=?",params=[self.project_id]);self.assertEqual(len(rows),4);self.assertTrue(any(n['state']=='skipped' and n['recipient_type']=='customer' and n['channel']=='email' for n in rows))
   self.f.sql("INSERT INTO nd_project_stages(project_id,position,title,status) VALUES (?,1,'Тестовый этап','completed')",params=[self.project_id])
   r=self.owner.patch(self.base+'/api.php?r=crm/projects/'+str(self.project_id),json={'version':1,'status':'completed','request_key':secrets.token_hex(32)});self.assertEqual(r.status_code,200,r.text)
   self.assertTrue(self.f.sql("SELECT * FROM nd_notification_outbox WHERE template='project_completed' AND record_id=?",params=[self.project_id]))
   self.f.sql("UPDATE nd_notification_outbox SET state='disabled' WHERE event_key<>? AND channel='email'",params=['invoice:'+str(i['id'])+':issued'])
   r=subprocess.run([self.f.php,str(self.f.path/'scripts/billing-worker.php')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertGreaterEqual(len(smtp.messages),2)
   expected=self.f.sql("SELECT id,state FROM nd_notification_outbox WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued']);self.assertEqual(len(expected),2);self.assertTrue(all(n['state']=='delivered' for n in expected))
   for n in expected:self.assertEqual(sum(('Message-ID: <nd-notice-'+str(n['id'])+'@').encode() in raw for _,raw in smtp.messages),1)
   import email
   for recipient,raw in smtp.messages:
    msg=email.message_from_bytes(raw);self.assertTrue(msg.is_multipart());self.assertEqual({p.get_content_type() for p in msg.walk() if not p.is_multipart()},{'text/plain','text/html'});self.assertNotIn(b'test_fixture_transport_only',raw)
   self.f.sql("UPDATE nd_notification_outbox SET state='processing',attempts=5,lease_until=DATE_SUB(UTC_TIMESTAMP(),INTERVAL 1 SECOND) WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued']);r=subprocess.run([self.f.php,str(self.f.path/'scripts/billing-worker.php')],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);self.assertTrue(all(n['state']=='failed' for n in self.f.sql("SELECT * FROM nd_notification_outbox WHERE event_key=? AND channel='email'",params=['invoice:'+str(i['id'])+':issued'])))
  finally:self.f.config=c;self.f.write_config()
 def test_30_parallel_workers_numbering_and_refund_reservations(self):
  from concurrent.futures import ThreadPoolExecutor
  a=self.invoice(issue=False);b=self.invoice(issue=False)
  def issue(i):
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/billing/routes.php";try{echo json_encode(bill_action(["type"=>"owner","id"=>1],$v["id"],"issue",["version"=>1,"confirm"=>true,"request_key"=>$v["key"]]));}catch(CrmFailure $e){echo json_encode(["error"=>$e->status]);}'
   return json.loads(self.f.php_eval(code,{'root':str(self.f.path),'id':i['id'],'key':secrets.token_hex(32)}))
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(issue,[a,b]))
  self.assertTrue(all(r.get('ok') for r in out),out);self.assertNotEqual(out[0]['record']['number'],out[1]['record']['number'])
  p=self.pay(a);row,o=self.settle(p)
  def reconcile(_):
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/billing/routes.php";echo json_encode(bill_sync_payment(["type"=>"owner","id"=>1],$v["id"]));'
   return json.loads(self.f.php_eval(code,{'root':str(self.f.path),'id':p['id']}))
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(reconcile,range(2)))
  self.assertTrue(all(r.get('ok') for r in out),out);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_payment_transactions WHERE attempt_id=?',params=[p['id']])[0]['n'],1)
  def refund(_):
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/billing/routes.php";try{echo json_encode(bill_refund(["type"=>"owner","id"=>1],$v["id"],["amount"=>"60.00","reason"=>"Parallel test","confirm"=>true,"request_key"=>$v["key"]]));}catch(CrmFailure $e){echo json_encode(["error"=>$e->status]);}'
   return json.loads(self.f.php_eval(code,{'root':str(self.f.path),'id':p['id'],'key':secrets.token_hex(32)}))
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(refund,range(2)))
  self.assertEqual(sum(bool(r.get('ok')) for r in out),1,out);self.assertEqual(sum(r.get('error')==409 for r in out),1,out)
 def test_31_database_failure_rolls_back_snapshot_and_idempotency(self):
  i=self.invoice(issue=False);before=self.detail(i);self.f.sql("CREATE TRIGGER bill_fail BEFORE INSERT ON nd_notification_outbox FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic failure'")
  try:r=self.post(self.owner,f'invoices/{i["id"]}/issue',version=int(i['version']),confirm=True);self.assertEqual(r.status_code,503,r.text);self.assertNotIn('synthetic',r.text)
  finally:self.f.sql('DROP TRIGGER bill_fail')
  after=self.detail(i);self.assertEqual(after['state'],'draft');self.assertIsNone(after['number']);self.assertIsNone(after['snapshot']);self.assertEqual(before['lines'],after['lines'])

 def test_32_unapproved_merchant_live_credentials_and_provider_disabled(self):
  i=self.invoice(issue=False);c=json.loads(json.dumps(self.f.config));before=len(ProviderFixture.calls)
  try:
   self.f.config['billing_merchant']['approved']=False;self.f.write_config();r=self.post(self.owner,f'invoices/{i["id"]}/issue',version=int(i['version']),confirm=True);self.assertEqual(r.status_code,503);self.assertEqual(self.detail(i)['state'],'draft')
   self.f.config=json.loads(json.dumps(c));self.f.write_config();r=self.post(self.owner,f'invoices/{i["id"]}/issue',version=int(i['version']),confirm=True);self.assertEqual(r.status_code,200)
   for field,value in [('mode','live'),('secret_key','not_a_test_key'),('enabled',False),('sandbox_approved',False)]:
    self.f.config=json.loads(json.dumps(c));self.f.config['billing_provider'][field]=value;self.f.write_config();self.assertFalse(self.get(self.owner,'settings').json()['provider_ready']);r=self.post(self.customer,f'invoices/{i["id"]}/pay',confirm=True);self.assertEqual(r.status_code,503,r.text)
   self.assertEqual(len(ProviderFixture.calls),before)
  finally:self.f.config=c;self.f.write_config()

 def test_33_collaboration_exact_document_event_templates(self):
  def cc(s,route,**data):
   data.setdefault('request_key',secrets.token_hex(32));url=self.base+('/api.php?r=crm/collab/' if s is self.owner else '/customer-api.php?r=collab/')+route;r=s.post(url,json=data);self.assertEqual(r.status_code,200,r.text);return r.json()
  rev=cc(self.owner,f'projects/{self.project_id}/documents',title='Тестовое ТЗ',kind='specification',fields={'title':'Тестовое ТЗ','acceptance':'Проверить результат'},file_ids=[])['revision']
  rev=cc(self.owner,f'revisions/{rev["id"]}/ready',version=int(rev['version']))['revision'];rev=cc(self.owner,f'revisions/{rev["id"]}/submit',version=int(rev['version']),confirm=True)['revision']
  cc(self.customer,f'approvals/{rev["approval"]["id"]}/decide',version=int(rev['approval']['version']),confirm=True,decision='changes_requested',feedback='Уточните тестовые требования',checksum=rev['checksum'])
  templates={r['template'] for r in self.f.sql("SELECT template FROM nd_notification_outbox WHERE entity='projects' AND record_id=?",params=[self.project_id])};self.assertTrue({'awaiting_approval','changes_requested'}<=templates)
  upload=self.owner.post(self.base+f'/api.php?r=crm/collab/upload',data={'project_id':self.project_id,'request_key':secrets.token_hex(32),'visibility':'customer'},files={'file':('result.pdf',self.pdf(),'application/pdf')});self.assertEqual(upload.status_code,200,upload.text)
  rev=cc(self.owner,f'projects/{self.project_id}/documents',title='Результат',kind='deliverable',fields={'title':'Результат','acceptance':'Проверить результат'},file_ids=[upload.json()['id']])['revision'];rev=cc(self.owner,f'revisions/{rev["id"]}/ready',version=int(rev['version']))['revision'];cc(self.owner,f'revisions/{rev["id"]}/submit',version=int(rev['version']),confirm=True)
  self.assertTrue(self.f.sql("SELECT id FROM nd_notification_outbox WHERE template='new_deliverable' AND record_id=?",params=[self.project_id]))

# Do not duplicate inherited Stage 6 tests during Stage 7 discovery.
for _name in dir(Collaboration):
 if _name.startswith('test_'):setattr(Billing,_name,None)
del Collaboration
