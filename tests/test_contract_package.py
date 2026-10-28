"""Six separate private templates and actual PDF/party/workspace integration; synthetic only."""
import hashlib,json,re,secrets,subprocess,requests,tempfile
from pathlib import Path
import test_paper_agreement_flow as prospect
ROOT=Path(__file__).resolve().parents[1]
class ContractPackage(prospect.PaperAgreementFlow):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-contracts.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
 def ctp(self,route,**data):return self.lp('contracts/'+route,**data)
 def cget(self):return self.lg('contracts/settings').json()
 def owner_data(self):
  data={k:'' for k in self.cget()['owner_labels']};data.update(full_name='ТЕСТОВЫЙ Исполнитель Иванович',inn=self.inputs()['owner_inn'],status='npd',email='owner@example.invalid',recipient='ТЕСТОВЫЙ Исполнитель Иванович',bank='ВЫМЫШЛЕННЫЙ ТЕСТОВЫЙ БАНК',bik='044525225')
  for k,prefix in [('account',data['bik'][-3:]),('corr','0'+data['bik'][4:6])]:
   base=('4' if k=='account' else '3')*19
   data[k]=next(base+str(last) for last in range(10) if sum(int(d)*[7,1,3][i%3] for i,d in enumerate(prefix+base+str(last)))%10==0)
  return data
 def new_documents(self):
  oid,legacy=self.prepare_documents();r=self.ctp('import');self.assertEqual(r.status_code,200,r.text);self.templates=[self.lg('templates/'+str(i)).json()['record'] for i in r.json()['ids']];self.assertEqual(len(self.templates),6)
  self.assertTrue(all(t['state'] in ['NEEDS_LEGAL_REVIEW','APPROVED'] for t in self.templates));self.assertEqual(self.ctp('import').json()['ids'],r.json()['ids'])
  for i,t in enumerate(self.templates):
   if t['state']=='APPROVED':continue
   self.templates[i]=self.must(self.lp('templates/'+str(t['id'])+'/approve',version=int(t['version']),checksum=t['checksum'],confirm=True,reason='SYNTHETIC fixture approval, never real legal review'))['record']
  s=self.cget();self.assertEqual(self.ctp('owner',data={'full_name':'Incomplete SYNTHETIC'},prior_id=int(s['owner']['id']) if s['owner'] else 0,reviewed=False).status_code,200);pid=self.cget()['owner']['id'];self.assertEqual(self.ctp('owner',data=self.owner_data(),prior_id=int(pid),reviewed=True).status_code,200)
  link=self.own('links',order_id=oid,document_ids=[],details=True,confirm=True,send_email=False,request_key=secrets.token_hex(32));self.assertEqual(link.status_code,200,link.text);g,x=self.exchange(link.json()['url'].split('#token=')[1]);self.consent(g,x);details=g.get(self.base+'/prospect-api.php?r=details').json();self.assertEqual(details['data']['name'],'SYNTHETIC no-account prospect');self.assertEqual(details['data']['email'],self.invite_email)
  data={k:'' for k in details['labels']};data.update(type='person',name='ТЕСТОВАЯ Заказчица Петровна',email=self.invite_email,purpose='personal',represented='no');r=g.post(self.base+'/prospect-api.php?r=details',json={'prior_id':0,'data':data,'submit':True});self.assertEqual(r.status_code,200,r.text);did=r.json()['id'];self.assertFalse(r.json()['account_created']);self.assertFalse(r.json()['email_verified']);self.assertEqual(self.ctp('review',id=did,version=1,approve=True,reason='SYNTHETIC reviewed identity',authority_review='SYNTHETIC person acts personally').status_code,200)
  self.assertEqual(self.create_link(oid,[legacy[0]],False).status_code,200)
  values={k:'ТЕСТОВЫЕ согласованные условия для '+k for t in self.templates for k in t['clauses']['_package']['fields'] if not k.startswith(('owner.','client.'))};values.update({'contract.number':'SYNTHETIC-'+str(oid),'contract.date':'2099-01-01','spec.date':'2099-01-01','act.date':'2099-02-01','change.date':'2099-02-01','permission.date':'2099-03-01','review.date':'2099-03-01','price.total':legacy[0] and self.inputs().get('price','0'),'price.rights_fee':'1.00','spec.milestones':json.dumps([{'result':'ТЕСТОВЫЙ результат','due_on':'2099-02-01','criteria':'ТЕСТОВЫЕ проверяемые критерии','amount':self.f.sql('SELECT total_amount FROM nd_orders WHERE id=?',params=[oid])[0]['total_amount']}]),'act.amount':self.f.sql('SELECT total_amount FROM nd_orders WHERE id=?',params=[oid])[0]['total_amount'],'act.rights_fee':'1.00','act.paid':'0.00','act.balance':self.f.sql('SELECT total_amount FROM nd_orders WHERE id=?',params=[oid])[0]['total_amount'],'act.balance_due':'2099-02-01'})
  del values['price.total'];
  for key in list(values):
   if key.startswith('payment.'):del values[key]
  terms=self.ctp('terms',order_id=oid,proposal_id=int(legacy[0]['id']),values=values,approved=True,confirm_terms=True);self.assertEqual(terms.status_code,200,terms.text);return oid,legacy,g,values,terms.json()['id']
 def gen(self,t,terms,**extra):return self.ctp('generate',template_id=int(t['id']),terms_id=terms,**extra)
 def test_separate_templates_real_pdfs_reviewed_profiles_scope_and_immutable_history(self):
  oid,legacy,g,values,terms=self.new_documents();draft=self.templates[0];self.f.sql("UPDATE nd_lc_templates SET state='NEEDS_LEGAL_REVIEW' WHERE id=?",params=[draft['id']]);self.assertEqual(self.gen(draft,terms).status_code,409);self.f.sql("UPDATE nd_lc_templates SET state='APPROVED' WHERE id=?",params=[draft['id']]);docs=[]
  for t in self.templates[:2]:
   r=self.gen(t,terms);self.assertEqual(r.status_code,200,r.text);b=r.json()['record'];docs.append(b);pdf=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=documents/'+str(b['id'])+'/pdf');self.assertEqual(pdf.status_code,200,pdf.text[:100]);self.assertTrue(pdf.content.startswith(b'%PDF-'));self.assertIn(b'/FontFile2',pdf.content)
   with tempfile.TemporaryDirectory() as tmp:
    f=Path(tmp)/'document.pdf';f.write_bytes(pdf.content);text=subprocess.check_output(['pdftotext',str(f),'-']).decode();self.assertIn(t['title'],text);self.assertIn('НейроДело',text);self.assertIn('Страница 1 /',text);self.assertNotIn('{{',text)
    for forbidden in ['Только владельцу','Codex','manifest.json','DRAFT_REQUIRES','юридической проверке','01_contract.docx']:self.assertNotIn(forbidden,text)
    fonts=subprocess.check_output(['pdffonts',str(f)]).decode();self.assertIn('yes yes yes',fonts)
   self.assertIn(self.stranger.get(self.base+'/lifecycle-api.php?r=documents/'+str(b['id'])+'/pdf').status_code,[401,403,404,503])
   self.assertEqual(self.create_link(oid,[b],False).status_code,409)
   p=self.lg('documents/'+str(b['id'])).json()['record']['pdf'];self.assertEqual(self.ctp('review-pdf',binding_id=int(b['id']),pdf_checksum=p['checksum'],confirm=True,reason='SYNTHETIC actual PDF inspected').status_code,200)
  link=self.create_link(oid,docs,False);self.assertEqual(link.status_code,200,link.text);guest,x=self.exchange(link.json()['url'].split('#token=')[1]);self.consent(guest,x);issued=guest.get(self.base+'/prospect-api.php?r=documents');self.assertEqual(issued.status_code,200,issued.text);self.assertTrue(all(d['pdf_available'] for d in issued.json()['documents']))
  url=self.base+'/prospect-api.php?r=pdf&id='+str(docs[0]['id']);before=guest.get(url);self.assertEqual(before.status_code,200);self.assertEqual(g.get(url).status_code,404);self.assertEqual(guest.get(self.base+'/prospect-api.php?r=pdf&id='+str(legacy[0]['id'])).status_code,404)
  old=self.cget()['owner'];changed=self.owner_data();changed['full_name']='ИЗМЕНЁННЫЙ ТЕСТОВЫЙ Исполнитель';self.assertEqual(self.ctp('owner',data=changed,prior_id=int(old['id']),reviewed=True).status_code,200);self.assertEqual(before.content,guest.get(url).content)
  for t in self.templates:
   sample=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/sample/'+str(t['id']));self.assertEqual(sample.status_code,200);source=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/source/'+str(t['id']));self.assertEqual(hashlib.sha256(source.content).hexdigest(),t['clauses']['_package']['sha256']);self.assertIn(self.customer.get(self.base+'/lifecycle-api.php?r=contracts/source/'+str(t['id'])).status_code,[401,403,503])
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_customer_accounts WHERE customer_id=?',params=[self.customer_id])[0]['n'],0)
 def test_isolated_details_pdfs_paper_countersign_payment_inbox_activation(self):
  oid,legacy,details,values,terms=self.new_documents();docs=[]
  for t in self.templates[:2]:
   b=self.must(self.gen(t,terms))['record'];p=self.lg('documents/'+str(b['id'])).json()['record']['pdf'];self.must(self.ctp('review-pdf',binding_id=int(b['id']),pdf_checksum=p['checksum'],confirm=True,reason='SYNTHETIC reviewed full PDF'));docs.append(b)
  self.paper_docs=[legacy[0],*docs];link=self.create_link(oid,docs,False);self.assertEqual(link.status_code,200,link.text);g,x=self.exchange(link.json()['url'].split('#token=')[1]);self.consent(g,x)
  self.assertEqual(self.ctp('release-payment',binding_id=int(docs[0]['id']),confirm=True,reason='not complete').status_code,409)
  for b in docs:
   r=g.post(self.base+'/prospect-api.php?r=upload',data={'binding_id':b['id'],'request_key':secrets.token_hex(32)},files={'file':('SYNTHETIC-paper-copy.pdf',self.pdf(),'application/pdf')});self.assertEqual(r.status_code,200,r.text);uid=r.json()['id'];self.assertEqual(self.lg('documents/'+str(b['id'])).json()['record']['state'],'SENT');self.must(self.own('import',upload_id=uid,confirm=True,reason='SYNTHETIC owner inspected original test copy'));fresh=self.lg('documents/'+str(b['id'])).json()['record'];self.must(self.action(fresh,'verify'))
   r=self.owner.post(self.base+'/api.php?r=crm/collab/upload',data={'project_id':str(self.project_id),'request_key':secrets.token_hex(32),'visibility':'customer'},files={'file':('SYNTHETIC-owner-completed-copy.pdf',self.pdf(),'application/pdf')});self.assertEqual(r.status_code,200,r.text);fid=int(r.json()['file']['id']);self.must(self.ctp('completed-copy',binding_id=int(b['id']),file_id=fid,confirm=True,reason='SYNTHETIC full pages, exact versions, legibility, signatures and authority reviewed'));r=g.get(self.base+'/prospect-api.php?r=completed-copy&id='+str(b['id']));self.assertEqual(r.status_code,200);self.assertEqual(r.content,self.pdf());self.assertEqual(self.ctp('completed-copy',binding_id=int(b['id']),file_id=fid,confirm=True,reason='duplicate cannot replace history').status_code,409)
  invoice=self.approved_template('invoice');self.must(self.ctp('release-payment',binding_id=int(docs[0]['id']),invoice_template_id=int(invoice['id']),confirm=True,reason='SYNTHETIC release original agreed schedule after copies'));r=g.get(self.base+'/prospect-api.php?r=payment&id='+str(docs[0]['id']));self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['payment_verified']);self.assertNotIn('email',r.json()['bank']);self.setup_action('open',confirm=True);self.assertEqual(self.invite(oid).status_code,409)
  item=min((i for i in self.lg('finance').json()['items'] if int(i['order_id'])==oid),key=lambda i:int(i['id']));self.assertEqual(self.bank(item,amount='0.01').status_code,200);self.assertEqual(self.invite(oid).status_code,409);amount=int(item['total_minor'])-1;entry='SYNTHETIC-'+secrets.token_hex(12);self.assertEqual(self.bank(item,amount=f'{amount//100}.{amount%100:02}',bank_entry_id=entry).status_code,200);self.assertEqual(self.bank(item,bank_entry_id=entry).status_code,409)
  self.smtp.reject=True;r=self.invite(oid);self.assertFalse(r.json()['smtp_accepted']);self.smtp.reject=False;self.smtp.messages.clear();r=self.invite(oid);self.assertEqual(r.status_code,200,r.text);self.assertFalse(r.json()['delivery_confirmed']);self.assertEqual(len(self.smtp.messages),1);token=self.token();s=requests.Session();session=s.get(self.base+'/customer-api.php?r=session').json();s.headers['X-CSRF-Token']=session['csrf'];payload={'token':token,'password':'SYNTHETIC-client12345','password_confirmation':'SYNTHETIC-client12345','consent':True,'policy_version':self.policy['version']};self.f.sql('UPDATE nd_customer_tokens SET expires_at=0 WHERE token_hash=SHA2(?,256)',params=[token]);self.assertEqual(s.post(self.base+'/customer-api.php?r=invite',json=payload).status_code,422);self.assertEqual(self.invite(oid).status_code,200);payload['token']=self.token();self.assertEqual(s.post(self.base+'/customer-api.php?r=invite',json=payload).status_code,200);self.assertEqual(s.post(self.base+'/customer-api.php?r=invite',json=payload).status_code,422);login=s.post(self.base+'/customer-api.php?r=login',json={'email':self.invite_email,'password':'SYNTHETIC-client12345'});self.assertEqual(login.status_code,200,login.text);s.headers['X-CSRF-Token']=login.json()['csrf'];self.assertEqual(self.fg(oid,s).status_code,200)
  for b in docs:
   url=self.base+'/lifecycle-api.php?r=documents/'+str(b['id'])+'/pdf';self.assertEqual(s.get(url).status_code,200);self.assertNotEqual(self.stranger.get(url).status_code,200)
  self.assertFalse(requests.get(self.base+'/customer-api.php?r=settings').json()['registration_enabled']);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_lc_receipt_evidence')[0]['n'],0)
 def test_owner_and_scoped_customer_forms_in_mobile_browser(self):
  import os
  from playwright.sync_api import sync_playwright
  oid,legacy,g,v,terms=self.new_documents();r=self.own('links',order_id=oid,document_ids=[],details=True,confirm=True,send_email=False,request_key=secrets.token_hex(32));self.assertEqual(r.status_code,200,r.text)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page(viewport={'width':375,'height':812});errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(self.base+'/studio.php');page.locator('#password').fill(self.f.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible');page.goto(self.base+'/contract-settings.php');page.get_by_role('button',name='Сохранить реквизиты',exact=True).wait_for();page.get_by_label('ФИО исполнителя',exact=True).fill('ТЕСТОВЫЙ неполный черновик');page.get_by_role('button',name='Сохранить реквизиты',exact=True).click();page.get_by_text('Сохранено.',exact=True).wait_for();page.reload();page.get_by_role('button',name='Сохранить реквизиты',exact=True).wait_for();self.assertEqual(page.get_by_label('ФИО исполнителя',exact=True).input_value(),'ТЕСТОВЫЙ неполный черновик');self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'))
   guest=browser.new_context(viewport={'width':375,'height':812}).new_page();guest.on('pageerror',lambda e:errors.append(str(e)));guest.goto(r.json()['url']);guest.get_by_role('checkbox').check();guest.get_by_role('button',name='Продолжить к документам',exact=True).click();guest.get_by_role('button',name='Передать данные для подготовки договора',exact=True).wait_for();guest.get_by_label('Тип заказчика',exact=True).select_option('company');self.assertTrue(guest.get_by_label('Юридический адрес организации',exact=True).is_visible());guest.get_by_label('Тип заказчика',exact=True).select_option('person');self.assertFalse(guest.get_by_label('Юридический адрес организации',exact=True).is_visible());guest.get_by_role('button',name='Сохранить черновик',exact=True).click();guest.get_by_text('Черновик сохранён.',exact=True).wait_for();self.assertEqual(guest.evaluate('location.hash'),'');self.assertFalse(guest.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(errors,[]);browser.close()
 def test_missing_fields_stage_checks_invalid_details_stale_edits_and_unauthorized(self):
  oid,legacy,g,v,terms=self.new_documents();bad=dict(v);del bad['support.start_event'];r=self.ctp('terms',order_id=oid,proposal_id=int(legacy[0]['id']),values=bad,approved=True,confirm_terms=True);self.assertEqual(r.status_code,200);self.assertEqual(self.gen(self.templates[0],r.json()['id']).status_code,422)
  for t in self.templates[2:]:self.assertEqual(self.gen(t,terms).status_code,409)
  details=g.get(self.base+'/prospect-api.php?r=details').json();data=details['data'].copy();data.update(type='company',inn='1234567890',ogrn='1234567890123');self.assertEqual(g.post(self.base+'/prospect-api.php?r=details',json={'prior_id':details['id'],'data':data,'submit':True}).status_code,422);self.assertEqual(g.post(self.base+'/prospect-api.php?r=details',json={'prior_id':0,'data':details['data'],'submit':True}).status_code,409)
  self.assertEqual(g.get(self.base+'/lifecycle-api.php?mode=owner&r=contracts/settings').status_code,401)
  self.assertEqual(self.ctp('owner',data={'inn':'123'},prior_id=0,reviewed=True).status_code,409)
  r=subprocess.run([self.f.php,str(self.f.path/'scripts/migrate-contracts.php'),'down'],capture_output=True,text=True);self.assertNotEqual(r.returncode,0);self.assertIn('rollback_refused_nonempty',r.stderr)
for name in dir(prospect.PaperAgreementFlow):
 if name.startswith('test_'):setattr(ContractPackage,name,None)

import unittest,os
class PdfRendering(unittest.TestCase):
 def test_all_six_standalone_cyrillic_pdfs_and_no_internal_content(self):
  with tempfile.TemporaryDirectory() as tmp:
   code='require '+json.dumps(str(ROOT/'private/lifecycle/contract-package.php'))+';foreach(ct_catalog() as $t){$v=array_fill_keys($t["fields"],"ТЕСТОВЫЕ ПРОВЕРЕННЫЕ ДАННЫЕ");$v["owner.postal_address_line"]="";$v["review.rating"]="";$v["review.company"]="";$v["review.photo_reference"]="";file_put_contents('+json.dumps(tmp)+' . "/".$t["kind"].".pdf",ct_pdf_bytes($t["title"],ct_fill($t,$v)));}'
   result=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',code],capture_output=True);self.assertEqual(result.returncode,0,result.stderr.decode());self.assertEqual(result.stderr,b'')
   templates=json.loads((ROOT/'private/lifecycle/package/catalog.json').read_text())['templates'];self.assertEqual(len(list(Path(tmp).glob('*.pdf'))),6)
   for t in templates:
    pdf=Path(tmp)/(t['kind']+'.pdf');body=pdf.read_bytes();self.assertTrue(body.startswith(b'%PDF-'));text=subprocess.check_output(['pdftotext',str(pdf),'-']).decode();self.assertIn(t['title'],text);self.assertIn('Страница 1 /',text);self.assertNotIn('{{',text)
    for banned in ['Codex','manifest.json','Только владельцу','NEEDS_LEGAL_REVIEW','LEGAL_REVIEW','01_contract.docx','Оценка при желании','Фото при желании']:self.assertNotIn(banned,text)
    fonts=subprocess.check_output(['pdffonts',str(pdf)]).decode();self.assertEqual(fonts.count('yes yes yes'),2)
    info=subprocess.check_output(['pdfinfo',str(pdf)]).decode();pages=int(re.search(r'Pages:\s+(\d+)',info).group(1));self.assertGreaterEqual(pages,1);self.assertIn('Страница '+str(pages)+' / '+str(pages),text)
    # Poppler must parse and rasterize every page, not merely recognize the PDF header.
    raster=Path(tmp)/(t['kind']+'-page');subprocess.run(['pdftoppm','-scale-to','650','-png',str(pdf),str(raster)],check=True,capture_output=True);self.assertEqual(len(list(Path(tmp).glob(t['kind']+'-page-*.png'))),pages)
