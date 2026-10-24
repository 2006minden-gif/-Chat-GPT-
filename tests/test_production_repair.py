"""Only synthetic temporary configs. Never touches production credentials or a remote host."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

class RepairSyntax(unittest.TestCase):
 def helper(self,code,source):
  php=os.environ.get('PHP_BIN','php');script="define('NEURO_REPAIR_LIBRARY',true);require $argv[1];$v=json_decode(stream_get_contents(STDIN),true);"+code
  r=subprocess.run([php,'-r',script,str(ROOT/'scripts/repair/production.php')],input=json.dumps(source),text=True,capture_output=True)
  self.assertEqual(r.returncode,0);self.assertEqual(r.stderr,'');return json.loads(r.stdout)
 def test_missing_comma_preserves_all_scalar_spellings(self):
  s="<?php return ['db_password'=>'SYNTHETIC_ONLY',\n'app_url'=>'https://example.invalid'\n'privacy_policy_approved'=>false,'setup_key'=>'','db_port'=>3306];"
  d=self.helper("$c=rp_config_candidate($v);echo json_encode(['kind'=>$c['kind'],'same'=>rp_literal_signature($v)===rp_literal_signature($c['content']),'valid'=>rp_static_config($c['content'])]);",s)
  self.assertEqual(d,{'kind':'missing_comma','same':True,'valid':True})
 def test_multiple_separator_candidate_preserves_literal_spelling(self):
  self.assertTrue(self.helper("$c=rp_config_candidate($v);echo json_encode(rp_static_config($c['content'])&&rp_literal_signature($v)===rp_literal_signature($c['content']));", "<?php return ['a'=>1 'b'=>2 'c'=>false];"))
 def test_valid_config_is_unchanged(self):
  s="<?php return ['db_password'=>'SYNTHETIC_ONLY','privacy_policy_approved'=>false];"
  self.assertTrue(self.helper("$c=rp_config_candidate($v);echo json_encode($v===$c['content']);",s))
 def test_refuses_unterminated_string_multiple_defects_and_executable_config(self):
  for s in ["<?php return ['db_password'=>'unterminated];", "<?php return ['a'=>getenv('SECRET')];", "<?php file_put_contents('/tmp/SHOULD_NOT_EXIST','x'); return [];", "<?php return ['a'=>\"$secret\"];", "<?php return ['a'=>1]; echo 'leak';"]:
   self.assertTrue(self.helper("try{rp_config_candidate($v);echo 'false';}catch(RepairFailure $e){echo 'true';}",s))
 def test_handles_comments_nested_arrays_and_booleans_without_reformat(self):
  for s in ["<?php return array('a'=>array('b'=>true)\n/* preserve */'c'=>null);", "<?php declare(strict_types=1); return ['a'=>-2\n'b'=>false];"]:
   self.assertTrue(self.helper("$c=rp_config_candidate($v);echo json_encode(rp_static_config($c['content'])&&rp_literal_signature($v)===rp_literal_signature($c['content']));",s))
 def test_inspect_is_redacted_and_does_not_write(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp);(p/'private').mkdir();(p/'public_html').mkdir();(p/'private/config.php').write_text("<?php return ['db_password'=>'SYNTHETIC_ONLY'\n'privacy_policy_approved'=>false];");(p/'public_html/.htaccess').write_text('Options -Indexes\n')
   before={str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()}
   r=subprocess.run([os.environ.get('PHP_BIN','php'),str(ROOT/'scripts/repair/production.php'),'inspect',tmp],env=dict(os.environ,NEURO_REPAIR_TEST='1'),text=True,capture_output=True)
   self.assertEqual(r.returncode,0);self.assertNotIn('SYNTHETIC_ONLY',r.stdout+r.stderr);d=json.loads(r.stdout);self.assertTrue(d['configuration']['automatic_repair_available']);self.assertEqual({str(f):f.read_bytes() for f in p.rglob('*') if f.is_file()},before)

if __name__=='__main__':unittest.main()
