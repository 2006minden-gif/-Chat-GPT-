"""Read-only issue 10 diagnostic. Never transfers production config; only reviewed PHP code goes in."""
import json,os,sys,shlex
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from client import Remote,ACCOUNT,RemoteFailure
from bridge import publish
plan=json.load(open('.github/control-plan.json'));report={'schema_version':1,'source_sha':os.environ['GITHUB_SHA'],'nonce':plan['nonce'],'run_id':os.environ['GITHUB_RUN_ID'],'production_touched':False,'issue10_inspection':True}
remote=None
try:
 remote=Remote(Path('.'),os.environ['GITHUB_SHA'],'readonly-issue10')
 report['php_capabilities']=remote.command(shlex.join(['/usr/bin/php8.4','-r',"echo json_encode(['ok'=>true,'tokenizer'=>function_exists('token_get_all'),'extension_dir'=>ini_get('extension_dir'),'module_exists'=>is_file(ini_get('extension_dir').'/tokenizer.so')]);"]),json_output=True)
 report['diagnosis']=remote.command(shlex.join(['/usr/bin/php8.4','/dev/stdin','inspect',ACCOUNT]),Path('scripts/repair/production.php').read_text(),True)
except Exception as e:
 report['error']=str(e) if isinstance(e,RemoteFailure) else type(e).__name__
 if isinstance(e,RemoteFailure):report['safe_diagnostic']={k:v for k,v in e.details.items() if k in ['ok','error','type'] and isinstance(v,(bool,str))}
finally:
 if remote:remote.close()
publish(report);print('Issue 10 metadata only; no production write')
