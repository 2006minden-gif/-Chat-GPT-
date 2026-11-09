"""Focused public brief handoff, existing catalog mapping and published-only XML."""
import os,subprocess,requests
from playwright.sync_api import sync_playwright,expect
import test_publications as publication
class DeliveryEntrypoints(publication.Publications):
 def test_explicit_brief_handoff_keeps_consent_separate_and_saves_one_inquiry(self):
  before=self.f.sql('SELECT COUNT(*) n FROM nd_leads')[0]['n']
  with sync_playwright() as pw:
   b=pw.chromium.launch(executable_path=os.environ.get('CHROMIUM_BIN','/usr/bin/chromium'),args=['--no-sandbox']);p=b.new_page(viewport={'width':375,'height':812});p.goto(self.base+'/services.php?service=ai');p.locator('#brief-goal').fill('SYNTHETIC delivery handoff, no external customers');p.locator('#service-brief button[type=submit]').click();p.locator('#send-site-brief').click();expect(p.locator('#consent')).to_be_enabled();self.assertFalse(p.locator('#consent').is_checked());self.assertIn('SYNTHETIC delivery handoff',p.locator('#idea').input_value());self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_leads')[0]['n'],before);p.locator('#name').fill('SYNTHETIC handoff');p.locator('#contact-value').fill('synthetic-handoff@example.invalid');p.locator('#consent').check();p.locator('#brief-form button[type=submit]').click();p.locator('#form-status').get_by_text('Заявка сохранена! Свяжемся с вами по указанному контакту.',exact=True).wait_for();self.assertEqual(self.f.sql('SELECT COUNT(*) n FROM nd_leads')[0]['n'],before+1);self.assertFalse(p.evaluate('document.documentElement.scrollWidth>innerWidth'));b.close()
 def test_existing_drafts_are_recognized_and_xml_never_lists_unpublished_cases(self):
  p=subprocess.run([self.f.php,str(self.f.path/'private/workflow/prepare.php')],capture_output=True,text=True);self.assertEqual(p.returncode,0,p.stderr);mapping=self.wget('catalog-map').json()['draft_mapping'];self.assertTrue(all(x['existing'] is not None for x in mapping));self.assertTrue(all(x['existing']['state']=='DRAFT' for x in mapping));case=self.save();xml=lambda:requests.get(self.base+'/sitemap-publications.php');self.assertNotIn(case['record']['slug'],xml().text);published=self.publish(case);self.assertEqual(published.status_code,200,published.text);self.assertIn(case['record']['slug'],xml().text);record=published.json()['record'];self.assertEqual(self.api('archive',{'id':int(record['id']),'version':int(record['version']),'confirm':True}).status_code,200);self.assertNotIn(case['record']['slug'],xml().text)
for name in dir(publication.Publications):
 if name.startswith('test_'):setattr(DeliveryEntrypoints,name,None)
