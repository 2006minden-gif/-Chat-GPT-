"""Public service guidance: browser-local brief, no API writes or personal-data storage."""
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import unittest
import requests
from playwright.sync_api import sync_playwright
ROOT=Path(__file__).resolve().parents[1]
class ServiceGuide(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);cls.root=Path(cls.tmp.name)
  shutil.copytree(ROOT/'public',cls.root/'public');shutil.copytree(ROOT/'private',cls.root/'private')
  # No config.php or database: public guide must remain independently usable.
  (cls.root/'private/config.php').unlink(missing_ok=True)
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1]
  cls.base='http://127.0.0.1:'+str(cls.port)
  cls.log=(cls.root/'server.log').open('w');cls.addClassCleanup(cls.log.close)
  cls.proc=subprocess.Popen([os.environ.get('PHP_BIN','php'),'-S','127.0.0.1:'+str(cls.port),'-t',str(cls.root/'public')],stdout=cls.log,stderr=cls.log);cls.addClassCleanup(cls.stop)
  for _ in range(80):
   try:
    if requests.get(cls.base+'/services.php',timeout=1).status_code==200:break
   except requests.ConnectionError:pass
   time.sleep(.05)
  else:raise RuntimeError('Guide fixture did not start')
 @classmethod
 def stop(cls):cls.proc.terminate();cls.proc.wait(timeout=5)
 def browser(self):
  p=sync_playwright().start();self.addCleanup(p.stop)
  b=p.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);self.addCleanup(b.close);return b
 def test_public_map_and_icons(self):
  import xml.etree.ElementTree as ET
  xml=requests.get(self.base+'/sitemap.xml');self.assertEqual(xml.status_code,200)
  locations={n.text for n in ET.fromstring(xml.content).findall('{*}url/{*}loc')}
  self.assertEqual(locations,{'https://neurodelo.pro'+p for p in ['/','/services.php','/privacy.php','/consent.php','/sitemap.php','/catalog.php','/portfolio.php','/reviews.php']})
  robots=requests.get(self.base+'/robots.txt');self.assertIn('Sitemap: https://neurodelo.pro/sitemap.xml',robots.text)
  page=requests.get(self.base+'/sitemap.php');self.assertEqual(page.status_code,200);self.assertIn('Карта сайта',page.text)
  icon=requests.get(self.base+'/favicon.ico');self.assertEqual(icon.content[:4],b'\x00\x00\x01\x00')
  svg=requests.get(self.base+'/favicon.svg');self.assertEqual(ET.fromstring(svg.content).tag,'{http://www.w3.org/2000/svg}svg')
 def test_page_works_without_configuration_or_database(self):
  r=requests.get(self.base+'/services.php');self.assertEqual(r.status_code,200);self.assertIn('ИИ-агент и автоматизация',r.text);self.assertIn('frame-ancestors',r.headers['Content-Security-Policy'])
  for p in ['/services/guide.js','/services/guide.css']:self.assertEqual(requests.get(self.base+p).status_code,200)
 def test_mobile_brief_is_local_and_updates_invalidate_result(self):
  page=self.browser().new_page(viewport={'width':375,'height':812});requests_seen=[];errors=[]
  page.on('request',lambda r:requests_seen.append((r.method,r.url,r.resource_type)));page.on('pageerror',lambda e:errors.append(str(e)))
  page.goto(self.base+'/services.php?service=ai');page.locator('#brief-tool').wait_for(state='visible')
  self.assertEqual(page.locator('#brief-service').input_value(),'ai');page.locator('#brief-goal').fill('Готовить черновики ответов клиентам')
  page.get_by_label('Подтверждение важных действий человеком',exact=True).check();page.locator('#service-brief button').click()
  summary=page.locator('#brief-summary').input_value();self.assertIn('ИИ-агент',summary);self.assertIn('Подтверждение важных действий человеком',summary)
  self.assertIn('Ничего не отправлено',page.locator('#brief-status').inner_text());self.assertTrue(page.locator('#telegram-brief').get_attribute('href').startswith('https://t.me/minden2006?text='))
  self.assertTrue(page.evaluate('document.documentElement.scrollWidth <= window.innerWidth'))
  page.locator('#brief-goal').fill('Изменённая задача');self.assertTrue(page.locator('#brief-result').is_hidden())
  self.assertEqual(page.locator('#brief-summary').input_value(),'');self.assertEqual(page.locator('#telegram-brief').get_attribute('href'),'https://t.me/minden2006')
  self.assertFalse(any(m!='GET' or t in ['fetch','xhr'] for m,u,t in requests_seen));self.assertEqual(errors,[])
 def test_service_changes_exclude_hidden_options_and_query_is_not_html(self):
  page=self.browser().new_page();page.goto(self.base+'/services.php?service=%3Cscript%3Ebad%3C%2Fscript%3E')
  self.assertEqual(page.locator('#brief-service').input_value(),'landing')
  page.get_by_label('Кнопка обращения в Telegram',exact=True).check();page.locator('#brief-service').select_option('app')
  page.locator('#brief-goal').fill('<script>window.bad=true</script>');page.locator('#service-brief button').click()
  self.assertNotIn('Кнопка обращения в Telegram',page.locator('#brief-summary').input_value());self.assertIsNone(page.evaluate('window.bad'))
  self.assertIn('<script>',page.locator('#brief-summary').input_value())
 def test_clipboard_failure_offers_manual_copy(self):
  page=self.browser().new_page();page.add_init_script("Object.defineProperty(navigator,'clipboard',{value:{writeText:()=>Promise.reject(new Error('blocked'))}})")
  page.goto(self.base+'/services.php');page.locator('#brief-goal').fill('Новый сайт');page.locator('#service-brief button').click();page.locator('#copy-brief').click()
  self.assertIn('скопируйте его вручную',page.locator('#brief-status').inner_text());self.assertIn('Новый сайт',page.locator('#brief-summary').input_value())
 def test_no_javascript_still_shows_services_and_real_contact(self):
  page=self.browser().new_page(java_script_enabled=False);page.goto(self.base+'/services.php')
  self.assertEqual(page.locator('.guide-card').count(),4);self.assertTrue(page.locator('noscript').is_visible());self.assertGreater(page.locator('a[href="https://t.me/minden2006"]').count(),0)
 def test_main_navigation_and_cards_have_real_destinations(self):
  page=self.browser().new_page();page.goto(self.base+'/index.html')
  self.assertEqual(page.get_by_role('link',name='Услуги и бриф',exact=True).get_attribute('href'),'/services.php')
  links=page.locator('.service-card > a');self.assertEqual(links.count(),4)
  for link in links.all():self.assertTrue(link.get_attribute('href').startswith('/services.php?service='))
