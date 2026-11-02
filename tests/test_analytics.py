"""Notice-based public counter; preserved earlier refusals, real browser transports/CSP, private-area exclusions. Synthetic only."""
import json,hashlib,subprocess,requests,unittest,os
from pathlib import Path
import test_prelaunch as prelaunch
class Analytics(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  class F(prelaunch.Prelaunch):pass
  cls.f=F;F.setUpClass();cls.addClassCleanup(F.doClassCleanups);cls.base=F.base
  F.config.update(privacy_policy_version='',privacy_policy_approved=False);F.write_config()
  p=F.path/'private/legal/privacy-2026-11-02-v4.json';d=json.loads(p.read_text());d.update(activation_requested=True,analytics_approved=True);p.write_text(json.dumps(d,ensure_ascii=False))
 def post(self,s,choice):return s.post(self.base+'/analytics-status.php',json={'version':'analytics-2026-11-02-v1','choice':choice},headers={'Origin':self.base})
 def test_minimal_signed_receipt_owner_gate_and_private_csp(self):
  s=requests.Session();d=s.get(self.base+'/analytics-status.php').json();self.assertTrue(d['eligible']);self.assertIsNone(d['receipt']);self.assertEqual(d['mode'],'public_notice');self.assertEqual(d['version'],'analytics-2026-11-02-v2');policy=requests.get(self.base+'/privacy.php').text;self.assertIn('без отдельного окна',policy);self.assertNotIn('только после отдельного согласия',policy);r=self.post(s,'allow');self.assertEqual(r.status_code,200,r.text);receipt=r.json()['receipt'];self.assertEqual(set(receipt),{'version','time','choice'});self.assertEqual(receipt['version'],'analytics-2026-11-02-v1');self.assertIn('HttpOnly',r.headers['Set-Cookie']);self.assertEqual(s.get(self.base+'/analytics-status.php').json()['receipt'],receipt)
  s.cookies.clear();s.cookies.set('neuro_analytics','tampered');self.assertIsNone(s.get(self.base+'/analytics-status.php').json()['receipt']);s.cookies.clear();self.assertEqual(s.post(self.base+'/analytics-status.php',json={'version':'old','choice':'allow'},headers={'Origin':self.base}).status_code,409);self.assertEqual(s.post(self.base+'/analytics-status.php',json={'choice':'allow'},headers={'Origin':'https://foreign.invalid'}).status_code,403)
  for cookie in ['nd_session','nd_customer','__Host-nd_customer','nd_prospect','__Host-nd_prospect']:
   t=requests.Session();t.cookies.set(cookie,'SYNTHETIC');self.assertFalse(t.get(self.base+'/analytics-status.php').json()['eligible']);self.assertNotIn('mc.yandex',t.get(self.base+'/').headers.get('Content-Security-Policy',''));self.assertEqual(self.post(t,'allow').status_code,409)
  for path in ['/studio.php','/customer.php','/portal.php','/documents.php?mode=owner','/payment.php','/prospect.php','/max.php','/max-link.php','/contract-settings.php','/services.php?token=SYNTHETIC','/portfolio-case.php?preview=1','/customer.php?invite=SYNTHETIC']:
   r=requests.get(self.base+path);self.assertNotIn('mc.yandex',r.headers.get('Content-Security-Policy',''));self.assertNotIn('metrika/tag.js',r.text)
  public=requests.get(self.base+'/');self.assertIn('no-store',public.headers.get('Cache-Control',''));self.assertEqual(public.headers.get('Vary'),'Cookie');self.assertIn('mc.yandex.ru/watch/114024456',public.text);self.assertLess(public.text.index('/analytics.js'),public.text.index('</head>'));self.assertLess(public.text.index('mc.yandex.ru/watch/114024456'),public.text.index('<header'));self.post(s,'allow');self.assertIn('mc.yandex.ru/watch/114024456',s.get(self.base+'/').text);self.assertNotIn('mc.yandex.ru/watch/',s.get(self.base+'/?token=SYNTHETIC').text);self.post(s,'deny');self.assertNotIn('mc.yandex.ru/watch/',s.get(self.base+'/').text)
 def browser(self):
  from playwright.sync_api import sync_playwright
  pw=sync_playwright().start();b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);return pw,b
 def sdk(self,p,requests_seen):
  def handle(route):
   requests_seen.append(route.request.url)
   if '/metrika/tag.js' in route.request.url:
    route.fulfill(content_type='application/javascript',body="""window.__calls=(window.ym?.a||[]).map(x=>Array.from(x));window.__recordable=Array.from(document.querySelectorAll('input,textarea,select,[contenteditable]')).filter(n=>!n.classList.contains('ym-disable-keys')).length;window.ym=(...args)=>{window.__calls.push(args);};window.__timer=setInterval(()=>{fetch('https://mc.yandex.ru/watch/114024456?SYNTHETIC_TEST=1').catch(()=>{});navigator.sendBeacon('https://mc.yandex.ru/watch/114024456?SYNTHETIC_TEST=2','');const image=new Image();image.src='https://mc.yandex.ru/watch/114024456?SYNTHETIC_TEST=3';},100);""")
   else:route.fulfill(status=204,body='')
  p.route('https://mc.yandex.ru/**',handle)
 def test_browser_automatic_start_masking_and_current_page_legacy_optout(self):
  from playwright.sync_api import expect
  pw,b=self.browser()
  try:
   p=b.new_page(viewport={'width':375,'height':812});seen=[];self.sdk(p,seen);p.goto(self.base+'/services.php?service=ai');p.wait_for_function('()=>window.__calls?.length>0');self.assertEqual(p.locator('.nd-analytics,.nd-analytics-settings').count(),0);self.assertIsNone(p.request.get(self.base+'/analytics-status.php').json()['receipt']);p.locator('#brief-goal').fill('SYNTHETIC_PRIVATE_PERSON');p.locator('#service-brief button[type=submit]').click();p.wait_for_timeout(200);self.assertGreater(len(seen),0);p.wait_for_function('()=>window.__calls?.length>0');self.assertEqual(p.evaluate('window.__recordable'),0);calls=p.evaluate('window.__calls');self.assertEqual(calls[0][0],114024456);self.assertEqual(calls[0][1],'init');self.assertTrue(calls[0][2]['webvisor']);self.assertEqual(calls[0][2]['url'],self.base+'/services.php');self.assertNotIn('SYNTHETIC_PRIVATE_PERSON',json.dumps(calls));self.assertTrue(p.locator('#brief').evaluate("n=>n.classList.contains('ym-hide-content')"));self.assertTrue(p.locator('#brief-result').evaluate("n=>n.classList.contains('ym-hide-content')"));self.assertTrue(p.locator('#telegram-brief').evaluate("n=>n.classList.contains('ym-disable-tracklink')"))
   p.evaluate("const d=document.createElement('dialog');d.id='ai-chat';d.innerHTML='<textarea>SYNTHETIC_DYNAMIC_PRIVATE</textarea>';document.body.append(d)");p.wait_for_timeout(100);self.assertTrue(p.locator('#ai-chat').evaluate("n=>n.classList.contains('ym-hide-content')"));self.assertTrue(p.locator('#ai-chat textarea').evaluate("n=>n.classList.contains('ym-disable-keys')"));p.evaluate("document.cookie='_ym_uid=SYNTHETIC; Path=/'");p.request.post(self.base+'/analytics-status.php',data={'version':'analytics-2026-11-02-v1','choice':'deny'},headers={'Origin':self.base});p.evaluate("new BroadcastChannel('neuro-analytics').postMessage('deny')");p.wait_for_function('()=>!window.neuroAnalytics.isRunning()');p.wait_for_timeout(150);after=len(seen);p.wait_for_timeout(500);self.assertEqual(len(seen),after);self.assertFalse(any(c['name'].startswith('_ym_') for c in p.context.cookies()));self.assertIn('destruct',[c[1] for c in p.evaluate('window.__calls')]);self.assertFalse(p.evaluate('document.documentElement.scrollWidth>innerWidth'));p.reload();p.wait_for_timeout(300);self.assertEqual(len(seen),after)
  finally:b.close();pw.stop()
 def test_browser_refusal_reload_sensitive_url_and_private_referrer(self):
  from playwright.sync_api import expect
  pw,b=self.browser()
  try:
   p=b.new_page();seen=[];self.sdk(p,seen);p.request.post(self.base+'/analytics-status.php',data={'version':'analytics-2026-11-02-v1','choice':'deny'},headers={'Origin':self.base});p.goto(self.base+'/');p.wait_for_timeout(200);p.reload();p.wait_for_timeout(200);self.assertEqual(seen,[]);p.context.clear_cookies();p.reload();p.wait_for_function('()=>window.__calls?.length>0');count=len(seen);p.goto(self.base+'/?token=SYNTHETIC_SECRET#token=SYNTHETIC_SECRET');p.wait_for_timeout(250);self.assertEqual(len(seen),count)
   external='https://foreign.example.test/person/SYNTHETIC_PERSON?token=SYNTHETIC_SECRET';p.route(external,lambda route:route.fulfill(content_type='text/html',body='<a href="'+self.base+'/">Website</a>'));p.goto(external);p.get_by_role('link',name='Website',exact=True).click();p.wait_for_function('()=>window.__calls?.length>0');self.assertNotIn('SYNTHETIC_',json.dumps(p.evaluate('window.__calls')));self.assertIn(p.evaluate('window.__calls[0][2].referrer'),['https://foreign.example.test/',''])
  finally:b.close();pw.stop()
 def test_global_safety_switch_disables_collection(self):
  tool=self.f.path/'private/analytics-control.php'
  try:
   r=subprocess.run([self.f.php,str(tool),'disable'],capture_output=True,text=True);self.assertEqual(r.returncode,0);self.assertFalse(requests.get(self.base+'/analytics-status.php').json()['approved']);self.assertNotIn('mc.yandex',requests.get(self.base+'/').headers.get('Content-Security-Policy',''))
  finally:self.assertEqual(subprocess.run([self.f.php,str(tool),'enable'],capture_output=True).returncode,0)
 def test_known_public_policy_upgrade_preserves_custom_policy_and_emergency_stop(self):
  original=dict(self.f.config);path=self.f.path/'private/privacy-policy.txt';content=path.read_bytes();old=json.loads((self.f.path/'private/legal/privacy-2026-10-27-v2.json').read_text())
  try:
   self.f.config.update(privacy_policy_approved=True,privacy_policy_version='privacy-2026-10-27-v2');self.f.write_config();path.write_text(old['policy']);self.assertEqual(requests.get(self.base+'/api.php?r=privacy').json()['version'],'privacy-2026-11-02-v4');self.assertTrue(requests.get(self.base+'/analytics-status.php').json()['approved']);prior3=json.loads((self.f.path/'private/legal/privacy-2026-11-02-v3.json').read_text());self.f.config['privacy_policy_version']=prior3['version'];self.f.write_config();path.write_text(prior3['policy']);self.assertEqual(requests.get(self.base+'/api.php?r=privacy').json()['version'],'privacy-2026-11-02-v4');self.f.config['privacy_policy_version']='privacy-2026-10-27-v2';self.f.write_config();path.write_text('SYNTHETIC custom approved policy');self.assertEqual(requests.get(self.base+'/api.php?r=privacy').json()['version'],'privacy-2026-10-27-v2');self.assertFalse(requests.get(self.base+'/analytics-status.php').json()['approved']);path.write_text(old['policy']);self.f.config['privacy_policy_disabled']=True;self.f.write_config();self.assertFalse(requests.get(self.base+'/api.php?r=privacy').json()['enabled']);self.assertFalse(requests.get(self.base+'/analytics-status.php').json()['approved'])
  finally:path.write_bytes(content);self.f.config.clear();self.f.config.update(original);self.f.write_config()
 def test_unapproved_analytics_remains_disabled(self):
  path=self.f.path/'private/legal/privacy-2026-11-02-v4.json';original=path.read_bytes();d=json.loads(original);d['analytics_approved']=False;path.write_text(json.dumps(d))
  try:self.assertFalse(requests.get(self.base+'/analytics-status.php').json()['approved']);self.assertNotIn('mc.yandex',requests.get(self.base+'/').headers.get('Content-Security-Policy',''))
  finally:path.write_bytes(original)
