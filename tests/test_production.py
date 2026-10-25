"""Stage 10 synthetic accepted-order adapter, persisted drafts, independent static QA. No code execution."""
import json
import secrets
import subprocess
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from test_ai import Ai

class ProductionTransport(BaseHTTPRequestHandler):
 mode='ok';calls=[]
 def log_message(self,*args):pass
 def do_POST(self):
  p=json.loads(self.rfile.read(int(self.headers['Content-Length'])));type(self).calls.append(p);context=p['context']['production'];role=p['agent']
  if self.mode=='unavailable':self.send_response(503);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{}');return
  if role=='production_coordinator':
   source=context['accepted_source'];result={'plan':{'title':'План координатора','steps':[{'key':'draft','title':'Документировать','agent':'production_agent','depends_on':[],'files':['agent.md','installation.md','limitations.md'],'requirement_ids':['R1']}],'requirements':[{'id':'R1','description':source['requirements']['R1'],'file':'agent.md','method':'contains','expected':'Схема агента'}],'budget_micro':100000,'cost_currency':'RUB','max_revisions':2,'limitations':['Только черновики']}}
  elif role=='production_qa':result={'findings':[],'reviewed_hash':context['reviewed_hash'],'limitations':['Только статическая проверка, без запуска кода']}
  else:
   files=[]
   for path in context['step']['files']:
    content='Схема агента\nПроверяемый черновик.' if path=='agent.md' else 'Инструкция. Код не исполнялся.'
    if self.mode=='missing' and path=='agent.md':continue
    if self.mode=='danger' and path=='agent.md':content="<?php system('danger');"
    if self.mode=='runtime' and path=='index.html':content='<html><body>Схема агента</body></html>'
    files.append({'path':path,'content':content,'kind':'documentation' if path.endswith('.md') else 'source'})
   result={'files':files,'notes':'Синтетические данные теста','limitations':['Runtime не проверялся'],'requirement_ids':['R1'],'execution_status':'DRAFT_ONLY'}
   if self.mode=='badpath':result['files'][0]['path']='../config.php'
   if self.mode=='fake_executed':result['execution_status']='EXECUTED'
  o={'agent':role,'summary':'Черновик производства','observations':[],'assumptions':[],'missing_information':[],'suggestions':[],'result':result};self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps({'status':'completed','output':json.dumps(o),'usage':{'input_tokens':100,'output_tokens':100,'actual_micro':None},'model':'controlled-production-fixture'}).encode())

