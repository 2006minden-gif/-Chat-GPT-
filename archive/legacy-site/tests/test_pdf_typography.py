"""Readable 11pt PDFs and authorized print copies without replacing issued bytes."""
import hashlib,json,os,re,subprocess,tempfile,zlib
from pathlib import Path
from playwright.sync_api import sync_playwright
import test_scoped_document_pdf as scoped
class PdfTypography(scoped.ScopedDocumentPdf):
 def render(self,title,paragraphs,compact):
  program='require '+json.dumps(str(self.f.path/'private/lifecycle/pdf.php'))+';$d=json_decode(stream_get_contents(STDIN),true);echo ct_pdf_bytes($d["title"],$d["paragraphs"],false,1793876400,$d["compact"]);'
  r=subprocess.run([self.f.php,'-r',program],input=json.dumps({'title':title,'paragraphs':paragraphs,'compact':compact},ensure_ascii=False).encode(),capture_output=True);self.assertEqual(r.returncode,0,r.stderr.decode());return r.stdout
 def extract(self,pdf):
  with tempfile.TemporaryDirectory() as tmp:
   path=Path(tmp)/'document.pdf';path.write_bytes(pdf);text=subprocess.check_output(['pdftotext',str(path),'-'],text=True);info=subprocess.check_output(['pdfinfo',str(path)],text=True);return text,int(re.search(r'Pages:\s+(\d+)',info).group(1))
 def normalized(self,text):
  text=re.sub(r'Страница \d+ / \d+','',text).replace('НейроДело\nneurodelo.pro','');return re.sub(r'\s+','',text)
 def test_readable_type_reduces_pages_and_preserves_all_terms_and_signature_space(self):
  paragraphs=[]
  for heading in ['Стороны и предмет','Результаты и исключения','Сроки и зависимости','Цена и порядок оплаты','Проверка и изменение объёма','Приёмка и недостатки','Исходники, права и лицензии','Конфиденциальность и данные','Прекращение и расчёты','Разногласия','Передача результата','Поддержка']:
   paragraphs.append(heading+'\n'+'ТЕСТОВЫЕ условия: исполнитель и заказчик согласовали проверяемый результат. Текст должен сохраняться полностью и оставаться читаемым при обычной печати. '*2)
  paragraphs.extend(['Исполнитель','ТЕСТОВЫЙ Исполнитель Иванович','Контакт: owner@example.invalid','Подпись: __________________','Заказчик','ТЕСТОВАЯ Заказчица Петровна','Контакт: client@example.invalid','Подпись: __________________'])
  old=self.render('ТЕСТ — коммерческое предложение',paragraphs,False);pdf=self.render('ТЕСТ — коммерческое предложение',paragraphs,True);oldtext,oldpages=self.extract(old);text,pages=self.extract(pdf);self.assertLess(pages,oldpages);self.assertEqual(self.normalized(text),self.normalized(oldtext));self.assertIn(b'/FontFile2',pdf);self.assertIn(b'/Subtype /Image',pdf)
  streams=[]
  for match in re.finditer(rb'stream\r?\n(.*?)\r?\nendstream',pdf,re.S):
   try:streams.append(zlib.decompress(match.group(1)))
   except zlib.error:pass
  self.assertRegex(b'\n'.join(streams),rb'/F\d+ 11\.00 Tf')
  for block in ['Исполнитель','Заказчик']:
   containing=[p for p in text.split('\f') if '\n'+block+'\n' in p];self.assertEqual(len(containing),1);self.assertIn('Подпись: __________________',containing[0])
  target=Path('/tmp/neuro-pdf-typography-synthetic.pdf');target.write_bytes(pdf);subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1200','-png',str(target),'/tmp/neuro-pdf-typography-synthetic'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE);print('SYNTHETIC pages:',oldpages,'->',pages,flush=True)
 def test_print_download_keeps_original_asset_and_scoped_access(self):
  oid,docs=self.prepare_documents();b=docs[0];link=self.create_link(oid,[b],False).json();g,x=self.exchange(link['url'].split('#token=')[1]);normal=self.base+'/prospect-api.php?r=pdf&id='+str(b['id']);url=normal+'&print=compact-v1';self.assertEqual(g.get(url).status_code,403);self.consent(g,x);self.assertEqual(g.get(url).status_code,200)
  asset=self.f.sql('SELECT * FROM nd_lc_pdf_assets WHERE binding_id=?',params=[b['id']])[0];snapshot=json.loads(b['input_snapshot']);original=self.render(snapshot['rendered']['title'],re.split(r'\r?\n\r?\n',snapshot['rendered']['description']),False);stored=self.f.path/'private/collaboration-files'/asset['storage_key'];stored.write_bytes(original);self.f.sql('UPDATE nd_lc_pdf_assets SET checksum=?,size_bytes=? WHERE binding_id=?',params=[hashlib.sha256(original).hexdigest(),len(original),b['id']]);before=self.f.sql('SELECT * FROM nd_lc_pdf_assets WHERE binding_id=?',params=[b['id']])[0];self.assertEqual(g.get(normal).content,original)
  pdf=g.get(url);self.assertEqual(pdf.status_code,200);self.assertTrue(pdf.content.startswith(b'%PDF-'));self.assertEqual(pdf.headers['X-Neuro-PDF-Purpose'],'compact-print-copy');self.assertEqual(pdf.headers['X-Neuro-Source-Hash'],b['generated_hash']);self.assertEqual(pdf.headers['X-Neuro-PDF-SHA256'],hashlib.sha256(pdf.content).hexdigest());self.assertEqual(self.normalized(self.extract(pdf.content)[0]),self.normalized(self.extract(original)[0]));self.assertEqual(g.get(url).content,pdf.content);self.assertEqual(self.f.sql('SELECT * FROM nd_lc_pdf_assets WHERE binding_id=?',params=[b['id']])[0],before);self.assertEqual(stored.read_bytes(),original)
  owner=self.owner.get(self.base+'/lifecycle-api.php?mode=owner&r=documents/'+str(b['id'])+'/pdf&print=compact-v1');self.assertEqual(owner.content,pdf.content)
  with sync_playwright() as pw:
   browser=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);page=browser.new_page();page.goto(link['url']);page.get_by_role('checkbox').check();page.get_by_role('button',name='Продолжить к документам',exact=True).click();download=page.get_by_role('link',name='Скачать PDF',exact=True);download.wait_for();self.assertEqual(download.count(),1);self.assertNotIn('Компактный',page.locator('body').inner_text())
   with page.expect_download() as got:download.click()
   with tempfile.TemporaryDirectory() as tmp:
    path=Path(tmp)/'download.pdf';got.value.save_as(str(path));self.assertEqual(path.read_bytes(),pdf.content)
   browser.close()
  self.assertEqual(g.get(url.replace('id='+str(b['id']),'id='+str(docs[1]['id']))).status_code,404);self.assertEqual(g.get(normal+'&print=unknown').status_code,422)
  import requests
  self.assertEqual(requests.get(url).status_code,401);tampered=dict(snapshot);tampered['rendered']=dict(snapshot['rendered'],description='SYNTHETIC tampered text');self.f.sql('UPDATE nd_lc_document_bindings SET input_snapshot=? WHERE id=?',params=[json.dumps(tampered,ensure_ascii=False),b['id']]);self.assertEqual(g.get(url).status_code,409);self.f.sql('UPDATE nd_lc_document_bindings SET input_snapshot=? WHERE id=?',params=[b['input_snapshot'],b['id']]);self.f.sql('UPDATE nd_lc_prospect_links SET expires_at=0 WHERE id=?',params=[link['id']]);self.assertEqual(g.get(url).status_code,401);self.f.sql('UPDATE nd_lc_prospect_links SET expires_at=1800000000,revoked_at=1 WHERE id=?',params=[link['id']]);self.assertEqual(g.get(url).status_code,401)
for name in dir(scoped.ScopedDocumentPdf):
 if name.startswith('test_'):setattr(PdfTypography,name,None)
