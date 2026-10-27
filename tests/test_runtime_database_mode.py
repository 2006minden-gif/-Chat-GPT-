import json
import test_prelaunch as fixture
class RuntimeDatabaseMode(fixture.Prelaunch):
 def test_session_validation_and_utc_preserve_host_configuration(self):
  original=self.sql('SELECT @@GLOBAL.sql_mode AS mode')[0]['mode']
  value=json.loads(self.php_eval('require $v["root"]."/private/app.php";$p=db();echo json_encode($p->query("SELECT @@SESSION.sql_mode AS mode,@@SESSION.time_zone AS tz")->fetch());',{'root':str(self.path)}))
  self.assertRegex(value['mode'],r'STRICT_(TRANS_TABLES|ALL_TABLES)');self.assertEqual(value['tz'],'+00:00');self.assertEqual(self.sql('SELECT @@GLOBAL.sql_mode AS mode')[0]['mode'],original)
for name in dir(fixture.Prelaunch):
 if name.startswith('test_'):setattr(RuntimeDatabaseMode,name,None)
