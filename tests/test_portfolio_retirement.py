"""Real reversible legacy-to-portfolio transition, files and MySQL foreign keys."""
import hashlib,json,shutil
from pathlib import Path
import requests
import fixture_site as fixture

class Retirement(fixture.Prelaunch):
 def setUp(self):
  self.sql('SET FOREIGN_KEY_CHECKS=0;'+''.join('DROP TABLE `'+r['TABLE_NAME']+'`;' for r in self.sql('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()'))+'SET FOREIGN_KEY_CHECKS=1;')
  parents='''CREATE TABLE nd_orders(id BIGINT UNSIGNED PRIMARY KEY);CREATE TABLE nd_customers(id BIGINT UNSIGNED PRIMARY KEY);CREATE TABLE nd_lc_templates(id BIGINT UNSIGNED PRIMARY KEY,kind VARCHAR(40));CREATE TABLE nd_lc_document_bindings(id BIGINT UNSIGNED PRIMARY KEY,order_id BIGINT UNSIGNED,template_id BIGINT UNSIGNED,state VARCHAR(20));'''
  self.sql(parents+(fixture.ROOT/'tests/fixtures/legacy.sql').read_text())
  self.sql("INSERT INTO nd_admin VALUES(1,'KEEP_PASSWORD');INSERT INTO nd_leads(name,contact,service,idea,notes,created) VALUES('KEEP','KEEP','KEEP','KEEP','KEEP',1)")
  self.raw=json.dumps({'title':'Existing','media':[]},ensure_ascii=False);self.digest=hashlib.sha256(self.raw.encode()).hexdigest()
  self.sql("INSERT INTO nd_publications(id,kind,slug,state,head_revision,published_version_id) VALUES(7,'portfolio','existing','PUBLISHED',1,11)")
  self.sql('INSERT INTO nd_publication_versions(id,publication_id,revision_number,body_json,checksum) VALUES(11,7,1,?,?)',params=[self.raw,self.digest])
  self.root=self.path/'retirement';shutil.rmtree(self.root,ignore_errors=True);self.root.mkdir();shutil.copytree(self.path/'private',self.root/'private');shutil.copytree(self.path/'public',self.root/'public_html')
  (self.root/'private/config.php').write_bytes((self.path/'private/config.php').read_bytes());(self.root/'private/old-contract.pdf').write_bytes(b'KEEP_DOCUMENT');(self.root/'public_html/customer.php').write_text('OLD_CODE');(self.root/'private/legacy.php').write_text('OLD_PRIVATE')
  self.candidate=self.path/'candidate';shutil.rmtree(self.candidate,ignore_errors=True);shutil.copytree(fixture.ROOT/'public',self.candidate/'public_html');shutil.copytree(fixture.ROOT/'database',self.candidate/'database')
  self.policy={'auth_tables':['nd_admin','nd_sessions','nd_limits'],'portfolio_tables':['nd_pf_items','nd_pf_versions','nd_pf_media']};self.policy['legacy_tables']=[r['TABLE_NAME'] for r in self.sql('SELECT TABLE_NAME FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE()') if r['TABLE_NAME'] not in self.policy['auth_tables']]
  self.manifest={'revision':'a'*40,'portfolio_retirement':self.policy,'files':{**{'public_html/'+p.name:'' for p in (fixture.ROOT/'public').iterdir()},'private/site.php':'','private/site-view.php':''}}
 def helper(self,code):
  return json.loads(self.php_eval('require $v["helper"];require $v["recovery"]; $root=$v["root"];$m=$v["manifest"];$candidate=$v["candidate"];'+code,{'helper':str(fixture.ROOT/'scripts/deploy/portfolio-retirement.php'),'recovery':str(fixture.ROOT/'scripts/deploy/recovery.php'),'root':str(self.root),'manifest':self.manifest,'candidate':str(self.candidate)}))
 def begin(self):return self.helper('echo json_encode(pt_begin($root,$candidate,$m,"test-release"));')
 def populate(self):return self.helper('$backup=$root."/backup";nr_rehearse(require $root."/private/config.php",$backup."/database-recovery");echo json_encode(pt_populate($root,$candidate,$m,$backup));')
 def test_copy_cleanup_preserves_data_password_media_and_documents(self):
  self.assertEqual(self.begin()['phase'],'renamed');self.assertEqual(self.populate()['copy'],{'items':1,'versions':1,'media':0})
  self.assertEqual(self.sql('SELECT body_json,checksum FROM nd_pf_versions')[0],{'body_json':self.raw,'checksum':self.digest})
  self.assertEqual(self.sql('SELECT rights_verified FROM nd_pf_items')[0]['rights_verified'],1)
  result=self.helper('pt_ready($root);echo json_encode(pt_cleanup($root,$m,fn()=>["available"=>true,"removed"=>1]));')
  self.assertTrue(result['physical_cleanup_verified']);self.assertEqual(result['active_table_count'],6)
  self.assertFalse((self.root/'private/legacy.php').exists());self.assertFalse((self.root/'public_html/customer.php').exists())
  archive=self.root/'.neurodelo-retired/test-release';self.assertEqual((archive/'removed/private/old-contract.pdf').read_bytes(),b'KEEP_DOCUMENT')
  self.assertEqual(self.sql('SELECT password_hash FROM nd_admin')[0]['password_hash'],'KEEP_PASSWORD');self.assertEqual(self.sql('SELECT name FROM nd_archive_leads')[0]['name'],'KEEP')
  self.assertEqual(self.helper('echo json_encode(array_keys(require $root."/private/config.php"));'),['db_host','db_port','db_name','db_user','db_password','app_url'])
  self.assertTrue(self.helper('echo json_encode(pt_cleanup($root,$m,fn()=>[]));')['physical_cleanup_verified'])
 def test_order_linked_visibility_uses_only_existing_exact_grants(self):
  self.sql("INSERT INTO nd_orders VALUES(1);INSERT INTO nd_customers VALUES(1);INSERT INTO nd_lc_templates VALUES(1,'portfolio_permission');INSERT INTO nd_lc_document_bindings VALUES(1,1,1,'AGREED')")
  for pid in [8,9]:
   self.sql("INSERT INTO nd_publications(id,kind,slug,order_id,state,head_revision,published_version_id) VALUES(?,'portfolio',?,1,'PUBLISHED',1,?)",params=[pid,'customer-'+str(pid),pid+10])
   self.sql('INSERT INTO nd_publication_versions(id,publication_id,revision_number,body_json,checksum) VALUES(?,?,1,?,?)',params=[pid+10,pid,self.raw,self.digest])
  self.sql("INSERT INTO nd_publication_permissions(version_id,binding_id,customer_id,state) VALUES(18,1,1,'GRANTED'),(19,1,1,'REVOKED')")
  self.begin();self.populate();self.assertEqual(self.sql('SELECT id,rights_verified FROM nd_pf_items ORDER BY id'),[{'id':7,'rights_verified':1},{'id':8,'rights_verified':1},{'id':9,'rights_verified':0}])
 def test_rollback_restores_original_names_and_rows(self):
  self.begin();self.populate();self.helper('pt_ready($root);pt_rollback($root);echo json_encode(pt_summary(pt_read($root)));')
  self.assertEqual(self.sql('SELECT body_json FROM nd_publication_versions')[0]['body_json'],self.raw)
  self.assertEqual(self.sql("SELECT COUNT(*) n FROM information_schema.tables WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME LIKE 'nd_pf_%'")[0]['n'],0)
  self.assertFalse((self.root/'portfolio-transition.json').exists())
 def test_unknown_schema_fails_before_renaming(self):
  self.sql('CREATE TABLE nd_unexpected(id INT)');result=self.helper('try{pt_begin($root,$candidate,$m,"test-release");echo "null";}catch(RuntimeException $e){echo json_encode($e->getMessage());}')
  self.assertEqual(result,'retirement_schema_changed');self.assertEqual(len(self.sql('SELECT * FROM nd_leads')),1)
 def test_corrupt_recovery_archive_blocks_file_removal(self):
  self.begin();self.populate();archive=self.root/'.neurodelo-retired/test-release';state=json.loads((self.root/'.neurodelo-retired/state.json').read_text());entry=next(iter(state['database_files']));(archive/'database-recovery'/entry).write_text('CORRUPTED')
  result=self.helper('pt_ready($root);try{pt_cleanup($root,$m,fn()=>[]);echo "null";}catch(RuntimeException $e){echo json_encode($e->getMessage());}')
  self.assertEqual(result,'retirement_archive_corrupt');self.assertTrue((self.root/'public_html/customer.php').exists());self.assertEqual(len(self.sql('SELECT * FROM nd_archive_leads')),1)
