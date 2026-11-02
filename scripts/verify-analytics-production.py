"""Public synthetic visit, real SDK/network. No owner login, inquiry, order or secrets."""
import argparse,json,re,time
from urllib.parse import urlsplit
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
COUNTER=114024456

def verify(base='https://neurodelo.pro'):
 if base!='https://neurodelo.pro':raise ValueError('production_origin_required')
 result={'ok':False,'counter':COUNTER,'checks':[]}
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
   page.goto(base+'/',wait_until='domcontentloaded',timeout=45000);page.get_by_role('button',name='Отклонить',exact=True).wait_for(timeout=15000);page.wait_for_timeout(700);check('no_sdk_pixel_or_tracking_before_consent',not outbound)
   page.get_by_role('button',name='Отклонить',exact=True).click();page.wait_for_function("()=>window.neuroAnalytics?.getChoice()==='deny'");page.reload(wait_until='domcontentloaded');page.wait_for_timeout(700);check('no_tracking_after_refusal_and_reload',not outbound)
   page.get_by_role('button',name='Настройки аналитики',exact=True).click();page.get_by_role('button',name='Разрешить аналитику',exact=True).click()
   deadline=time.monotonic()+45
   while time.monotonic()<deadline:
    page.wait_for_timeout(500)
    if any('/watch/'+str(COUNTER) in u and 200<=status<300 for u,status in responses):break
   check('real_yandex_sdk_received',any('/metrika/tag.js' in u and status==200 for u,status in responses))
   check('real_counter_watch_http_2xx',any('/watch/'+str(COUNTER) in u and 200<=status<300 for u,status in responses))
   receipt=context.request.get(base+'/analytics-status.php').json()['receipt'];check('minimal_version_time_choice_receipt',set(receipt)=={'version','time','choice'} and receipt['version']=='analytics-2026-11-02-v1' and receipt['choice']=='allow')
   page.get_by_role('button',name='Настройки аналитики',exact=True).click();page.get_by_role('button',name='Отклонить',exact=True).click();page.wait_for_function("()=>window.neuroAnalytics?.getChoice()==='deny'");page.wait_for_timeout(300);after=len(outbound);page.wait_for_timeout(1500);check('no_new_tracking_current_page_after_withdrawal',len(outbound)==after)
   check('accessible_metrica_cookies_removed',not any(c['name'].startswith('_ym_') for c in context.cookies([base])))
   page.reload(wait_until='domcontentloaded');page.wait_for_timeout(500);check('withdrawal_persists',len(outbound)==after)
   restored=context.request.post(base+'/analytics-status.php',data={'choice':'allow'},headers={'Origin':base});check('consent_for_private_page_exclusion_test',restored.ok);context.clear_cookies(name='neuro_analytics_block')
   for path in ['/studio.php','/customer.php','/portal.php','/prospect.php','/payment.php','/documents.php?mode=owner','/max-link.php']:
    page.goto(base+path,wait_until='domcontentloaded');page.wait_for_timeout(100)
   check('private_pages_do_not_load_tracker',len(outbound)==after)
   result['ok']=True
  except Exception as error:result['network_failures']=failed;result['error']=str(error) if isinstance(error,RuntimeError) else type(error).__name__
  finally:context.close();browser.close()
 return result

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--evidence',type=Path,required=True);args=parser.parse_args();result=verify();args.evidence.write_text(json.dumps(result,ensure_ascii=False,indent=2));print(json.dumps(result,ensure_ascii=False));raise SystemExit(0 if result['ok'] else 1)
