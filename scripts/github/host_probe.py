"""Authorized read-only SSH diagnostics. Results return by Git; no raw configuration/log export."""
import json,os,subprocess,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from client import Remote, RemoteFailure, ACCOUNT
from bridge import publish
plan=json.loads(Path('.github/control-plan.json').read_text());revision=os.environ['GITHUB_SHA']
report={'schema_version':1,'nonce':plan['nonce'],'source_sha':revision,'run_id':os.environ['GITHUB_RUN_ID'],
 'run_url':'https://github.com/2006minden-gif/-Chat-GPT-/actions/runs/'+os.environ['GITHUB_RUN_ID'],'production_touched':False,'read_only_host_probe':True}
remote=None
try:
 remote=Remote(Path('.'),revision,'readonly-probe')
 # Select a PHP 8.4 CLI from known executable names, without changing server configuration.
 candidates=[remote.php,'php8.4','php84','/usr/local/bin/php8.4','/usr/local/php84/bin/php']
 import shlex
 command='for b in '+shlex.join(candidates)+'; do if command -v "$b" >/dev/null 2>&1; then v=$("$b" -r \'echo PHP_VERSION_ID;\' 2>/dev/null) || continue; if [ "$v" -ge 80400 ] 2>/dev/null; then printf \'%s\\n\' "$b"; exit 0; fi; fi; done; exit 1'
 r=subprocess.run(remote.ssh+[remote.target,command],capture_output=True,text=True,timeout=30)
 if r.returncode:raise RemoteFailure('php84_cli_not_found')
 php=r.stdout.strip()
 if php not in candidates:raise RemoteFailure('unexpected_php_command')
 script=Path('scripts/deploy/readonly-probe.php').read_text()
 r=subprocess.run(remote.ssh+[remote.target,shlex.join([php,'/dev/stdin'])],input=script,capture_output=True,text=True,timeout=45)
 if r.returncode:raise RemoteFailure('readonly_probe_failed')
 report['host']=json.loads(r.stdout)
except Exception as error:report['error_type']=type(error).__name__;report['error']=str(error) if isinstance(error,RemoteFailure) else 'readonly_diagnostic_unavailable'
finally:
 if remote:remote.close()
publish(report)
print('Read-only diagnostic evidence returned; no application or database changes')
