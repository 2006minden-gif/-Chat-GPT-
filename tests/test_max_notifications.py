"""MAX integration uses a pure injected transport, never real bots or tokens."""
import hashlib,json,os,shutil,time
from pathlib import Path
import requests
import test_prelaunch as fixture

class MaxNotifications(fixture.Prelaunch):
 def setUp(self):
  shutil.rmtree(self.path/'private/notifications/runtime',ignore_errors=True)
  (self.path/'max-calls.json').unlink(missing_ok=True)
 def run_php(self,code,**extra):
  bootstrap=r'''
require $v['root'].'/private/app.php';require $v['root'].'/private/notifications/max.php';
$mock=function($method,$path,$token,$body)use($v){
 $log=$v['root'].'/max-calls.json';$rows=is_file($log)?json_decode(file_get_contents($log),true):[];
 $rows[]=['method'=>$method,'path'=>$path,'body'=>$body];file_put_contents($log,json_encode($rows));
 if(($v['broken']??false)&&str_starts_with($path,'/messages'))throw new RuntimeException('max_api_failed');
 if($path==='/me')return ['is_bot'=>true,'user_id'=>1234,'username'=>'synthetic_bot'];
 if($path==='/subscriptions')return ['success'=>true];
 return ['message'=>['body'=>['mid'=>'synthetic-message']]];
};
'''
  return json.loads(self.php_eval(bootstrap+code,{'root':str(self.path),**extra}))
 def connect(self):return self.run_php("echo json_encode(max_connect('SYNTHETIC_NOT_A_REAL_TOKEN',$mock));")
 def event(self,code,user=456):return {'update_type':'message_created','message':{'sender':{'user_id':user,'is_bot':False},'recipient':{'chat_type':'dialog'},'body':{'text':code}}}
 def state(self):return json.loads((self.path/'private/notifications/runtime/state.json').read_text())
 def bind(self):
  result=self.connect();state=self.state()
  response=requests.post(self.base+'/max-webhook.php',json=self.event(result['command']),headers={'X-Max-Bot-Api-Secret':state['webhook_secret']})
  self.assertEqual(response.status_code,200);self.assertIn('pending_user_id',self.state())
  self.run_php("max_confirm($mock);echo json_encode(['ok'=>true]);")
 def add_lead(self):
  self.sql("INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES ('PRIVATE_NAME','private@example.com','Сайт или лендинг','PRIVATE_DESCRIPTION','',?)",params=[int(time.time())])
  return self.sql('SELECT MAX(id) AS id FROM nd_leads')[0]['id']
 def test_authorization_and_csrf_are_required(self):
  self.assertEqual(requests.get(self.api('notifications/max')).status_code,401)
  self.assertEqual(requests.post(self.api('notifications/max'),json={'action':'connect','token':'SYNTHETIC_NOT_A_REAL_TOKEN'}).status_code,401)
  session,headers=self.owner()
  self.assertEqual(session.post(self.api('notifications/max'),json={'action':'disable'}).status_code,403)
  bad={**headers,'Origin':'https://evil.invalid'}
  self.assertEqual(session.post(self.api('notifications/max'),headers=bad,json={'action':'disable'}).status_code,403)
  self.assertEqual(session.post(self.api('notifications/max'),headers=headers,json={'action':'connect','token':'bad\r\nheader'}).status_code,422)
 def test_pairing_requires_secret_code_private_chat_and_owner_confirmation(self):
  result=self.connect();state=self.state();secret=state['webhook_secret']
  for header in ['', 'a'*64]:
   response=requests.post(self.base+'/max-webhook.php',json=self.event(result['command']),headers={'X-Max-Bot-Api-Secret':header});self.assertEqual(response.status_code,403)
  for text in ['/connect '+'a'*32,'hello']:
   self.assertEqual(requests.post(self.base+'/max-webhook.php',json=self.event(text),headers={'X-Max-Bot-Api-Secret':secret}).status_code,200)
   self.assertNotIn('pending_user_id',self.state())
  event=self.event(result['command']);event['message']['recipient']['chat_type']='chat'
  requests.post(self.base+'/max-webhook.php',json=event,headers={'X-Max-Bot-Api-Secret':secret});self.assertNotIn('pending_user_id',self.state())
  requests.post(self.base+'/max-webhook.php',json=self.event(result['command']),headers={'X-Max-Bot-Api-Secret':secret})
  self.assertFalse(self.state()['enabled'])
  self.run_php("max_confirm($mock);echo json_encode(['ok'=>true]);")
  self.assertTrue(self.state()['enabled']);self.assertEqual(self.state()['user_id'],456)
  # Replayed pairing command cannot change the recipient.
  requests.post(self.base+'/max-webhook.php',json=self.event(result['command'],999),headers={'X-Max-Bot-Api-Secret':secret})
  self.assertNotIn('pending_user_id',self.state());self.assertEqual(self.state()['user_id'],456)
  session,_=self.owner();status=session.get(self.api('notifications/max')).json()
  self.assertTrue(status['connected']);self.assertNotIn('token',status);self.assertNotIn(secret,json.dumps(status));self.assertNotIn('SYNTHETIC_NOT_A_REAL_TOKEN',json.dumps(status))
  self.assertEqual((self.path/'private/notifications/runtime/state.json').stat().st_mode&0o777,0o600)
 def test_expired_pair_is_ignored(self):
  result=self.connect();secret=self.state()['webhook_secret']
  self.run_php("max_locked(function(){$s=max_read();$s['pair_expires']=time()-1;max_write($s);});echo json_encode(['ok'=>true]);")
  requests.post(self.base+'/max-webhook.php',json=self.event(result['command']),headers={'X-Max-Bot-Api-Secret':secret});self.assertNotIn('pending_user_id',self.state())
 def test_failures_keep_queue_and_retry_does_not_resend_success(self):
  self.bind();before=self.state()['cursor'];lead=self.add_lead()
  result=self.run_php('echo json_encode(max_pump(1,$mock));',broken=True)
  self.assertEqual(result['sent'],0);self.assertEqual(self.state()['cursor'],before)
  self.assertEqual(self.state()['error_code'],'max_api_failed')
  self.assertTrue(self.run_php('echo json_encode(max_pump(1,$mock));')['deferred'])
  self.run_php("max_locked(function(){$s=max_read();$s['retry_at']=0;max_write($s);});echo json_encode(['ok'=>true]);")
  self.assertEqual(self.run_php('echo json_encode(max_pump(1,$mock));')['sent'],1)
  self.assertEqual(self.state()['cursor'],lead)
  self.assertEqual(self.run_php('echo json_encode(max_pump(1,$mock));')['sent'],0)
  calls=json.loads((self.path/'max-calls.json').read_text());texts=json.dumps(calls,ensure_ascii=False)
  self.assertNotIn('PRIVATE_NAME',texts);self.assertNotIn('private@example.com',texts);self.assertNotIn('PRIVATE_DESCRIPTION',texts)
  self.assertIn('Новая заявка №'+str(lead),texts)
 def test_lower_id_committing_after_higher_id_is_not_lost(self):
  self.bind()
  self.sql("INSERT INTO nd_leads(id,name,contact,service,idea,notes,created) VALUES (1000000,'TEST','t@example.com','Сайт или лендинг','test','',?)",params=[int(time.time())])
  self.assertEqual(self.run_php('echo json_encode(max_pump(1,$mock));')['sent'],1)
  self.sql("INSERT INTO nd_leads(id,name,contact,service,idea,notes,created) VALUES (999999,'TEST','t@example.com','Сайт или лендинг','test','',?)",params=[int(time.time())])
  self.assertEqual(self.run_php('echo json_encode(max_pump(1,$mock));')['sent'],1)
  self.assertIn(999999,self.state()['completed_ids']);self.assertIn(1000000,self.state()['completed_ids'])
 def test_symlink_state_refused(self):
  runtime=self.path/'private/notifications/runtime';runtime.mkdir();target=self.path/'untouched';target.write_text('KEEP');(runtime/'state.json').symlink_to(target)
  result=self.run_php("try{max_read();echo '{}';}catch(Throwable $e){echo json_encode(['error'=>$e->getMessage()]);}")
  self.assertEqual(result['error'],'max_storage_unsafe');self.assertEqual(target.read_text(),'KEEP')
 def test_max_profile_contact_validation_and_public_links(self):
  contact='https://max.ru/u/f9LHodD0cOKgQK_L9u-un2-ttcwfRfu_-_a-2Ai_usx_frNtjq1jjuiZSLE'
  result=self.run_php("echo json_encode(['valid'=>valid_contact($v['contact']),'bad'=>valid_contact('https://max.ru.evil.invalid/u/example')]);",contact=contact)
  self.assertTrue(result['valid']);self.assertFalse(result['bad'])
  for route in ['/','/services.php']:
   page=requests.get(self.base+route)
   if route=='/services.php' and page.status_code==404:continue # fixture router does not expose the independent guide
   self.assertIn(contact,page.text);self.assertIn('https://t.me/minden2006',page.text)
 def test_settings_browser_sends_secret_only_in_authenticated_body(self):
  from playwright.sync_api import sync_playwright
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox'])
   try:
    page=browser.new_page(viewport={'width':375,'height':900});page.goto(self.base+'/studio.php')
    page.locator('#password').fill(self.password);page.locator('#login-form button').click();page.locator('#dashboard').wait_for(state='visible')
    page.locator('.max-settings summary').click();seen=[]
    def mock(route):
     if route.request.method=='GET':route.fulfill(status=200,content_type='application/json',body=json.dumps({'configured':True,'connected':False,'pair_received':False}));return
     seen.append(route.request)
     route.fulfill(status=200,content_type='application/json',body=json.dumps({'ok':True,'command':'/connect '+'b'*32,'bot_url':'https://max.ru/synthetic_bot'}))
    page.route('**/api.php?r=notifications/max',mock)
    page.locator('#max-token').fill('SYNTHETIC_NOT_A_REAL_TOKEN');page.locator('#max-settings-form button').click();page.locator('#max-pairing').wait_for(state='visible')
    self.assertEqual(page.locator('#max-token').input_value(),'');self.assertNotIn('SYNTHETIC',page.url)
    self.assertEqual(seen[0].post_data_json['token'],'SYNTHETIC_NOT_A_REAL_TOKEN');self.assertTrue(seen[0].headers['x-csrf-token'])
    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
   finally:browser.close()

for name in vars(fixture.Prelaunch):
 if name.startswith('test_') and name not in vars(MaxNotifications):setattr(MaxNotifications,name,None)
