"""Public synthetic visit, real SDK/network. No owner login, inquiry, order or secrets."""
import argparse,json,re,time
from urllib.parse import urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright
COUNTER=114024456

def verify(base='https://neurodelo.pro'):
 if base!='https://neurodelo.pro':raise ValueError('production_origin_required')
 result={'ok':False,'counter':COUNTER,'mode':'public_notice','checks':[]}
 def check(name,ok):
  result['checks'].append({'name':name,'ok':bool(ok)})
  if not ok:raise RuntimeError(name)
 with sync_playwright() as pw:
  browser=pw.chromium.launch(headless=True);context=browser.new_context(viewport={'width':375,'height':812});page=context.new_page();outbound=[];responses=[];failed=[]
  def tracking(url):return bool(re.search(r'^https://(?:mc\.yandex\.(?:ru|com)|yastatic\.net)/',url))
  def observe(route):outbound.append(route.request.url);route.continue_()
  page.route(re.compile(r'^https://(?:mc\.yandex\.(?:ru|com)|yastatic\.net)/'),observe)
  page.on('requestfailed',lambda r:failed.append({'host':urlsplit(r.url).hostname,'path':urlsplit(r.url).path,'error':r.failure}) if tracking(r.url) else None)
  page.on('response',lambda r:responses.append((r.url,r.status)) if tracking(r.url) else None)
  try:
   page.goto(base+'/',wait_until='domcontentloaded',timeout=45000)
   deadline=time.monotonic()+45
   while time.monotonic()<deadline:
    page.wait_for_timeout(500)
    if any('/watch/'+str(COUNTER) in u and 200<=status<300 for u,status in responses):break
   check('no_analytics_popup_or_settings_button',page.locator('.nd-analytics,.nd-analytics-settings').count()==0)
   check('published_policy_version',context.request.get(base+'/api.php?r=privacy').json().get('version')=='privacy-2026-11-02-v4')
   check('real_yandex_sdk_received_without_click',any('/metrika/tag.js' in u and status==200 for u,status in responses))
   check('real_counter_watch_http_2xx',any('/watch/'+str(COUNTER) in u and 200<=status<300 for u,status in responses))
   check('public_inputs_masked',page.locator('input:not(.ym-disable-keys),textarea:not(.ym-disable-keys),select:not(.ym-disable-keys),[contenteditable]:not(.ym-disable-keys)').count()==0)
   state=context.request.get(base+'/analytics-status.php').json();check('no_fabricated_consent_or_preference_cookie',state['receipt'] is None and not any(c['name']=='neuro_analytics' for c in context.cookies([base])))
   page.goto(base+'/services.php?service=ai',wait_until='domcontentloaded');page.wait_for_function('()=>window.neuroAnalytics?.isRunning()');page.wait_for_timeout(700);check('whole_brief_and_preview_masked',page.locator('#brief.ym-hide-content,#brief-result.ym-hide-content').count()==2)
   after=len(outbound)
   for path in ['/studio.php','/customer.php','/portal.php','/prospect.php','/payment.php','/documents.php?mode=owner','/max-link.php','/portfolio-case.php?preview=1','/customer.php?invite=SYNTHETIC','/?token=SYNTHETIC']:
    page.goto(base+path,wait_until='domcontentloaded');page.wait_for_timeout(100)
   check('private_and_token_pages_do_not_load_tracker',len(outbound)==after)
   context.add_cookies([{'name':'neuro_analytics_block','value':'1','url':base,'secure':True,'sameSite':'Lax'}]);page.goto(base+'/',wait_until='domcontentloaded');page.wait_for_timeout(500);check('earlier_refusal_remains_effective',len(outbound)==after)
   check('earlier_refusal_blocks_noscript_pixel','mc.yandex.ru/watch/' not in context.request.get(base+'/').text())
   page.goto(base+'/privacy.php',wait_until='domcontentloaded');check('published_notice_matches_automatic_mode','без отдельного окна' in page.locator('.policy-text').inner_text() and 'Вебвизор' in page.locator('.policy-text').inner_text())
   result['ok']=True
  except Exception as error:result['network_failures']=failed;result['error']=str(error) if isinstance(error,RuntimeError) else type(error).__name__
  finally:context.close();browser.close()
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();result=verify();args.evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['ok'] else 1)
