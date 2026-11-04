"""Owner draft save must work before media, with honest retry and private uploads."""
import os,json,secrets,requests
from pathlib import Path
from playwright.sync_api import sync_playwright,expect
import test_publications as publications
class PortfolioSaveRecovery(publications.Publications):
 def page(self,browser):
  c=browser.new_context(viewport={'width':375,'height':812});c.add_cookies([{'name':x.name,'value':x.value,'url':self.base} for x in self.owner.cookies]);return c.new_page()
 def test_title_only_draft_generated_address_and_image_video_reload(self):
  self.prepare_synthetic_owner()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=self.page(browser);errors=[];page.on('pageerror',lambda e:errors.append(str(e)));page.goto(self.base+'/publication-owner.php');page.get_by_label('Название',exact=True).fill('SYNTHETIC title-only case');page.get_by_role('button',name='Сохранить приватную редакцию',exact=True).click();page.get_by_role('heading',name='Добавить изображения и видео',exact=True).wait_for();self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_publications')[0]['n'],1);record=self.api('items').json()['items'][0];self.assertTrue(record['slug'].startswith('case-'));self.assertEqual(record['state'],'DRAFT');self.assertEqual(requests.get(self.base+'/publication-api.php?r=items').json()['items'],[])
   publish=self.api('publish',{'id':int(record['id']),'version':int(record['version']),'checksum':record['head']['checksum'],'sort_order':0,'confirm':True,'own_materials_confirmed':True,'reason':'SYNTHETIC no complete text'});self.assertEqual(publish.status_code,422)
   png=publications.base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=');video=(Path(__file__).parent/'fixtures/publication-synthetic.webm').read_bytes();page.get_by_label('Выбрать несколько изображений и видео',exact=True).set_input_files([{'name':'SYNTHETIC.png','mimeType':'image/png','buffer':png},{'name':'SYNTHETIC.webm','mimeType':'video/webm','buffer':video}]);page.get_by_role('button',name='Загрузить выбранные файлы',exact=True).click();page.get_by_role('heading',name='Элементов в смешанной галерее: 2',exact=True).wait_for();page.reload();page.get_by_role('button',name='Редактировать кейс и галерею',exact=True).click();page.get_by_role('heading',name='Элементов в смешанной галерее: 2',exact=True).wait_for();self.assertEqual(errors,[]);self.assertFalse(page.evaluate('document.documentElement.scrollWidth>innerWidth'));self.assertEqual(requests.get(self.base+'/publication-api.php?r=items').json()['items'],[]);browser.close()
 def test_lost_save_response_reuses_request_key_and_does_not_duplicate_case(self):
  self.prepare_synthetic_owner()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=self.page(browser);keys=[]
   def handler(route):
    if route.request.method=='POST' and 'r=save' in route.request.url:
     keys.append(route.request.post_data_json['request_key'])
     if len(keys)==1:route.fetch();route.abort('failed');return
    route.continue_()
   page.route('**/publication-api.php?*',handler);page.goto(self.base+'/publication-owner.php');page.get_by_label('Название',exact=True).fill('SYNTHETIC retry after lost response');page.get_by_role('button',name='Сохранить приватную редакцию',exact=True).click();expect(page.locator('#pub-message')).to_contain_text('Связь прервалась');expect(page.locator('#pub-message')).to_be_in_viewport();page.get_by_role('button',name='Сохранить приватную редакцию',exact=True).click();page.get_by_role('heading',name='Добавить изображения и видео',exact=True).wait_for();self.assertEqual(len(keys),2);self.assertEqual(keys[0],keys[1]);self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_publications')[0]['n'],1);browser.close()
 def test_upload_failure_preserves_selection_and_shows_plain_russian_error(self):
  self.prepare_synthetic_owner()
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=self.page(browser);page.goto(self.base+'/publication-owner.php');page.get_by_label('Название',exact=True).fill('SYNTHETIC upload failure');page.get_by_role('button',name='Сохранить приватную редакцию',exact=True).click();page.get_by_role('heading',name='Добавить изображения и видео',exact=True).wait_for();page.route('**/publication-api.php?mode=owner&r=upload',lambda route:route.fulfill(status=413,content_type='text/html',body='<html>hosting body limit</html>'));field=page.get_by_label('Выбрать несколько изображений и видео',exact=True);field.set_input_files({'name':'SYNTHETIC.png','mimeType':'image/png','buffer':b'SYNTHETIC payload not uploaded'});page.get_by_role('button',name='Загрузить выбранные файлы',exact=True).click();expect(page.locator('#pub-message')).to_contain_text('Не все файлы добавлены');self.assertEqual(field.evaluate('x=>x.files.length'),1);expect(page.locator('.upload-status')).to_contain_text('Хостинг вернул неожиданный ответ');self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_publication_media')[0]['n'],0);browser.close()
for name in dir(publications.Publications):
 if name.startswith('test_'):setattr(PortfolioSaveRecovery,name,None)
