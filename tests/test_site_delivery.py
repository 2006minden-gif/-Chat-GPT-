"""Release integrity and real Apache rules, including old files left on hosting."""
import ast
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts/deploy'))
import release,client,health

class Delivery(unittest.TestCase):
 def test_release_is_complete_credentials_and_retired_application_excluded(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=Path(tmp)/'bundle';manifest=release.build(bundle,'a'*40);client.validate_bundle(bundle,'a'*40)
   self.assertTrue(manifest['database_recovery_required']);self.assertEqual(manifest['migrations'],[])
   self.assertNotIn('private/config.php',manifest['files']);self.assertNotIn('public_html/customer-api.php',manifest['files'])
   expected=['public_html/'+n for n in release.policy_check()['public_files']]+['private/'+n for n in release.policy_check()['private_files']]
   source=(ROOT/'scripts/deploy/remote.php').read_text();literal=re.search(r'function paths\(\):array \{\s*return (\[[^;]+\]);',source).group(1)
   self.assertEqual(ast.literal_eval(literal),expected)
   self.assertTrue(all(not n.startswith('archive/') for n in manifest['files']))
   (bundle/'private/config.php').write_text('PRIVATE')
   with self.assertRaises(ValueError):client.validate_bundle(bundle,'a'*40)
 def test_remote_bundle_revalidation_accepts_managed_health_evidence(self):
  with tempfile.TemporaryDirectory() as tmp:
   bundle=Path(tmp)/'bundle';release.build(bundle,'a'*40)
   (bundle/'baseline.json').write_text('{"ok":true}');(bundle/'after-health.json').write_text('{"ok":true}')
   code='define("NEURO_DEPLOY_LIBRARY",true);require '+json.dumps(str(ROOT/'scripts/deploy/remote.php'))+';echo json_encode(verify_bundle('+json.dumps(str(bundle))+',"test")["revision"]);'
   result=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',code],capture_output=True,text=True,check=True)
   self.assertEqual(json.loads(result.stdout),'a'*40)
   (bundle/'unexpected.txt').write_text('unexpected')
   result=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',code],capture_output=True,text=True)
   self.assertNotEqual(result.returncode,0);self.assertIn('unexpected_release_file',result.stderr)
 def test_retired_code_is_absent_from_repository(self):
  for name in ['archive/legacy-site','private/app.php','private/notifications','scripts/notifications','.github/workflows/notifications.yml']:
   self.assertFalse((ROOT/name).exists(),name)
 def test_downloadable_templates_are_manual_and_valid_packages(self):
  import zipfile,xml.etree.ElementTree as ET
  files=list((ROOT/'manual-templates').glob('*.docx'));self.assertEqual(len(files),6)
  for file in files:
   with zipfile.ZipFile(file) as z:
    text=''.join(ET.fromstring(z.read('word/document.xml')).itertext())
    self.assertNotIn('{{',text);self.assertIn('[____________________]',text);self.assertNotIn('кабинет',text.lower())

class ApacheRetirement(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup);cls.path=Path(cls.tmp.name);cls.path.chmod(0o755);public=cls.path/'public';shutil.copytree(ROOT/'public',public)
  (public/'site-router.php').write_text('PORTFOLIO_ROUTER_ONLY')
  cls.retired=json.loads((ROOT/'tests/fixtures/retired-public-paths.json').read_text())
  for name in cls.retired:(public/name).write_text('RETIRED_SECRET_SHOULD_NOT_EXECUTE')
  (public/'.well-known/acme-challenge').mkdir(parents=True);(public/'.well-known/acme-challenge/token-test').write_text('ACME_OK')
  s=socket.socket();s.bind(('127.0.0.1',0));cls.port=s.getsockname()[1];s.close();modules=Path(os.environ['APACHE_MODULE_DIR']);apache=os.environ['APACHE_BIN'];conf=cls.path/'httpd.conf'
  conf.write_text(f'''ServerRoot "{cls.path}"
ServerName localhost
Listen 127.0.0.1:{cls.port}
PidFile "{cls.path}/httpd.pid"
ErrorLog "{cls.path}/error.log"
LoadModule mpm_event_module "{modules}/mod_mpm_event.so"
LoadModule authz_core_module "{modules}/mod_authz_core.so"
LoadModule dir_module "{modules}/mod_dir.so"
LoadModule rewrite_module "{modules}/mod_rewrite.so"
DocumentRoot "{public}"
<Directory "{public}">
 Options FollowSymLinks
 AllowOverride All
 Require all granted
</Directory>
''')
  subprocess.run([apache,'-t','-f',str(conf)],capture_output=True,check=True);cls.proc=subprocess.Popen([apache,'-f',str(conf),'-DFOREGROUND'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);cls.addClassCleanup(cls.stop)
  for _ in range(100):
   try:cls.request('/styles.css');break
   except OSError:time.sleep(.05)
  else:raise RuntimeError((cls.path/'error.log').read_text())
 @classmethod
 def stop(cls):cls.proc.terminate();cls.proc.wait(timeout=5)
 @classmethod
 def request(cls,path):
  c=http.client.HTTPConnection('127.0.0.1',cls.port,timeout=3);c.request('GET',path);r=c.getresponse();result=(r.status,r.read());c.close();return result
 def test_old_physical_files_are_routed_to_closed_handler(self):
  for name in self.retired:
   status,body=self.request('/'+name)
   self.assertNotIn(b'RETIRED_SECRET_SHOULD_NOT_EXECUTE',body,name)
   self.assertTrue(status in [403,410] or body==b'PORTFOLIO_ROUTER_ONLY',(name,status,body[:100]))
 def test_assets_acme_and_private_files(self):
  self.assertEqual(self.request('/.well-known/acme-challenge/token-test'),(200,b'ACME_OK'))
  self.assertEqual(self.request('/styles.css')[0],200)
  for path in ['/index.html','/.htaccess','/private/config.php','/customer-api.php/anything']:
   status,body=self.request(path);self.assertTrue(status in [403,410] or body==b'PORTFOLIO_ROUTER_ONLY')
