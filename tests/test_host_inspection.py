"""Host outage inspection stays read-only and never exports configuration values."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
class HostInspection(unittest.TestCase):
 def test_readonly_inspection_redacts_credentials_and_accepts_a_stubbed_origin_probe(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);(root/'private').mkdir();(root/'public_html').mkdir()
   (root/'private/config.php').write_text("<?php return ['app_url'=>'https://neurodelo.pro','db_host'=>'localhost','db_name'=>'example','db_user'=>'test','db_password'=>'SYNTHETIC_PRIVATE_VALUE'];")
   (root/'public_html/.htaccess').write_text('Options -Indexes\n')
   before={p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()}
   code="define('NEURO_REPAIR_LIBRARY',true);require "+json.dumps(str(ROOT/'scripts/repair/production.php'))+";echo json_encode(rp_inspect("+json.dumps(tmp)+",fn()=>['https'=>['connected'=>false,'failure'=>'timeout']]));"
   r=subprocess.run([os.environ.get('PHP_BIN','php'),'-r',code],text=True,capture_output=True,check=True);result=json.loads(r.stdout)
   self.assertTrue(result['read_only']);self.assertTrue(result['configuration']['syntax_valid'])
   self.assertEqual(result['origin_http']['https']['failure'],'timeout')
   self.assertNotIn('SYNTHETIC_PRIVATE_VALUE',r.stdout)
   self.assertEqual(before,{p.relative_to(root).as_posix():p.read_bytes() for p in root.rglob('*') if p.is_file()})
