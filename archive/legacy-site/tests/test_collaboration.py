"""Stage 6 private collaboration HTTP tests on random loopback-only databases."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import unittest
import requests
import test_prelaunch as fixture

class Collaboration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class F(fixture.Prelaunch):
   @classmethod
   def write_config(c):
    blob=base64.b64encode(json.dumps(c.config).encode()).decode();(c.path/'private/config.php').write_text("<?php return json_decode(base64_decode('"+blob+"'),true);")
  cls.f=F;F.setUpClass();cls.addClassCleanup(F.doClassCleanups)
  for runner in ['migrate.php','migrate-customer.php','migrate-crm.php','migrate-collab.php']:
   r=subprocess.run([F.php,str(F.path/'scripts'/runner),'up'],capture_output=True,text=True)
   if r.returncode:raise RuntimeError(r.stderr)
  F.config.update(crm_operations_enabled=True,client_collaboration_enabled=True,customer_auth_enabled=True,customer_auth_privacy_approved=True,customer_auth_test_mode=True);F.write_config();cls.base=F.base
 def setUp(self):
  self.f.sql('DELETE FROM nd_limits');self.owner=requests.Session();r=self.owner.post(self.base+'/api.php?r=login',json={'password':self.f.password});self.assertEqual(r.status_code,200,r.text);self.owner.headers['X-CSRF-Token']=r.json()['csrf']
  self.customer_id=self.insert("INSERT INTO nd_customers(name,email) VALUES ('Синтетический клиент','a@example.invalid')",'nd_customers')
  self.project_id=self.insert("INSERT INTO nd_projects(customer_id,title,status) VALUES (?,'Синтетический проект','active')",'nd_projects',[self.customer_id])
  self.customer=self.account(self.customer_id)
  other=self.insert("INSERT INTO nd_customers(name) VALUES ('Другой клиент')",'nd_customers');self.other_customer_id=other;self.stranger=self.account(other)
 def insert(self,sql,table,params=None):
  self.f.sql(sql,params=params);return int(self.f.sql('SELECT MAX(id) AS n FROM '+table)[0]['n'])
 def account(self,cid):
  email=secrets.token_hex(8)+'@example.invalid';password=secrets.token_urlsafe(20);h=self.f.php_eval('echo password_hash($v["p"],PASSWORD_DEFAULT);',{'p':password})
  aid=self.insert("INSERT INTO nd_customer_accounts(customer_id,email,password_hash,status) VALUES (?,?,?,'active')",'nd_customer_accounts',[cid,email,h]);policy=hashlib.sha256((self.f.path/'private/privacy-policy.txt').read_bytes()).hexdigest()
  self.f.sql("INSERT INTO nd_customer_auth VALUES (?,'invitation',?,?,?,?)",params=[aid,int(time.time()),int(time.time()),'test-policy-v1',policy])
  s=requests.Session();r=s.get(self.base+'/customer-api.php?r=session');s.headers['X-CSRF-Token']=r.json()['csrf'];r=s.post(self.base+'/customer-api.php?r=login',json={'email':email,'password':password});self.assertEqual(r.status_code,200,r.text);s.headers['X-CSRF-Token']=r.json()['csrf'];return s
 def url(self,s,route):return self.base+('/api.php?r=crm/collab/' if s is self.owner else '/customer-api.php?r=collab/')+route
 def get(self,s,route,**params):return s.get(self.url(s,route),params=params)
 def post(self,s,route,**d):
  d.setdefault('request_key',secrets.token_hex(32));return s.post(self.url(s,route),json=d)
 def test_01_messages_auth_unread_idempotency_and_archive(self):
  route=f'projects/{self.project_id}/messages';payload={'body':'Здравствуйте <script>alert(1)</script>','request_key':secrets.token_hex(32)}
  a=self.post(self.owner,route,**payload);self.assertEqual(a.status_code,200,a.text);self.assertEqual(self.post(self.owner,route,**payload).json()['id'],a.json()['id'])
  self.assertEqual(self.get(self.stranger,route).status_code,404);self.assertEqual(self.post(self.stranger,route,body='Попытка').status_code,404)
  self.assertEqual(self.get(self.customer,'threads').json()['items'][0]['unread'],1)
  self.assertEqual(self.post(self.customer,f'projects/{self.project_id}/read',last_message_id=a.json()['id']).status_code,200);self.assertEqual(self.get(self.customer,'threads').json()['items'][0]['unread'],0)
  b=self.post(self.customer,route,body='Ответ клиента');self.assertEqual(b.status_code,200,b.text);self.assertEqual(len(self.get(self.owner,route).json()['items']),2)
  bad=self.post(self.customer,route,body='Проверка вложений',file_ids=[[]]);self.assertEqual(bad.status_code,422);self.assertNotIn('/private/',bad.text)
  self.assertEqual(self.post(self.customer,route,body=' ').status_code,422);self.assertEqual(self.post(self.customer,route,body='x'*5001).status_code,422)
  no=requests.Session();no.cookies.update(self.customer.cookies);self.assertEqual(no.post(self.url(self.customer,route),json=payload).status_code,403)
  self.f.sql('UPDATE nd_projects SET archived_at=UTC_TIMESTAMP() WHERE id=?',params=[self.project_id]);self.assertEqual(self.get(self.customer,route).status_code,200);self.assertEqual(self.post(self.customer,route,body='Закрытый').status_code,409)
 def pdf(self):return b'%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n'
 def upload(self,s,name='test.pdf',body=None,**data):
  fields={'project_id':str(self.project_id),'request_key':secrets.token_hex(32),'visibility':'internal'};fields.update(data)
  return s.post(self.url(s,'upload'),data=fields,files={'file':(name,self.pdf() if body is None else body,'application/octet-stream')})
 def test_02_private_files_visibility_download_and_missing_bytes(self):
  key=secrets.token_hex(32);r=self.upload(self.owner,request_key=key);self.assertEqual(r.status_code,200,r.text);fid=r.json()['id'];self.assertNotIn('storage_key',r.text)
  self.assertEqual(self.upload(self.owner,request_key=key).json()['id'],fid)
  url=self.base+'/collab-download.php?mode=customer&id='+str(fid)
  self.assertEqual(self.customer.get(url).status_code,404);self.assertEqual(self.stranger.get(url).status_code,404);self.assertEqual(requests.get(url).status_code,401)
  r=self.post(self.owner,'files/'+str(fid),version=1,visibility='customer',archived=False);self.assertEqual(r.status_code,200,r.text)
  r=self.customer.get(url);self.assertEqual(r.status_code,200,r.text);self.assertEqual(r.content,self.pdf());self.assertEqual(r.headers['X-Content-Type-Options'],'nosniff');self.assertIn('attachment',r.headers['Content-Disposition'])
  self.assertEqual(self.stranger.get(url).status_code,404);self.assertEqual(self.stranger.get(url).json(),self.stranger.get(self.base+'/collab-download.php?mode=customer&id=99999999').json())
  self.assertEqual(self.post(self.customer,f'projects/{self.project_id}/messages',body='Прикреплён файл',file_ids=[fid]).status_code,200)
  row=self.f.sql('SELECT storage_key FROM nd_cc_files WHERE id=?',params=[fid])[0];path=self.f.path/'private/collaboration-files'/row['storage_key'];self.assertEqual(path.stat().st_mode&0o777,0o600);path.unlink()
  r=self.customer.get(url);self.assertEqual(r.status_code,503);self.assertNotIn(str(self.f.path),r.text)
  self.assertEqual(self.customer.get(self.base+'/private/collaboration-files/'+row['storage_key']).status_code,404)
 def test_03_invalid_uploads_quotas_and_clean_failures(self):
  for name,body in [('run.php',b'<?php echo 1;'),('fake.pdf',b'<?php echo 1;'),('active.pdf',b'%PDF-1.4\n/JavaScript x\n%%EOF'),('../evil.pdf',self.pdf()),('fake.png',self.pdf()),('empty.pdf',b''),('page.html',b'<html>x</html>')]:
   r=self.upload(self.owner,name,body);self.assertEqual(r.status_code,422,(name,r.text))
  before=self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'];config=dict(self.f.config)
  try:
   self.f.config['collaboration_file_max_bytes']=1;self.f.write_config();self.assertEqual(self.upload(self.owner).status_code,422)
   self.f.config['collaboration_file_max_bytes']=5242880;self.f.config['collaboration_total_max_bytes']=1;self.f.write_config();self.assertEqual(self.upload(self.owner).status_code,507)
  finally:self.f.config=config;self.f.write_config()
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'],before)
  r=self.owner.post(self.url(self.owner,'upload'),data={'project_id':self.project_id,'request_key':secrets.token_hex(32)});self.assertEqual(r.status_code,422)
  self.assertEqual(self.upload(self.stranger).status_code,404)
  import socket
  count=self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'];boundary='neuroInterruptedUpload';body=('--'+boundary+'\r\nContent-Disposition: form-data; name="file"; filename="partial.pdf"\r\nContent-Type: application/pdf\r\n\r\n%PDF-partial').encode()
  headers=('POST /api.php?r=crm/collab/upload HTTP/1.1\r\nHost: 127.0.0.1:'+str(self.f.port)+'\r\nContent-Type: multipart/form-data; boundary='+boundary+'\r\nContent-Length: '+str(len(body)+4096)+'\r\nCookie: nd_session='+self.owner.cookies.get('nd_session')+'\r\nX-CSRF-Token: '+self.owner.headers['X-CSRF-Token']+'\r\nConnection: close\r\n\r\n').encode()
  with socket.create_connection(('127.0.0.1',self.f.port),timeout=3) as sock:
   sock.sendall(headers+body);sock.shutdown(socket.SHUT_WR)
   try:sock.recv(4096)
   except socket.timeout:pass
  self.assertEqual(self.get(self.owner,'threads').status_code,200);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_cc_files')[0]['n'],count)

 def test_04_office_archive_validation(self):
  import io,zipfile
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:
   z.writestr('[Content_Types].xml','<Types><Override ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>');z.writestr('_rels/.rels','<Relationships/>');z.writestr('word/document.xml','<document/>')
  zip_enabled=self.f.php_eval('echo class_exists("ZipArchive")?"yes":"no";',{})=='yes'
  r=self.upload(self.owner,'spec.docx',buf.getvalue());self.assertEqual(r.status_code,200 if zip_enabled else 503,r.text)
  with zipfile.ZipFile(buf,'a') as z:z.writestr('word/vbaProject.bin',b'evil')
  r=self.upload(self.owner,'macro.docx',buf.getvalue());self.assertEqual(r.status_code,422 if zip_enabled else 503,r.text)
 def document(self,kind='specification',files=None,**extra):
  d={'title':'Техническое задание','kind':kind,'fields':{'title':'Техническое задание','description':'Описание реальной тестовой задачи','acceptance':'Проверить согласованные требования'},'file_ids':files or []};d.update(extra)
  r=self.post(self.owner,f'projects/{self.project_id}/documents',**d);self.assertEqual(r.status_code,200,r.text);return r.json()['revision']
 def ready_submit(self,rev):
  rid=rev['id'];r=self.post(self.owner,f'revisions/{rid}/ready',version=int(rev['version']));self.assertEqual(r.status_code,200,r.text)
  r=self.post(self.owner,f'revisions/{rid}/submit',version=int(r.json()['revision']['version']),confirm=True);self.assertEqual(r.status_code,200,r.text);return r.json()['revision']
 def decide(self,rev,decision='approved',s=None,**extra):
  data={'version':int(rev['approval']['version']),'checksum':rev['checksum'],'confirm':True,'decision':decision,'feedback':'Нужно уточнить требования' if decision=='changes_requested' else ''};data.update(extra)
  return self.post(s or self.customer,'approvals/'+str(rev['approval']['id'])+'/decide',**data)
 def test_05_specification_revisions_and_immutable_approval(self):
  v1=self.document();self.assertEqual(self.get(self.customer,'revisions/'+str(v1['id'])).status_code,404)
  v1=self.ready_submit(v1);self.assertEqual(self.get(self.stranger,'revisions/'+str(v1['id'])).status_code,404)
  self.assertEqual(self.decide(v1,'changes_requested',feedback='no').status_code,422)
  r=self.decide(v1,'changes_requested');self.assertEqual(r.status_code,200,r.text)
  original=self.f.sql('SELECT body,checksum FROM nd_cc_revisions WHERE id=?',params=[v1['id']])[0]
  self.assertEqual(self.post(self.owner,f'revisions/{v1["id"]}/save',version=int(v1['version']),fields={'title':'Изменить задним числом'}).status_code,409)
  current=self.get(self.owner,'revisions/'+str(v1['id'])).json()['revision'];doc=current['document']
  r=self.post(self.owner,f'documents/{doc["id"]}/revise',version=int(doc['version']));self.assertEqual(r.status_code,200,r.text);v2=self.ready_submit(r.json()['revision'])
  self.assertEqual(self.decide(v1).status_code,409)
  request=secrets.token_hex(32);r=self.decide(v2,request_key=request);self.assertEqual(r.status_code,200,r.text);self.assertEqual(self.decide(v2,request_key=request).json(),r.json())
  self.assertEqual(self.decide(v2).status_code,409)
  self.assertEqual(self.f.sql('SELECT body,checksum FROM nd_cc_revisions WHERE id=?',params=[v1['id']])[0],original)
  self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_cc_decisions WHERE approval_id=?',params=[v2['approval']['id']])[0]['n'],1)
  current=self.get(self.owner,'revisions/'+str(v2['id'])).json()['revision'];r=self.post(self.owner,f'revisions/{v2["id"]}/finalize',version=int(current['version']));self.assertEqual(r.status_code,200,r.text)
  old=self.get(self.owner,'revisions/'+str(v1['id'])).json()['revision'];archived=self.post(self.owner,f'revisions/{v1["id"]}/archive',version=int(old['version']));self.assertEqual(archived.status_code,200,archived.text);self.assertIsNotNone(self.get(self.customer,'revisions/'+str(v1['id'])).json()['revision']['archived_at']);self.assertEqual(self.f.sql('SELECT body,checksum FROM nd_cc_revisions WHERE id=?',params=[v1['id']])[0],original)
  self.f.sql("UPDATE nd_customers SET name='Имя после согласования' WHERE id=?",params=[self.customer_id]);self.f.sql("UPDATE nd_projects SET title='Название после согласования' WHERE id=?",params=[self.project_id])
  url=self.base+'/collab-print.php?mode=customer&id='+str(v2['id']);page=self.customer.get(url);self.assertEqual(page.status_code,200,page.text);self.assertIn('text/html',page.headers['Content-Type']);self.assertIn(v2['checksum'],page.text);self.assertIn('Синтетический клиент',page.text);self.assertIn('Синтетический проект',page.text);self.assertNotIn('Имя после согласования',page.text);self.assertNotIn('Название после согласования',page.text);self.assertEqual(self.stranger.get(url).status_code,404)
  history=self.f.sql("SELECT actor_admin_id,actor_customer_account_id FROM nd_activity_history WHERE project_id=? AND action='cc_decision_recorded'",params=[self.project_id]);self.assertTrue(history);self.assertIsNone(history[0]['actor_admin_id']);self.assertIsNotNone(history[0]['actor_customer_account_id'])
 def test_06_outdated_pending_review_and_concurrency(self):
  rev=self.ready_submit(self.document());doc=rev['document']
  r=self.post(self.owner,f'documents/{doc["id"]}/revise',version=int(doc['version']));self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.decide(rev).status_code,409)
  draft=r.json()['revision'];fields=dict(draft['fields']);fields['requirements']='Первое изменение'
  r=self.post(self.owner,f'revisions/{draft["id"]}/save',version=int(draft['version']),fields=fields,file_ids=[]);self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.post(self.owner,f'revisions/{draft["id"]}/save',version=int(draft['version']),fields={'requirements':'Устаревшее изменение'},file_ids=[]).status_code,409)
  self.assertEqual(self.get(self.owner,f'revisions/{draft["id"]}').json()['revision']['fields']['requirements'],'Первое изменение')
 def test_07_delivery_files_revision_and_cross_customer_isolation(self):
  f1=self.upload(self.owner,visibility='customer');self.assertEqual(f1.status_code,200,f1.text)
  v1=self.ready_submit(self.document('deliverable',[f1.json()['id']]));self.assertEqual(self.decide(v1,'changes_requested').status_code,200)
  current=self.get(self.owner,f'revisions/{v1["id"]}').json()['revision'];doc=current['document']
  f2=self.upload(self.owner,name='updated.pdf',visibility='customer');self.assertEqual(f2.status_code,200,f2.text)
  r=self.post(self.owner,f'documents/{doc["id"]}/revise',version=int(doc['version']),fields=current['fields'],file_ids=[f2.json()['id']]);self.assertEqual(r.status_code,200,r.text);v2=self.ready_submit(r.json()['revision']);self.assertEqual(self.decide(v2).status_code,200)
  self.assertEqual(len(self.get(self.owner,f'projects/{self.project_id}/documents').json()['items']),2)
  for route in [f'projects/{self.project_id}/files',f'projects/{self.project_id}/documents',f'projects/{self.project_id}/approvals',f'revisions/{v2["id"]}']:
   self.assertEqual(self.get(self.stranger,route).status_code,404,route)
  self.assertEqual(self.decide(v2,s=self.stranger).status_code,404);self.assertEqual(self.get(self.stranger,f'revisions/{v2["id"]}').json(),self.get(self.stranger,'revisions/99999999').json())
  self.assertEqual(self.post(self.customer,f'projects/{self.project_id}/documents',title='Попытка',kind='plan').status_code,403)
  self.assertEqual(self.get(self.customer,f'revisions/{v1["id"]}').json()['revision']['files'][0]['id'],f1.json()['id'])
 def test_08_final_acceptance_requires_completed_milestones(self):
  doc=self.document('final');r=self.post(self.owner,f'revisions/{doc["id"]}/ready',version=int(doc['version']));self.assertEqual(r.status_code,200,r.text)
  self.assertEqual(self.post(self.owner,f'revisions/{doc["id"]}/submit',version=int(r.json()['revision']['version']),confirm=True).status_code,409)
  self.f.sql("INSERT INTO nd_project_stages(project_id,position,title,status) VALUES (?,1,'Готовый этап','completed')",params=[self.project_id])
  r=self.post(self.owner,f'revisions/{doc["id"]}/submit',version=int(r.json()['revision']['version']),confirm=True);self.assertEqual(r.status_code,200,r.text);sent=r.json()['revision']
  self.f.sql('UPDATE nd_projects SET version=version+1 WHERE id=?',params=[self.project_id]);self.assertEqual(self.decide(sent).status_code,409)
 def test_09_storage_cleanup_concurrent_quota_and_bad_metadata(self):
  from concurrent.futures import ThreadPoolExecutor
  root=self.f.path/'private/collaboration-files';before=set(root.iterdir()) if root.exists() else set()
  self.f.sql("CREATE TRIGGER cc_test_fail BEFORE INSERT ON nd_cc_files FOR EACH ROW SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='synthetic storage failure'")
  try:
   r=self.upload(self.owner);self.assertEqual(r.status_code,503,r.text)
   self.assertEqual(set(root.iterdir()) if root.exists() else set(),before)
  finally:self.f.sql('DROP TRIGGER cc_test_fail')
  kept=self.upload(self.owner);self.assertEqual(kept.status_code,200,kept.text);storage=self.f.sql('SELECT storage_key FROM nd_cc_files WHERE id=?',params=[kept.json()['id']])[0]['storage_key'];kept_path=root/storage
  helper='require $v["root"]."/private/app.php";require $v["root"]."/private/collab/core.php";require $v["root"]."/private/collab/files.php";echo cc_cleanup_upload($v["path"]);'
  self.assertEqual(self.f.php_eval(helper,{'root':str(self.f.path),'path':str(kept_path)}),'retained');self.assertTrue(kept_path.exists())
  unknown=root/secrets.token_hex(32);unknown.write_bytes(b'uncertain outcome fixture');old_config=dict(self.f.config)
  try:
   self.f.config['db_name']=self.f.dbname+'_unavailable';self.f.write_config();self.assertEqual(self.f.php_eval(helper,{'root':str(self.f.path),'path':str(unknown)}),'retained_unknown');self.assertTrue(unknown.exists())
  finally:self.f.config=old_config;self.f.write_config()
  self.assertEqual(self.f.php_eval(helper,{'root':str(self.f.path),'path':str(unknown)}),'removed');self.assertFalse(unknown.exists())
  saved=dict(self.f.config);used=sum(p.stat().st_size for p in root.iterdir() if p.name!='.quota.lock')
  try:
   self.f.config['collaboration_total_max_bytes']=used+len(self.pdf())+1;self.f.write_config()
   with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:self.upload(self.owner),range(2)))
   self.assertEqual(sorted(r.status_code for r in results),[200,507])
  finally:self.f.config=saved;self.f.write_config()
  fid=next(r.json()['id'] for r in results if r.status_code==200);self.f.sql("UPDATE nd_cc_files SET storage_key='../unsafe' WHERE id=?",params=[fid]);r=self.owner.get(self.base+'/collab-download.php?mode=owner&id='+str(fid));self.assertEqual(r.status_code,503);self.assertNotIn(str(self.f.path),r.text)
 def test_10_browser_chat_upload_documents_approvals_desktop_mobile(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);errors=[]
   owner_context=browser.new_context(viewport={'width':1440,'height':1000});owner_context.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);pg=owner_context.new_page();pg.on('pageerror',lambda e:errors.append(str(e)));pg.on('dialog',lambda d:d.accept())
   pg.goto(self.base+f'/collaboration.php?mode=owner&project={self.project_id}#messages');pg.wait_for_selector('textarea[name=message]');pg.locator('textarea[name=message]').fill('Сообщение из браузера <script>alert(1)</script>')
   pg.locator('input[type=file]').set_input_files({'name':'browser.pdf','mimeType':'application/pdf','buffer':self.pdf()});pg.get_by_role('button',name='Загрузить файл',exact=True).click();pg.get_by_text('Сохранён: browser.pdf',exact=True).wait_for();pg.route('**/api.php?r=crm/collab/projects/*/messages',lambda route:route.fulfill(status=200,content_type='text/html',body='<html>Unexpected response</html>') if route.request.method=='POST' else route.continue_());pg.get_by_role('button',name='Отправить',exact=True).click();pg.get_by_text('Сервер прислал неожиданный ответ. Операция не подтверждена.',exact=True).wait_for();self.assertIn('Сообщение из браузера',pg.locator('textarea[name=message]').input_value());pg.unroute('**/api.php?r=crm/collab/projects/*/messages');pg.get_by_role('button',name='Отправить',exact=True).click();pg.locator('.conversation').get_by_text('Сообщение из браузера <script>alert(1)</script>',exact=True).wait_for()
   self.assertEqual(pg.locator('.conversation script').count(),0)
   shots=Path(os.environ.get('NEURO_COLLAB_SCREENSHOTS','/tmp/neuro-stage6-ux'));shots.mkdir(parents=True,exist_ok=True);pg.screenshot(path=str(shots/'owner-messages.png'),full_page=True)
   pg.locator('#cc-nav a[href="#documents"]').click();pg.get_by_role('button',name='Создать документ',exact=True).click();pg.wait_for_selector('#cc-modal[open]');pg.locator('[name=title]').fill('Браузерное ТЗ');pg.locator('[name=acceptance]').fill('Проверить работоспособность всех согласованных разделов');pending_save=[];pg.route('**/api.php?r=crm/collab/projects/*/documents',lambda route:pending_save.append(route) if route.request.method=='POST' else route.continue_());pg.get_by_role('button',name='Сохранить черновик',exact=True).click();pg.wait_for_function("() => document.querySelector('#cc-close').disabled");pg.keyboard.press('Escape');self.assertTrue(pg.locator('#cc-modal').is_visible());pg.get_by_text('Дождитесь завершения сохранения. Черновик остаётся в форме.',exact=True).first.wait_for();self.assertTrue(pending_save);pending_save[0].continue_();pg.wait_for_selector('#cc-modal[open]',state='hidden');pg.unroute('**/api.php?r=crm/collab/projects/*/documents')
   pg.get_by_role('button',name='Открыть версию',exact=True).click();pg.get_by_role('button',name='Подготовить к отправке',exact=True).click();pg.get_by_role('button',name='Отправить на согласование',exact=True).click();pg.get_by_role('button',name='Отозвать запрос',exact=True).wait_for();pg.screenshot(path=str(shots/'owner-document.png'),full_page=True)
   customer_context=browser.new_context(viewport={'width':390,'height':844});customer_context.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.customer.cookies]);client=customer_context.new_page();client.on('pageerror',lambda e:errors.append(str(e)));client.on('dialog',lambda d:d.accept())
   client.goto(self.base+f'/collaboration.php?project={self.project_id}#approvals');client.get_by_role('button',name='Открыть точную версию',exact=True).click();client.get_by_role('button',name='Согласовать',exact=True).wait_for();self.assertTrue(client.locator('#cc-modal').evaluate('e => e.scrollWidth<=e.clientWidth'));client.screenshot(path=str(shots/'customer-review-mobile.png'),full_page=True);client.get_by_role('button',name='Согласовать',exact=True).click();client.get_by_text('Решение клиента',exact=True).wait_for();client.get_by_role('button',name='Закрыть',exact=True).click()
   client.locator('#open-project').click();client.get_by_role('heading',name='Синтетический проект',exact=True).wait_for();self.assertTrue(client.url.endswith('#projects/'+str(self.project_id)));self.assertEqual(client.locator('.card').count(),1)
   for section in ['overview','messages','files','documents','approvals','deliverables']:
    client.goto(self.base+f'/collaboration.php?project={self.project_id}#'+section);client.wait_for_function("() => document.querySelector('#cc-content').children.length>0");self.assertTrue(client.evaluate('document.documentElement.scrollWidth<=innerWidth'),section)
   client.screenshot(path=str(shots/'customer-dashboard-mobile.png'),full_page=True)
   other=self.insert("INSERT INTO nd_projects(customer_id,title,status) VALUES (?,'Второй проект владельца','active')",'nd_projects',[self.other_customer_id])
   pg.get_by_role('button',name='Закрыть',exact=True).click();pg.goto(self.base+f'/collaboration.php?mode=owner&project={self.project_id}#documents');pg.reload();pg.get_by_role('button',name='Создать документ',exact=True).wait_for();pending_files=[]
   pattern='**/api.php?r=crm/collab/projects/'+str(self.project_id)+'/files';pg.route(pattern,lambda route:pending_files.append(route));pg.get_by_role('button',name='Создать документ',exact=True).click()
   for _ in range(20):
    if pending_files:break
    pg.wait_for_timeout(10)
   self.assertTrue(pending_files);pg.locator('.thread').filter(has_text='Второй проект владельца').click();pg.wait_for_function("() => document.querySelector('#project-title').textContent.startsWith('Второй проект владельца')")
   with pg.expect_response(lambda r:f'projects/{self.project_id}/files' in r.url) as response:pending_files[0].continue_()
   response.value.body();pg.wait_for_timeout(50);self.assertFalse(pg.locator('#cc-modal').is_visible());pg.unroute(pattern)
   pg.get_by_role('button',name='Создать документ',exact=True).click();pg.wait_for_selector('#cc-modal[open]');pg.locator('[name=title]').fill('Документ второго проекта');pg.get_by_role('button',name='Сохранить черновик',exact=True).click();pg.wait_for_selector('#cc-modal[open]',state='hidden')
   self.assertEqual(int(self.f.sql('SELECT project_id FROM nd_cc_documents WHERE title=?',params=['Документ второго проекта'])[0]['project_id']),other)
   pg.goto(self.base+f'/collaboration.php?mode=owner&project={self.project_id}#messages');pg.wait_for_selector('textarea[name=message]');pg.locator('textarea[name=message]').fill('Сообщение первого проекта')
   pending_send=[];send_pattern='**/api.php?r=crm/collab/projects/'+str(self.project_id)+'/messages';pg.route(send_pattern,lambda route:pending_send.append(route) if route.request.method=='POST' else route.continue_());pg.get_by_role('button',name='Отправить',exact=True).click()
   for _ in range(20):
    if pending_send:break
    pg.wait_for_timeout(10)
   self.assertTrue(pending_send);pg.locator('.thread').filter(has_text='Второй проект владельца').click();pg.wait_for_function("() => document.querySelector('#project-title').textContent.startsWith('Второй проект владельца')");pg.wait_for_selector('textarea[name=message]');pg.locator('textarea[name=message]').fill('Черновик второго проекта')
   pg.locator('input[type=file]').set_input_files({'name':'second-project.pdf','mimeType':'application/pdf','buffer':self.pdf()});pg.get_by_role('button',name='Загрузить файл',exact=True).click();pg.get_by_text('Сохранён: second-project.pdf',exact=True).wait_for()
   pending_send[0].continue_();pg.locator('#threads').get_by_text('Сообщение первого проекта',exact=True).wait_for();pg.unroute(send_pattern)
   self.assertEqual(pg.locator('textarea[name=message]').input_value(),'Черновик второго проекта');pg.get_by_text('1 вложений сохранено.',exact=True).wait_for();pg.get_by_role('button',name='Отправить',exact=True).click();pg.locator('.conversation').get_by_text('Черновик второго проекта',exact=True).wait_for()
   self.assertEqual(int(self.f.sql('SELECT project_id FROM nd_cc_messages WHERE body=?',params=['Сообщение первого проекта'])[0]['project_id']),self.project_id);self.assertEqual(int(self.f.sql('SELECT project_id FROM nd_cc_messages WHERE body=?',params=['Черновик второго проекта'])[0]['project_id']),other)
   pg.wait_for_load_state('networkidle');client.wait_for_load_state('networkidle');self.assertEqual(errors,[]);browser.close()
 def test_11_free_space_guard_and_binary_office_members(self):
  images=[('tiny.png','iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aOu0AAAAASUVORK5CYII='),('tiny.webp','UklGRiIAAABXRUJQVlA4IBYAAAAwAQCdASoBAAEADsD+JaQAA3AAAAAA')]
  for name,encoded in images:
   r=self.upload(self.owner,name,base64.b64decode(encoded));self.assertEqual(r.status_code,200,r.text)
  for free in [False,0,16777216]:
   value=self.f.php_eval('require $v["root"]."/private/app.php";require $v["root"]."/private/collab/core.php";require $v["root"]."/private/collab/files.php";try{cc_capacity(0,100,1000,$v["free"]);echo "unexpected";}catch(CrmFailure $e){echo $e->status;}',{'root':str(self.f.path),'free':free});self.assertEqual(value,'507')
  import io,zipfile
  buf=io.BytesIO()
  with zipfile.ZipFile(buf,'w') as z:
   z.writestr('[Content_Types].xml','<Types><Override ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/></Types>');z.writestr('_rels/.rels','<Relationships/>');z.writestr('xl/workbook.xml','<workbook/>')
  enabled=self.f.php_eval('echo class_exists("ZipArchive")?"yes":"no";',{})=='yes'
  r=self.upload(self.owner,'sheet.xlsx',buf.getvalue());self.assertEqual(r.status_code,200 if enabled else 503,r.text)
  with zipfile.ZipFile(buf,'a') as z:z.writestr('xl/unrelated.sh','echo unwanted')
  r=self.upload(self.owner,'arbitrary.xlsx',buf.getvalue());self.assertEqual(r.status_code,422 if enabled else 503,r.text)
 def test_12_readonly_storage_inventory_never_deletes_or_exposes_names(self):
  r=self.upload(self.owner,name='private-inventory.pdf');self.assertEqual(r.status_code,200,r.text);root=self.f.path/'private/collaboration-files';orphan=root/secrets.token_hex(32);orphan.write_bytes(b'isolated orphan fixture')
  result=subprocess.run([self.f.php,str(self.f.path/'scripts/check-collab-storage.php')],capture_output=True,text=True);self.assertEqual(result.returncode,1,result.stderr);data=json.loads(result.stdout);self.assertGreaterEqual(data['unreferenced'],1);self.assertTrue(orphan.exists());self.assertNotIn('private-inventory',result.stdout);self.assertNotIn(str(root),result.stdout)
 def test_13_feature_gates_disabled_accounts_and_message_pagination(self):
  saved=dict(self.f.config)
  try:
   self.f.config['client_collaboration_enabled']=False;self.f.write_config();self.assertEqual(self.get(self.owner,'threads').status_code,503);self.assertEqual(self.get(self.customer,'threads').status_code,503)
  finally:self.f.config=saved;self.f.write_config()
  for i in range(35):self.f.sql("INSERT INTO nd_cc_messages(project_id,actor_type,actor_id,body) VALUES (?,'owner',1,?)",params=[self.project_id,'Синтетическое сообщение '+str(i)])
  page1=self.get(self.customer,f'projects/{self.project_id}/messages').json()['items'];page2=self.get(self.customer,f'projects/{self.project_id}/messages',page=2).json()['items'];self.assertEqual(len(page1),30);self.assertEqual(len(page2),5);self.assertFalse(set(m['id'] for m in page1)&set(m['id'] for m in page2))
  gone=self.insert("INSERT INTO nd_projects(customer_id,title) VALUES (?,'Удалённый тестовый проект')",'nd_projects',[self.customer_id]);self.f.sql('DELETE FROM nd_projects WHERE id=?',params=[gone]);self.assertEqual(self.upload(self.owner,project_id=str(gone)).status_code,404)
  shared=self.upload(self.owner,visibility='customer');self.assertEqual(shared.status_code,200,shared.text)
  self.f.sql("UPDATE nd_customer_accounts SET status='disabled' WHERE customer_id=?",params=[self.customer_id]);self.assertEqual(self.get(self.customer,f'projects/{self.project_id}/messages').status_code,401);self.assertEqual(self.customer.get(self.base+'/collab-download.php?mode=customer&id='+str(shared.json()['id'])).status_code,401)
  self.f.sql("UPDATE nd_customers SET status='archived' WHERE id=?",params=[self.customer_id]);self.assertEqual(self.post(self.owner,f'projects/{self.project_id}/messages',body='Запрет').status_code,409)
