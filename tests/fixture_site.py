"""Isolated integration suite. Creates/drops only a random neuro_test_* database.
Requires NEURO_TEST_DSN=mysql:host=127.0.0.1;port=... and optional test DB
admin credentials NEURO_TEST_USER/PASSWORD; PHP_BIN selects an executable.
Copies the application into a temporary directory; never writes live config.php.
"""
import hashlib, json, os, secrets, shutil, socket, subprocess, tempfile, time, unittest
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
class Prelaunch(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.stage=1
  cls.php=os.environ.get('PHP_BIN','php')
  dsn=os.environ.get('NEURO_TEST_DSN','')
  if not dsn.startswith('mysql:host=127.0.0.1;port=') or ';dbname=' in dsn:
   raise RuntimeError('Provide a loopback-only NEURO_TEST_DSN without a database name; never use production credentials')
  cls.dbname='neuro_test_'+secrets.token_hex(8)
  cls.dbargs={'dsn':dsn+';charset=utf8mb4','user':os.environ.get('NEURO_TEST_USER','root'),'password':os.environ.get('NEURO_TEST_PASSWORD','')}
  cls.tmp=tempfile.TemporaryDirectory();cls.path=Path(cls.tmp.name)
  for name in ['public','private','tests','scripts','database']:shutil.copytree(ROOT/name,cls.path/name,ignore=shutil.ignore_patterns('config.php','__pycache__'))
  cls.password=secrets.token_urlsafe(24)
  cls.sql('CREATE DATABASE `'+cls.dbname+'` CHARACTER SET utf8mb4',admin=True)
  cls.addClassCleanup(cls.cleanup)
  cls.sql((ROOT/'database/schema.sql').read_text())
  cls.sql("INSERT INTO nd_admin VALUES (1, '"+cls.php_eval('echo password_hash($v["password"], PASSWORD_DEFAULT);',{'password':cls.password})+"')")
  sock=socket.socket();sock.bind(('127.0.0.1',0));cls.port=sock.getsockname()[1];sock.close();cls.base='http://127.0.0.1:'+str(cls.port)
  cls.config={'db_host':'127.0.0.1','db_port':int(dsn.split('port=')[1]),'db_name':cls.dbname,'db_user':cls.dbargs['user'],'db_password':cls.dbargs['password'],'app_url':cls.base,'setup_key':''}
  if cls.stage>=5:
   cls.config.update(privacy_policy_approved=True,privacy_policy_version='test-policy-v1')
   (cls.path/'private/privacy-policy.txt').write_text('SYNTHETIC TEST FIXTURE ONLY. Not a legal policy.')
  cls.write_config()
  cls.log=(cls.path/'server.log').open('w');cls.proc=subprocess.Popen([cls.php,'-d','opcache.enable=0','-d','opcache.enable_cli=0','-S','127.0.0.1:'+str(cls.port),'-t',str(cls.path/'public'),str(cls.path/'public/site-router.php')],stdout=cls.log,stderr=cls.log)
  for _ in range(100):
   try:requests.get(cls.base,timeout=1);break
   except requests.ConnectionError:time.sleep(.1)
  else:raise RuntimeError('PHP server failed to start')
 @classmethod
 def php_eval(cls,code,values):
  r=subprocess.run([cls.php,'-r','$v=json_decode(stream_get_contents(STDIN),true);'+code],input=json.dumps(values),text=True,capture_output=True)
  if r.returncode:raise RuntimeError('Isolated PHP helper failed: '+r.stderr[:150])
  return r.stdout.strip()
 @classmethod
 def sql(cls,sql,admin=False,params=None):
  v=dict(cls.dbargs);v['dsn']+=('' if admin else ';dbname='+cls.dbname);v.update(sql=sql,params=params or [])
  output=cls.php_eval('$p=new PDO($v["dsn"],$v["user"],$v["password"],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]); if($v["params"]){$q=$p->prepare($v["sql"]);$q->execute($v["params"]);}else{$q=$p->query($v["sql"]);}echo json_encode($q->columnCount() ? $q->fetchAll(PDO::FETCH_ASSOC) : []);',v)
  return json.loads(output)
 @classmethod
 def write_config(cls):
  def q(v):
   if isinstance(v,bool):return 'true' if v else 'false'
   return "'"+str(v).replace('\\','\\\\').replace("'","\\'")+"'"
  (cls.path/'private/config.php').write_text('<?php return ['+','.join(q(k)+'=>'+q(v) for k,v in cls.config.items())+'];')
 @classmethod
 def cleanup(cls):
  if hasattr(cls,'proc'):cls.proc.terminate();cls.proc.wait(timeout=5);cls.log.close()
  cls.sql('DROP DATABASE `'+cls.dbname+'`',admin=True);cls.tmp.cleanup()
 def setUp(self):self.sql('DELETE FROM nd_limits')
 def api(self,route):return self.base+'/portfolio-api.php?r='+route
 def lead(self,**changes):
  data={'name':'Тест','contact':'test@example.com','service':'ИИ-агент','idea':'Тестовый проект'}
  if self.stage>=3:data['idempotency_key']=secrets.token_hex(32)
  if self.stage>=5:data.update(consent=True,policy_version='test-policy-v1')
  data.update(changes);return data
 def owner(self):
  s=requests.Session();r=s.post(self.api('login'),json={'password':self.password});self.assertEqual(r.status_code,200);return s,{'X-CSRF-Token':r.json()['csrf']}
