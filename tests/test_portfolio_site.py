"""Real portfolio-only browser/API flow against a disposable loopback database."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import unittest
import requests
import fixture_site as fixture

class PortfolioSite(fixture.Prelaunch):
 def test_public_health_contract_and_retired_private_paths(self):
  import sys
  sys.path.insert(0,str(fixture.ROOT/'scripts/deploy'))
  import health
  report=health.snapshot(base=self.base,extra_assets=['/site.css','/site.js','/portfolio-editor.js'])
  self.assertTrue(report['ok'],{p:r for p,r in report['checks'].items() if not r['ok']})
  self.assertEqual(requests.get(self.base+'/private/config.php').status_code,403)
 def payload(self,**changes):
  return dict(title='Тестовая работа',text='Реальный сценарий теста на одноразовых данных.',category='website',media=[],published=False,**changes)
 def test_old_routes_cannot_read_or_write_even_with_owner_session(self):
  self.sql("INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES ('KEEP','keep@example.com','Сайт','KEEP','KEEP',1)")
  before=self.sql('SELECT * FROM nd_leads');session,headers=self.owner()
  for old in (fixture.ROOT/'archive/legacy-site/public').glob('*.php'):
   if old.name in ['index.php','studio.php','portfolio.php','portfolio-case.php']:continue
   for method in ['get','post']:
    response=getattr(session,method)(self.base+'/'+old.name,headers=headers,**({'json':{'action':'delete'}} if method=='post' else {}))
    self.assertEqual(response.status_code,410,(old.name,method,response.text[:100]))
  self.assertEqual(self.sql('SELECT * FROM nd_leads'),before)
 def test_owner_auth_csrf_upload_and_existing_password(self):
  self.assertEqual(requests.get(self.api('items')).status_code,401)
  self.assertEqual(requests.post(self.api('save'),json=self.payload()).status_code,401)
  s,h=self.owner()
  self.assertEqual(s.post(self.api('save'),json=self.payload()).status_code,403)
  self.assertEqual(s.post(self.api('save'),headers={**h,'Origin':'https://evil.invalid'},json=self.payload()).status_code,403)
  bad=s.post(self.api('upload'),headers=h,files={'file':('attack.php',b'<?php echo 1;','image/png')})
  self.assertEqual(bad.status_code,422)
  self.assertEqual(s.post(self.api('logout'),headers=h,json={}).status_code,200)
  self.assertEqual(s.get(self.api('items')).status_code,401)
 def test_publish_edit_conflict_unpublish_preserves_versions(self):
  s,h=self.owner();d=self.payload()
  first=s.post(self.api('save'),headers=h,json=d);self.assertEqual(first.status_code,200,first.text);item=first.json()['item']
  url=self.base+'/portfolio-case.php?case='+item['slug'];self.assertEqual(requests.get(url).status_code,404)
  d.update(id=item['id'],version=item['version'],published=True,rights_confirmed=True,featured=True)
  published=s.post(self.api('save'),headers=h,json=d);self.assertEqual(published.status_code,200,published.text);item=published.json()['item']
  self.assertIn(d['title'],requests.get(url).text);self.assertIn(d['title'],requests.get(self.base+'/').text)
  self.assertEqual(s.post(self.api('save'),headers=h,json=d).status_code,409)
  d.update(version=item['version'],published=False)
  result=s.post(self.api('save'),headers=h,json=d);self.assertEqual(result.status_code,200,result.text)
  self.assertEqual(requests.get(url).status_code,404)
  self.assertEqual(len(self.sql('SELECT * FROM nd_publication_versions WHERE publication_id=?',params=[item['id']])),3)
 def test_legacy_portfolio_and_files_are_read_without_migration(self):
  slug='legacy-'+secrets.token_hex(4);raw=json.dumps({'title':'Существующая работа','text':'Сохранить','media':[]},ensure_ascii=False)
  self.sql("INSERT INTO nd_publications(kind,slug,state,head_revision) VALUES ('portfolio',?,'PUBLISHED',1)",params=[slug]);pid=self.sql('SELECT id FROM nd_publications WHERE slug=?',params=[slug])[0]['id']
  self.sql('INSERT INTO nd_publication_versions(publication_id,revision_number,body_json,checksum) VALUES (?,1,?,?)',params=[pid,raw,hashlib.sha256(raw.encode()).hexdigest()]);vid=self.sql('SELECT id FROM nd_publication_versions WHERE publication_id=?',params=[pid])[0]['id'];self.sql('UPDATE nd_publications SET published_version_id=? WHERE id=?',params=[vid,pid])
  self.assertIn('Существующая работа',requests.get(self.base+'/portfolio.php').text)
  s,h=self.owner();self.assertTrue(any(i['slug']==slug for i in s.get(self.api('items')).json()['items']))
 def test_mobile_owner_upload_publish_edit_archive_end_to_end(self):
  from playwright.sync_api import sync_playwright
  image=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aWQAAAABJRU5ErkJggg==')
  with sync_playwright() as p:
   browser=p.chromium.launch(executable_path=os.environ['CHROMIUM_BIN'],args=['--no-sandbox'])
   try:
    page=browser.new_page(viewport={'width':390,'height':844});page.goto(self.base+'/studio.php');page.locator('#password').fill(self.password);page.locator('#login-form button').click();page.locator('#editor-panel').wait_for(state='visible')
    page.locator('#new-work').click();title='Мобильный кейс '+secrets.token_hex(4);page.locator('#title').fill(title);page.locator('#text').fill('Проверено с нуля без CRM, заказа и клиента.');page.locator('#files').set_input_files({'name':'project.png','mimeType':'image/png','buffer':image});page.locator('#upload-status').filter(has_text='Загружено файлов: 1').wait_for();page.locator('[name=rights_confirmed]').check();page.locator('[name=featured]').check();page.locator('button[name=publish]').click();page.locator('#save-status').filter(has_text='сохранена и опубликована').wait_for()
    self.assertTrue(page.evaluate('document.documentElement.scrollWidth<=innerWidth'))
    session,headers=self.owner();item=next(i for i in session.get(self.api('items')).json()['items'] if i['body']['title']==title);mid=item['body']['media'][0]['id'];media=requests.get(self.api('media')+'&id='+str(mid));self.assertEqual(media.status_code,200);self.assertEqual(media.content,image)
    public=browser.new_page();public.goto(self.base+'/portfolio.php');public.get_by_role('link',name=title).click();public.get_by_role('heading',name=title,exact=True).wait_for();self.assertEqual(public.locator('figure img').count(),1)
    page.locator('#text').fill('Изменённое описание');page.locator('button[name=publish]').click();page.locator('#save-status').filter(has_text='сохранена и опубликована').wait_for();public.reload();public.get_by_text('Изменённое описание',exact=True).wait_for()
    page.once('dialog',lambda dialog:dialog.accept());page.locator('.work-card').filter(has_text=title).get_by_role('button',name='Убрать работу').click();page.locator('.work-card').filter(has_text=title).wait_for(state='detached');self.assertEqual(requests.get(self.api('media')+'&id='+str(mid)).status_code,404)
    self.assertTrue(any((self.path/'private/publication-files').iterdir()))
   finally:browser.close()

if __name__=='__main__':unittest.main()
