"""One owner readiness, no repeat mail/catalog setup, private Cyrillic illustrated guide."""
import json,subprocess,requests,tempfile,os
from pathlib import Path
import test_owner_planning as planning
class OwnerHelp(planning.OwnerPlanning):
 def test_private_readiness_complete_illustrated_pdf_and_no_secret_exports(self):
  self.prepare_synthetic_owner()
  self.assertEqual(requests.get(self.base+'/owner-help-api.php?r=guide').status_code,401);self.assertEqual(self.stranger.get(self.base+'/owner-help-api.php?r=readiness').status_code,401);r=self.owner.get(self.base+'/owner-help-api.php?r=readiness');self.assertEqual(r.status_code,200,r.text);d=r.json()['readiness'];mail=next(x for x in d['rows'] if x['id']=='mail');self.assertTrue(mail['completed']);self.assertIn('Повторная',mail['remaining']);catalog=next(x for x in d['rows'] if x['id']=='catalog');self.assertIn('повторно не создавать',catalog['remaining']);self.assertFalse(d['public_registration_enabled']);self.assertTrue(all(x['responsible'] for x in d['provider']['questions']));self.assertNotIn('password',json.dumps(d));self.assertNotIn('SYNTHETIC_ONLY_MAX_TOKEN',json.dumps(d));pdf=self.owner.get(self.base+'/owner-help-api.php?r=guide');self.assertEqual(pdf.status_code,200,pdf.text[:200] if pdf.status_code!=200 else '');self.assertEqual(pdf.headers['Content-Type'],'application/pdf');self.assertIn(b'/FontFile2',pdf.content);self.assertGreaterEqual(pdf.content.count(b'/Subtype /Image'),3)
  with tempfile.TemporaryDirectory() as folder:
   p=Path(folder)/'guide.pdf';p.write_bytes(pdf.content);text=subprocess.check_output(['pdftotext',str(p),'-'],text=True);self.assertIn('Что мне сделать сейчас',text);self.assertIn('Как добавить работу в портфолио',text);self.assertIn('синтетических данных',text);self.assertNotIn(self.f.password,text);self.assertNotIn('smtp-password',text)
  if os.environ.get('NEURO_GUIDE_PDF'):Path(os.environ['NEURO_GUIDE_PDF']).write_bytes(pdf.content)
  page=requests.get(self.base+'/help.php');self.assertEqual(page.status_code,200);self.assertIn('Один заказ от начала до завершения',page.text);self.assertIn('/owner-help-api.php?r=guide',page.text);questions=self.owner.get(self.base+'/owner-help-api.php?r=provider-questions');self.assertEqual(questions.status_code,200);self.assertIn('Поддержка',questions.text)
for name in dir(planning.OwnerPlanning):
 if name.startswith('test_'):setattr(OwnerHelp,name,None)