class Production(Ai):
 @classmethod
 def setUpClass(cls):
  super().setUpClass();r=subprocess.run([cls.f.php,str(cls.f.path/'scripts/migrate-production.php'),'up'],capture_output=True,text=True)
  if r.returncode:raise RuntimeError(r.stderr)
  cls.transport=ThreadingHTTPServer(('127.0.0.1',0),ProductionTransport);threading.Thread(target=cls.transport.serve_forever,daemon=True).start();cls.addClassCleanup(cls.transport.server_close);cls.addClassCleanup(cls.transport.shutdown)
  cls.f.config.update(production_enabled=True,production_execution_enabled=True,production_test_mode=True);cls.f.config['ai_provider']['endpoint']='http://127.0.0.1:'+str(cls.transport.server_port);cls.f.write_config()
  for role in ['production_coordinator','production_website','production_application','production_agent','production_design','production_content','production_integration','production_qa']:cls.f.sql('INSERT INTO nd_ai_agents(agent_id,enabled) VALUES (?,1)',params=[role])
 def setUp(self):
  super().setUp();ProductionTransport.mode='ok';self.order=self.insert("INSERT INTO nd_orders(customer_id,number,title,total_amount,status) VALUES (?,?,'Тестовый заказ','288.75','confirmed')",'nd_orders',[self.customer_id,'PROD-'+secrets.token_hex(5)]);self.f.sql('UPDATE nd_projects SET order_id=? WHERE id=?',params=[self.order,self.project_id])
  r=self.cc(self.owner,f'projects/{self.project_id}/documents',kind='specification',title='Принятое ТЗ',fields={'title':'Принятое ТЗ','requirements':'Подготовить документ со схемой агента по явному брифу','acceptance':'Схема агента'},file_ids=[]);rev=r['revision'];rev=self.cc(self.owner,f'revisions/{rev["id"]}/ready',version=int(rev['version']))['revision'];rev=self.cc(self.owner,f'revisions/{rev["id"]}/submit',version=int(rev['version']),confirm=True)['revision'];self.cc(self.customer,f'approvals/{rev["approval"]["id"]}/decide',version=int(rev['approval']['version']),checksum=rev['checksum'],confirm=True,decision='approved',feedback='Принято');self.spec=rev['id'];self.quote=self.approved_price()
  self.f.config.setdefault('production_test_acceptances',{})[str(self.order)]={'spec_revision_id':int(self.spec),'quotation_id':int(self.quote['id']),'service_type':'agent_spec'};self.f.write_config()
  for rate in self.quote['calculation']['rates'].values():
   r=self.ppost('rates/scope',rate_id=int(rate['id']),service_type='agent_spec',active=True,verified_at='2026-01-01 00:00:00',source='Явные синтетические данные теста');self.assertEqual(r.status_code,200,r.text)
 def cc(self,s,route,**d):
  d.setdefault('request_key',secrets.token_hex(32));r=s.post(self.base+('/api.php?r=crm/collab/' if s is self.owner else '/customer-api.php?r=collab/')+route,json=d);self.assertEqual(r.status_code,200,r.text);return r.json()
 def ppost(self,route,**d):return self.post(self.owner,'production/'+route,**d)
 def pget(self,route):return self.get(self.owner,'production/'+route)
 def plan_body(self,files=None):
  paths=files or ['agent.md','installation.md','limitations.md'];return {'title':'Проверяемый план','steps':[{'key':'draft','title':'Подготовить документы','agent':'production_agent','depends_on':[],'files':paths,'requirement_ids':['R1']}],'requirements':[{'id':'R1','description':'Схема агента','file':paths[0],'method':'contains','expected':'Схема агента'}],'budget_micro':100000,'cost_currency':'RUB','max_revisions':2,'limitations':['Нет sandbox для исполнения кода']}
 def plan(self,body=None):
  r=self.ppost('plans',project_id=self.project_id,spec_revision_id=self.spec,plan=body or self.plan_body());self.assertEqual(r.status_code,200,r.text);p=r.json()['record'];r=self.ppost(f'plans/{p["id"]}/validate',version=int(p['version']),checksum=p['checksum']);self.assertEqual(r.status_code,200,r.text);p=r.json()['record'];r=self.ppost(f'plans/{p["id"]}/approve',version=int(p['version']),checksum=p['checksum'],confirm=True);self.assertEqual(r.status_code,200,r.text);return r.json()['record']
 def start(self,p):
  r=self.ppost(f'plans/{p["id"]}/start',version=int(p['version']),confirm=True);self.assertEqual(r.status_code,200,r.text);return r.json()['id']
 def worker(self,run):
  r=subprocess.run([self.f.php,str(self.f.path/'scripts/production-worker.php'),str(run)],capture_output=True,text=True);self.assertEqual(r.returncode,0,r.stderr);return self.pget(f'runs/{run}').json()['record']
 def test_70_static_flow_package_owner_delivery_customer_acceptance(self):
  run=self.start(self.plan());r=self.worker(run);self.assertEqual(r['state'],'READY',r);self.assertEqual(len(r['artifacts']),1);self.assertEqual(r['artifacts'][0]['execution_status'],'DRAFT_ONLY');self.assertEqual(r['qa'][0]['verdict'],'PASS')
  pkg=self.ppost(f'runs/{run}/package');self.assertEqual(pkg.status_code,200,pkg.text);pid=pkg.json()['id'];data=self.pget(f'runs/{run}').json()['record'];p=data['packages'][0];fileurl=self.base+'/collab-download.php?mode=customer&id='+str(p['file_id']);self.assertEqual(self.customer.get(fileurl).status_code,404)
  self.assertEqual(self.ppost(f'packages/{pid}/deliver',version=int(p['version']),checksum=p['manifest_hash'],confirm=True).status_code,409)
  self.assertEqual(self.ppost(f'packages/{pid}/approve',version=int(p['version']),checksum=p['manifest_hash'],confirm=True).status_code,200);p=self.pget(f'runs/{run}').json()['record']['packages'][0];payload={'version':int(p['version']),'checksum':p['manifest_hash'],'confirm':True,'request_key':secrets.token_hex(32)};self.assertEqual(self.ppost(f'packages/{pid}/deliver',**payload).status_code,200);self.assertEqual(self.ppost(f'packages/{pid}/deliver',**payload).status_code,200)
  download=self.customer.get(fileurl);self.assertEqual(download.status_code,200,download.text);manifest=download.json();self.assertEqual(manifest['format'],'neurodelo-delivery-json-v1');self.assertNotIn('db_password',download.text);self.assertNotIn('estimated_micro',download.text);self.assertEqual(self.stranger.get(fileurl).status_code,404)
  data=self.pget(f'runs/{run}').json()['record'];self.assertEqual(data['state'],'DELIVERED');self.assertEqual(self.ppost(f'runs/{run}/finish',version=int(data['version']),confirm=True).status_code,409)
  rev=self.owner.get(self.base+'/api.php?r=crm/collab/revisions/'+str(data['packages'][0]['revision_id'])).json()['revision'];self.cc(self.customer,f'approvals/{rev["approval"]["id"]}/decide',version=int(rev['approval']['version']),checksum=rev['checksum'],confirm=True,decision='approved',feedback='Результат принят');self.f.sql("INSERT INTO nd_project_stages(project_id,position,title,status) VALUES (?,1,'Фактически завершено владельцем','completed')",params=[self.project_id]);data=self.pget(f'runs/{run}').json()['record'];done=self.ppost(f'runs/{run}/finish',version=int(data['version']),confirm=True);self.assertEqual(done.status_code,200,done.text);self.assertEqual(done.json()['profitability']['status'],'PARTIAL');self.assertIsNone(done.json()['profitability']['actual_contribution_minor']);self.assertEqual(self.f.sql('SELECT status FROM nd_orders WHERE id=?',params=[self.order])[0]['status'],'completed')
 def test_71_runtime_unavailable_never_passes_or_delivers(self):
  ProductionTransport.mode='runtime';p=self.plan(self.plan_body(['index.html','installation.md','limitations.md']));run=self.start(p);r=self.worker(run);self.assertEqual(r['state'],'NEEDS_HUMAN');self.assertEqual(r['qa'][0]['verdict'],'NOT_TESTED');self.assertEqual(self.ppost(f'runs/{run}/package').status_code,409);self.assertEqual(self.f.sql('SELECT status FROM nd_orders WHERE id=?',params=[self.order])[0]['status'],'confirmed')
 def test_72_qa_revisions_bounded_and_old_artifacts_preserved(self):
  ProductionTransport.mode='missing';run=self.start(self.plan());r=self.worker(run);self.assertEqual(r['state'],'QA_REJECTED',r);old=r['artifacts'][0]['checksum']
  for cycle in [1,2]:
   revision=self.ppost(f'runs/{run}/revision',version=int(r['version']),reason='Верните отсутствующий результат');self.assertEqual(revision.status_code,200,revision.text);r=self.worker(run);self.assertEqual(r['state'],'QA_REJECTED')
  over=self.ppost(f'runs/{run}/revision',version=int(r['version']),reason='Предел исчерпан');self.assertEqual(over.status_code,200,over.text);r=self.pget(f'runs/{run}').json()['record'];self.assertEqual(r['state'],'NEEDS_HUMAN');self.assertEqual(r['artifacts'][0]['checksum'],old);self.assertEqual(len(r['revisions']),2)
 def test_73_stage9_and_price_source_fail_closed(self):
  config=json.loads(json.dumps(self.f.config))
  try:
   self.f.config['production_test_mode']=False;self.f.write_config();r=self.ppost('plans',project_id=self.project_id,spec_revision_id=self.spec,plan=self.plan_body());self.assertEqual(r.status_code,409);self.assertIn('STAGE9',r.text)
  finally:self.f.config=config;self.f.write_config()
  p=self.plan();self.f.sql('UPDATE nd_projects SET version=version+1 WHERE id=?',params=[self.project_id]);self.assertEqual(self.ppost(f'plans/{p["id"]}/start',version=int(p['version']),confirm=True).status_code,409)
 def test_74_failed_dependency_and_generated_path_guard(self):
  b=self.plan_body();b['steps'].append({'key':'next','title':'Зависимый шаг','agent':'production_content','depends_on':['draft'],'files':['extra.md'],'requirement_ids':['R1']});ProductionTransport.mode='badpath';run=self.start(self.plan(b));r=self.worker(run);self.assertEqual(r['state'],'NEEDS_HUMAN');self.assertIsNone(r['steps'][1]['ai_task_id']);self.assertEqual(r['artifacts'],[])
 def test_75_customer_isolation_and_expense_provenance(self):
  run=self.start(self.plan());self.assertEqual(self.get(self.stranger,f'production/projects/{self.project_id}').status_code,404);r=self.get(self.customer,f'production/projects/{self.project_id}');self.assertEqual(r.status_code,200,r.text);self.assertNotIn('budget',r.text);self.assertNotIn('prompt',r.text);self.assertEqual(self.get(self.customer,f'production/runs/{run}').status_code,403)
  for cat in ['provider','owner_labor','testing','tools','hosting','external','other','tax_and_fees']:
   self.assertEqual(self.ppost(f'runs/{run}/expense',category=cat,amount='0',currency='RUB',verified=True,source='Явно подтверждённый синтетический ноль').status_code,200)
  report=self.pget(f'runs/{run}').json()['record']['costs'];self.assertEqual(report['status'],'COMPLETE');self.assertEqual(report['actual_recorded_minor'],0);self.assertEqual(report['actual_contribution_minor'],28875)

 def test_76_automatic_bounded_revision_and_private_seal(self):
  c=json.loads(json.dumps(self.f.config))
  try:
   self.f.config['production_auto_revisions_enabled']=True;self.f.write_config();ProductionTransport.mode='missing';run=self.start(self.plan())
   for _ in range(3):r=self.worker(run)
   self.assertEqual(r['state'],'NEEDS_HUMAN');self.assertEqual(len(r['revisions']),2);self.assertEqual(len(r['artifacts']),3);self.assertEqual(r['last_error'],'revision_limit')
  finally:self.f.config=c;self.f.write_config()
 def test_77_pause_resume_budget_and_disabled_execution(self):
  run=self.start(self.plan());r=self.pget(f'runs/{run}').json()['record'];self.assertEqual(self.ppost(f'runs/{run}/pause',version=int(r['version']),confirm=True).status_code,200);before=len(ProductionTransport.calls);self.worker(run);self.assertEqual(len(ProductionTransport.calls),before);r=self.pget(f'runs/{run}').json()['record'];self.assertEqual(self.ppost(f'runs/{run}/resume',version=int(r['version']),confirm=True).status_code,200);self.assertEqual(self.worker(run)['state'],'READY')
  b=self.plan_body();b['budget_micro']=1;p=self.plan(b);run=self.start(p);r=self.worker(run);self.assertEqual(r['state'],'NEEDS_HUMAN');self.assertEqual(r['last_error'],'budget_exhausted');self.assertEqual(r['artifacts'],[])
 def test_78_coordinator_and_plan_validation_contracts(self):
  t=self.run_task(self.create('production_coordinator',project_id=self.project_id));self.assertEqual(t['state'],'COMPLETED',t);self.assertEqual(t['artifacts'][0]['effect_entity'],'production_plans');p=self.pget('plans/'+str(t['artifacts'][0]['effect_id'])).json()['record'];self.assertEqual(p['state'],'DRAFT')
  b=self.plan_body();b['steps'][0]['depends_on']=['draft'];self.assertEqual(self.ppost('plans',project_id=self.project_id,spec_revision_id=self.spec,plan=b).status_code,422)
  b=self.plan_body();b['steps'][0]['agent']='production_qa';self.assertEqual(self.ppost('plans',project_id=self.project_id,spec_revision_id=self.spec,plan=b).status_code,422)
 def test_79_concurrent_delivery_exactly_once(self):
  from concurrent.futures import ThreadPoolExecutor
  run=self.start(self.plan());self.worker(run);pkg=self.ppost(f'runs/{run}/package');self.assertEqual(pkg.status_code,200,pkg.text);p=self.pget(f'runs/{run}').json()['record']['packages'][0];self.assertEqual(self.ppost(f'packages/{p["id"]}/approve',version=int(p['version']),checksum=p['manifest_hash'],confirm=True).status_code,200);p=self.pget(f'runs/{run}').json()['record']['packages'][0]
  def deliver(_):
   code='require $v["root"]."/private/app.php";require $v["root"]."/private/ai/routes.php";echo json_encode(prod_package_action($v["id"],"deliver",["version"=>$v["version"],"checksum"=>$v["hash"],"confirm"=>true,"request_key"=>$v["key"]]));'
   return json.loads(self.f.php_eval(code,{'root':str(self.f.path),'id':p['id'],'version':int(p['version']),'hash':p['manifest_hash'],'key':secrets.token_hex(32)}))
  with ThreadPoolExecutor(max_workers=2) as pool:out=list(pool.map(deliver,range(2)))
  self.assertTrue(all(r['ok'] for r in out));self.assertEqual(self.f.sql("SELECT COUNT(*) n FROM nd_cc_documents WHERE project_id=? AND kind='deliverable'",params=[self.project_id])[0]['n'],1)
 def test_80_critical_qa_and_legacy_file_visibility_cannot_bypass_approval(self):
  ProductionTransport.mode='danger';run=self.start(self.plan());r=self.worker(run);self.assertEqual(r['state'],'QA_REJECTED');self.assertTrue(any(f['severity']=='critical' and f['result']=='FAIL' for f in r['findings']));self.assertEqual(self.ppost(f'runs/{run}/package').status_code,409)
  ProductionTransport.mode='ok';run=self.start(self.plan());self.worker(run);self.assertEqual(self.ppost(f'runs/{run}/package').status_code,200);p=self.pget(f'runs/{run}').json()['record']['packages'][0];f=self.f.sql('SELECT * FROM nd_cc_files WHERE id=?',params=[p['file_id']])[0]
  legacy=self.owner.post(self.base+'/api.php?r=crm/collab/files/'+str(f['id']),json={'version':int(f['version']),'visibility':'customer','archived':False,'request_key':secrets.token_hex(32)});self.assertEqual(legacy.status_code,409,legacy.text);self.assertEqual(self.customer.get(self.base+'/collab-download.php?mode=customer&id='+str(f['id'])).status_code,404)

 def test_81_browser_owner_board_plan_and_mobile(self):
  import os
  from pathlib import Path
  from playwright.sync_api import sync_playwright
  plan=self.plan();run=self.start(plan);self.worker(run);errors=[]
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);ctx=browser.new_context(viewport={'width':1440,'height':1000});ctx.add_cookies([{'name':c.name,'value':c.value,'url':self.base} for c in self.owner.cookies]);pg=ctx.new_page();pg.on('pageerror',lambda e:errors.append(str(e)))
   pg.goto(self.base+'/production.php#run/'+str(run));pg.get_by_role('heading',name='Производство №'+str(run),exact=True).wait_for();self.assertEqual(pg.locator('#prod-error').inner_text(),'');pg.get_by_role('heading',name='Проверка качества',exact=True).wait_for()
   evidence=Path('/tmp/neuro-stage10-ux');evidence.mkdir(exist_ok=True);pg.screenshot(path=str(evidence/'owner-run.png'),full_page=True)
   pg.goto(self.base+'/production.php#overview');pg.get_by_role('heading',name='Готовы к отправке',exact=True).wait_for();pg.set_viewport_size({'width':390,'height':844});self.assertTrue(pg.evaluate('document.documentElement.scrollWidth<=innerWidth'));pg.screenshot(path=str(evidence/'owner-mobile.png'),full_page=True)
   pg.goto(self.base+'/production.php#capabilities');pg.get_by_text('Расписание worker не подтверждено.',exact=True).wait_for();pg.wait_for_load_state('networkidle');self.assertEqual(errors,[]);self.assertEqual(pg.locator('#prod-error').inner_text(),'');browser.close()

 def test_82_reserved_budget_covers_all_provider_retries(self):
  run=self.start(self.plan());self.worker(run)
  rows=self.f.sql('SELECT s.budget_total_micro,a.max_attempts,u.estimated_micro FROM nd_prod_steps s JOIN nd_ai_tasks a ON a.id=s.ai_task_id JOIN nd_ai_attempts x ON x.task_id=a.id JOIN nd_ai_usage u ON u.attempt_id=x.id WHERE s.run_id=?',params=[run]);self.assertTrue(rows)
  for r in rows:self.assertGreaterEqual(int(r['budget_total_micro']),int(r['max_attempts'])*int(r['estimated_micro']))

for _name in dir(Ai):
 if _name.startswith('test_'):setattr(Production,_name,None)
del Ai
