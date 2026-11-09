"""Actual MySQL snapshot/shadow restore, in a disposable loopback database only."""
import hashlib,json,secrets,shutil,time
from pathlib import Path
import test_prelaunch as fixture

class DatabaseRecovery(fixture.Prelaunch):
 def setUp(self):
  self.sql('DROP TABLE IF EXISTS nd_recovery_children');self.sql('DROP TABLE IF EXISTS nd_recovery_parents')
  self.folder=self.path/('recovery-'+secrets.token_hex(8))
 def run_php(self,code):
  prefix='require $v["root"]."/scripts/deploy/recovery.php";$c=require $v["root"]."/private/config.php";'
  return json.loads(self.php_eval(prefix+code,{'root':str(self.path),'folder':str(self.folder)}))
 def shadows(self):
  return [x['TABLE_NAME'] for x in self.sql('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()') if x['TABLE_NAME'].startswith('nd_r_')]
 def test_actual_rows_unicode_binary_and_null_restore_without_source_changes(self):
  self.sql('CREATE TABLE nd_recovery_parents(id INT PRIMARY KEY,payload VARBINARY(100) NOT NULL,label VARCHAR(100),nullable_value TEXT NULL) ENGINE=InnoDB')
  self.sql('CREATE TABLE nd_recovery_children(id INT PRIMARY KEY,parent_id INT,CONSTRAINT nd_recovery_test_fk FOREIGN KEY(parent_id) REFERENCES nd_recovery_parents(id)) ENGINE=InnoDB')
  self.sql('INSERT INTO nd_recovery_parents VALUES (?,UNHEX(?),?,NULL)',params=[1,'00fffe10','Юникод; DROP TABLE nd_admin; не SQL'])
  self.sql('INSERT INTO nd_recovery_children VALUES (1,1)')
  before=self.sql('SELECT HEX(payload) AS payload,label,nullable_value FROM nd_recovery_parents')
  proof=self.run_php('echo json_encode(nr_rehearse($c,$v["folder"]));')
  self.assertTrue(proof['verified']);self.assertTrue(proof['shadow_tables_removed']);self.assertFalse(proof['source_data_written'])
  self.assertGreaterEqual(proof['tables_verified'],6);self.assertEqual(proof['foreign_keys_verified'],1)
  self.assertEqual(self.sql('SELECT HEX(payload) AS payload,label,nullable_value FROM nd_recovery_parents'),before)
  self.assertNotIn('Юникод',json.dumps(proof));self.assertEqual(self.shadows(),[])
  for file in ['schema.json','rows.jsonl','verified.json']:self.assertEqual((self.folder/file).stat().st_mode&0o777,0o600)
 def test_restore_uses_backup_snapshot_not_newer_live_rows(self):
  self.run_php('nr_snapshot(nr_pdo($c),$v["folder"]);echo "{}";')
  self.sql("INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES ('SYNTHETIC','test@example.com','Сайт или лендинг','Newer than backup','',?)",params=[int(time.time())])
  current=int(self.sql('SELECT COUNT(*) AS n FROM nd_leads')[0]['n'])
  proof=self.run_php('echo json_encode(nr_restore_verify(nr_pdo($c),$v["folder"]));')
  self.assertTrue(proof['verified']);self.assertEqual(int(self.sql('SELECT COUNT(*) AS n FROM nd_leads')[0]['n']),current);self.assertEqual(self.shadows(),[])
 def test_corrupt_backup_refused_before_clone_or_source_writes(self):
  self.run_php('nr_snapshot(nr_pdo($c),$v["folder"]);echo "{}";')
  with (self.folder/'rows.jsonl').open('a') as f:f.write('tampered')
  result=self.run_php('try{nr_restore_verify(nr_pdo($c),$v["folder"]);echo "{}";}catch(Throwable $e){echo json_encode(["error"=>$e->getMessage()]);}')
  self.assertEqual(result['error'],'recovery_backup_checksum_mismatch');self.assertEqual(self.shadows(),[])
 def test_foreign_keys_checked_and_scratch_removed_on_bad_backup(self):
  self.sql('CREATE TABLE nd_recovery_parents(id INT PRIMARY KEY) ENGINE=InnoDB');self.sql('CREATE TABLE nd_recovery_children(id INT PRIMARY KEY,parent_id INT,FOREIGN KEY(parent_id) REFERENCES nd_recovery_parents(id)) ENGINE=InnoDB')
  self.sql('INSERT INTO nd_recovery_parents VALUES(1)');self.sql('INSERT INTO nd_recovery_children VALUES(1,1)')
  self.run_php('nr_snapshot(nr_pdo($c),$v["folder"]);echo "{}";')
  import base64
  rows=[json.loads(x) for x in (self.folder/'rows.jsonl').read_text().splitlines()]
  for name,values in rows:
   if name=='nd_recovery_children':values[1]=base64.b64encode(b'999').decode()
  raw=''.join(json.dumps(x,separators=(',',':'))+'\n' for x in rows).encode();(self.folder/'rows.jsonl').write_bytes(raw)
  manifest=json.loads((self.folder/'schema.json').read_text());manifest['data_sha256']=hashlib.sha256(raw).hexdigest()
  encoded=[v for name,v in rows if name=='nd_recovery_children'];manifest['tables']['nd_recovery_children']['data']['sha256']=hashlib.sha256(''.join(json.dumps(x,separators=(',',':'))+'\n' for x in encoded).encode()).hexdigest()
  (self.folder/'schema.json').write_text(json.dumps(manifest))
  result=self.run_php('try{nr_restore_verify(nr_pdo($c),$v["folder"]);echo "{}";}catch(Throwable $e){echo json_encode(["error"=>$e->getMessage()]);}')
  self.assertEqual(result['error'],'recovery_foreign_key_verification_failed');self.assertEqual(self.shadows(),[])
  self.assertEqual(int(self.sql('SELECT parent_id FROM nd_recovery_children WHERE id=1')[0]['parent_id']),1)
 def test_existing_backup_directory_never_overwritten(self):
  self.folder.mkdir();(self.folder/'keep').write_text('KEEP')
  result=self.run_php('try{nr_snapshot(nr_pdo($c),$v["folder"]);echo "{}";}catch(Throwable $e){echo json_encode(["error"=>$e->getMessage()]);}')
  self.assertEqual(result['error'],'recovery_path_collision');self.assertEqual((self.folder/'keep').read_text(),'KEEP')

for name in vars(fixture.Prelaunch):
 if name.startswith('test_') and name not in vars(DatabaseRecovery):setattr(DatabaseRecovery,name,None)
