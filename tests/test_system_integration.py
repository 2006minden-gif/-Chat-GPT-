"""Stage 11 manual handoff on real PHP/MySQL/HTTP, no AI credentials or calls."""
import json
import secrets
import subprocess
import time
import unittest
from pathlib import Path
from test_collaboration import Collaboration

class SystemIntegration(Collaboration):
 @classmethod
 def setUpClass(cls):
  super().setUpClass()
  for r in ['migrate-billing.php','migrate-ai.php','migrate-pricing.php','migrate-production.php','migrate-manual.php']:
   x=subprocess.run([cls.f.php,str(cls.f.path/'scripts'/r),'up'],capture_output=True,text=True)
   if x.returncode:raise RuntimeError(r+": "+x.stderr)
  cls.f.config.update(manual_handoff_enabled=True,ai_enabled=False,production_enabled=False);cls.f.write_config()
 def setUp(self):
  super().setUp();self.task=self.insert("INSERT INTO nd_tasks(title,description) VALUES ('Подготовить документ','Только синтетические материалы')",'nd_tasks');self.f.sql('INSERT INTO nd_task_projects(task_id,project_id) VALUES (?,?)',params=[self.task,self.project_id])
  r=self.post(self.owner,f'projects/{self.project_id}/documents',kind='specification',title='Принятое ТЗ',fields={'title':'Принятое ТЗ','requirements':'Составить документ','acceptance':'Схема агента'},file_ids=[]).json()['revision'];r=self.post(self.owner,f'revisions/{r["id"]}/ready',version=int(r['version'])).json()['revision'];r=self.post(self.owner,f'revisions/{r["id"]}/submit',version=int(r['version']),confirm=True).json()['revision'];x=self.post(self.customer,f'approvals/{r["approval"]["id"]}/decide',version=int(r['approval']['version']),checksum=r['checksum'],confirm=True,decision='approved',feedback='Согласовано');self.assertEqual(x.status_code,200,x.text);self.spec=r['id']
 def mget(self,path,s=None):return self.get(s or self.owner,'manual/'+path)
 def mpost(self,path,**d):return self.post(self.owner,'manual/'+path,**d)
 def job(self,key=None):
  r=self.mpost('prepare',project_id=self.project_id,task_id=self.task,spec_revision_id=self.spec,confirm=True,request_key=key or secrets.token_hex(32));self.assertEqual(r.status_code,200,r.text);return self.mget('jobs/'+str(r.json()['id'])).json()['record']
 def body(self,code=False,missing=False):
  files=[{'path':p,'content':'Схема агента. Синтетическая инструкция.','kind':'documentation'} for p in ['agent.md','installation.md','limitations.md'] if not(missing and p=='installation.md')]
  if code:files.append({'path':'index.html','content':'<h1>Схема агента</h1>','kind':'source'})
  return {'files':files,'requirements':[{'id':'R1','file':'agent.md','method':'contains','expected':'Схема агента'}]}
 def imp(self,j,**body):
  r=self.mpost(f'jobs/{j["id"]}/import',version=int(j['version']),**(body or self.body()));self.assertEqual(r.status_code,200,r.text);return self.result(r.json()['id'])
 def result(self,id):return self.mget('results/'+str(id)).json()['record']
 def action(self,r,action,expect=200,**d):
  x=self.mpost(f'results/{r["id"]}/{action}',version=int(r['version']),checksum=r['checksum'],confirm=True,**d);self.assertEqual(x.status_code,expect,x.text);return self.result(r['id'])
 def test_01_manual_end_to_end_without_provider_and_exact_delivery(self):
  k=secrets.token_hex(32);j=self.job(k);self.assertEqual(self.job(k)['id'],j['id']);self.assertIn('РУЧНАЯ ПЕРЕДАЧА',j['assignment']);self.assertFalse(self.f.config['ai_enabled']);r=self.imp(j)
  self.action(r,'deliver',409);r=self.action(r,'check');self.assertEqual(r['state'],'READY');self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_ai_tasks')[0]['n'],0);r=self.action(r,'approve');self.assertIsNone(r['file_id']);r=self.action(r,'deliver');self.assertEqual(r['state'],'DELIVERED')
  url=self.base+'/collab-download.php?mode=customer&id='+str(r['file_id']);x=self.customer.get(url);self.assertEqual(x.status_code,200,x.text);self.assertEqual(x.json()['files'][0]['path'],'agent.md');self.assertEqual(self.stranger.get(url).status_code,404);self.assertIn('attachment',x.headers['Content-Disposition']);self.action(r,'deliver');self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_cc_documents WHERE project_id=? AND kind=\'deliverable\'',params=[self.project_id])[0]['n'],1)
  f=self.f.sql('SELECT version FROM nd_cc_files WHERE id=?',params=[r['file_id']])[0];self.assertEqual(self.post(self.owner,'files/'+str(r['file_id']),version=int(f['version']),visibility='customer',archived=False).status_code,409)
 def test_02_code_not_executed_and_missing_docs_revision(self):
  j=self.job();r=self.imp(j,**self.body(code=True));r=self.action(r,'check');self.assertEqual(r['state'],'BLOCKED');self.assertIn('NOT_TESTED',r['review_json']);self.action(r,'approve',409);r=self.action(r,'changes',feedback='Убрать непроверенный код; передать документацию');j=self.mget('jobs/'+str(j['id'])).json()['record'];r2=self.imp(j,**self.body(missing=True));r2=self.action(r2,'check');self.assertEqual(r2['state'],'QA_REJECTED');self.assertEqual(self.result(r['id'])['state'],'CHANGES_REQUESTED');self.assertNotEqual(r['checksum'],r2['checksum'])
 def test_03_stale_source_csrf_ownership_and_methods(self):
  j=self.job();self.assertEqual(self.mget('jobs/'+str(j['id']),self.customer).status_code,403);self.assertEqual(self.mget('jobs/'+str(j['id']),self.stranger).status_code,403)
  h=self.owner.headers.pop('X-CSRF-Token');self.assertEqual(self.mpost('prepare',project_id=self.project_id).status_code,403);self.owner.headers['X-CSRF-Token']=h
  self.f.sql('UPDATE nd_tasks SET version=version+1 WHERE id=?',params=[self.task]);self.assertEqual(self.mpost(f'jobs/{j["id"]}/import',version=int(j['version']),**self.body()).status_code,409);self.assertEqual(self.mget('prepare').status_code,404)
 def test_04_reject_unsafe_files_tampered_approval_and_archive(self):
  j=self.job();b=self.body();b['files'][0]['path']='../config.php';self.assertEqual(self.mpost(f'jobs/{j["id"]}/import',version=int(j['version']),**b).status_code,422)
  b=self.body();b['files'][0]['content']='<?php system("blocked");';self.assertEqual(self.mpost(f'jobs/{j["id"]}/import',version=int(j['version']),**b).status_code,422);r=self.imp(j);r=self.action(r,'check');self.assertEqual(self.mpost(f'results/{r["id"]}/approve',version=int(r['version']),checksum='0'*64,confirm=True).status_code,409)
  self.f.sql('UPDATE nd_projects SET archived_at=UTC_TIMESTAMP() WHERE id=?',params=[self.project_id]);self.action(r,'approve',409)
 def test_05_migration_roundtrip_guards_and_old_rows(self):
  # Existing manual records from earlier tests must prevent destructive rollback.
  self.job();x=subprocess.run([self.f.php,str(self.f.path/'scripts/migrate-manual.php'),'down'],capture_output=True,text=True);self.assertEqual(x.returncode,1);self.assertIn('rollback_refused_nonempty_auth',x.stderr)
  x=subprocess.run([self.f.php,str(self.f.path/'scripts/migrate-production.php'),'down'],capture_output=True,text=True);self.assertEqual(x.returncode,1);self.assertIn('newer_migration_applied',x.stderr)
 def test_06_browser_copy_import_check_and_approval(self):
  import os
  from playwright.sync_api import sync_playwright
  j=self.job();errors=[]
  with sync_playwright() as p:
   b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);ctx=b.new_context(viewport={'width':390,'height':844},permissions=['clipboard-read','clipboard-write']);ctx.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);pg=ctx.new_page();pg.on('pageerror',lambda e:errors.append(str(e)));pg.on('dialog',lambda d:d.accept());pg.goto(self.base+'/handoff.php#job/'+str(j['id']));pg.get_by_role('button',name='Скопировать задание',exact=True).click();pg.get_by_text('Задание скопировано. Проверьте текст перед переносом.',exact=True).wait_for();self.assertIn('РУЧНАЯ ПЕРЕДАЧА',pg.evaluate('navigator.clipboard.readText()'));pg.get_by_label('Результат JSON: files и requirements',exact=True).fill(json.dumps(self.body(),ensure_ascii=False));pg.route('**/api.php?**',lambda route: route.fulfill(status=200,content_type='text/html',body='<html>Unrelated page</html>') if '/import' in route.request.url else route.continue_());pg.get_by_role('button',name='Загрузить результат',exact=True).click();pg.get_by_text('Ответ сервера не подтверждён. Черновик сохранён.',exact=True).wait_for();self.assertEqual(json.loads(pg.get_by_label('Результат JSON: files и requirements',exact=True).input_value()),self.body());self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_manual_results WHERE job_id=?',params=[j['id']])[0]['n'],0);pg.unroute('**/api.php?**');pg.get_by_role('button',name='Загрузить результат',exact=True).click();pg.get_by_role('button',name='Отправить на проверку',exact=True).click();pg.get_by_role('button',name='Утвердить результат',exact=True).click();pg.get_by_role('button',name='Передать клиенту',exact=True).wait_for();self.assertEqual(pg.locator('#handoff-error').inner_text(),'');self.assertTrue(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'));out=Path('/tmp/neuro-stage11-ux');out.mkdir(exist_ok=True);pg.screenshot(path=str(out/'manual-owner-mobile.png'),full_page=True);pg.wait_for_load_state('networkidle');self.assertEqual(errors,[]);b.close()
 def test_07_measured_bounded_lists(self):
  j=self.job();times=[]
  for _ in range(5):
   t=time.perf_counter();r=self.mget('jobs&page=1');times.append(round((time.perf_counter()-t)*1000,3));self.assertEqual(r.status_code,200);self.assertLessEqual(len(r.json()['items']),20)
  Path('/tmp/neuro-stage11-performance.json').write_text(json.dumps({'endpoint':'manual/jobs&page=1','samples_ms':times,'synthetic_jobs':int(self.f.sql('SELECT COUNT(*) n FROM nd_manual_jobs')[0]['n']),'environment':'loopback PHP8.4 MySQL5.7, not hosting benchmark'}))

 def test_08_independent_process_delivery_idempotency(self):
  from concurrent.futures import ThreadPoolExecutor
  j=self.job();r=self.imp(j);r=self.action(r,'check');r=self.action(r,'approve')
  def deliver(_):
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/collab/routes.php";require $v["root"]."/private/manual/routes.php";echo json_encode(mh_action($v["id"],"deliver",["version"=>$v["version"],"checksum"=>$v["hash"],"confirm"=>true,"request_key"=>$v["key"]]));'
   return json.loads(self.f.php_eval(code,{'root':str(self.f.path),'id':r['id'],'version':int(r['version']),'hash':r['checksum'],'key':secrets.token_hex(32)}))
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(deliver,range(2)))
  self.assertTrue(all(x['ok'] for x in out));self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_cc_documents WHERE project_id=? AND kind='deliverable'",params=[self.project_id])[0]['n'],1)

 def test_09_shared_navigation_flags_and_real_routes(self):
  self.assertEqual(self.mget('jobs&project_id=invalid').status_code,422)
  pages=['/workspace.php','/portal.php','/collaboration.php?mode=owner','/handoff.php']
  for path in pages:
   r=self.owner.get(self.base+path);self.assertEqual(r.status_code,200,r.text);self.assertIn('product-navigation',r.text)
  html=self.owner.get(self.base+'/handoff.php').text;self.assertIn('Каталог услуг и интерактивный бриф пока недоступны',html);self.assertNotIn('href="/ai.php',html);self.assertNotIn('href="/production.php',html);self.assertIn('href="/handoff.php',html)

for name in dir(Collaboration):
 if name.startswith('test_'):setattr(SystemIntegration,name,None)
del Collaboration
