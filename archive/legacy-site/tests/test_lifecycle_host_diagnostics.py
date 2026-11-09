import json
import test_prelaunch as fixture

class HostDiagnostics(fixture.Prelaunch):
 def test_private_subprocess_error_is_classified_without_raw_data(self):
  folder=self.path/'diagnostic';folder.mkdir();path=folder/'migration-004_crm_foundation.log.error';path.write_text(json.dumps({'error':'strict_sql_mode_required','private':'DO_NOT_EXPORT'}))
  code="eval(substr(explode('$lock=null;',file_get_contents($v['root'].'/scripts/deploy/remote.php'))[0],5));echo json_encode(safe_subprocess_diagnostic($v['path']));"
  out=self.php_eval(code,{'root':str(self.path),'path':str(path)});self.assertEqual(json.loads(out)['code'],'strict_sql_mode_required');self.assertNotIn('DO_NOT_EXPORT',out)
  path=folder/'database.sql.error';path.write_text('mysqldump: Got error: 1045: Access denied for PRIVATE_USER with PRIVATE_PASSWORD')
  out=self.php_eval(code,{'root':str(self.path),'path':str(path)});self.assertEqual(json.loads(out),{'stage':'database_dump','code':'mysql_error_1045'});self.assertNotIn('PRIVATE',out)
  path.write_text('Unexpected PRIVATE secret error')
  out=self.php_eval(code,{'root':str(self.path),'path':str(path)});self.assertEqual(json.loads(out)['code'],'unclassified_private_subprocess_failure');self.assertNotIn('secret',out)

for name in dir(fixture.Prelaunch):
 if name.startswith('test_'):setattr(HostDiagnostics,name,None)
