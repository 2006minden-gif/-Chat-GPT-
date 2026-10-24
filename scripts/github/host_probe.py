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
report['secret_presence']={name:bool(os.environ.get(name,'')) for name in ['SSH_HOST','SSH_PORT','SSH_USER','DEPLOY_PATH','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS']}
import health
report['public_health']=health.snapshot()
try:
 remote=Remote(Path('.'),revision,'readonly-probe')
 # Select a PHP 8.4 CLI from known executable names, without changing server configuration.
 import shlex
 command="""set -u
printf 'ND_SSH_OK\n'
candidates=$( { command -v php 2>/dev/null || true; find /usr/bin /usr/local /opt -maxdepth 6 -type f -name 'php' 2>/dev/null || true; } | sort -u)
selected=''
fallback=''
for b in $candidates; do
 v=$("$b" -n -r 'echo PHP_VERSION_ID;' 2>/dev/null) || continue
 case "$v" in ''|*[!0-9]*) continue;; esac
 if [ "$v" -ge 80400 ]; then selected="$b"; break; fi
 if [ "$v" -ge 70000 ]; then fallback="$b"; fi
done
if [ -n "$selected" ]; then printf '%s\n' "$selected"; elif [ -n "$fallback" ]; then printf '%s\n' "$fallback"; else exit 1; fi
"""
 r=subprocess.run(remote.ssh+[remote.target,'bash -se'],input=command,capture_output=True,text=True,timeout=45)
 if 'ND_SSH_OK' not in r.stdout:
  categories={'Permission denied':'ssh_authentication_failed','Connection refused':'ssh_connection_refused','timed out':'ssh_connection_timeout','Host key verification failed':'ssh_host_key_verification_failed','REMOTE HOST IDENTIFICATION HAS CHANGED':'ssh_host_key_changed','Could not resolve hostname':'ssh_dns_failed'}
  report['ssh_exit_code']=r.returncode
  diagnostic=r.stdout+'\n'+r.stderr
  for name in ['GH_TOKEN','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS','SSH_HOST','SSH_USER','DEPLOY_PATH']:
   secret=os.environ.get(name,'')
   if secret:diagnostic=diagnostic.replace(secret,'<redacted>')
  import re
  diagnostic=re.sub(r'-----BEGIN [^-]*PRIVATE KEY-----[\s\S]*?-----END [^-]*PRIVATE KEY-----','<redacted key>',diagnostic)
  report['transport_diagnostic']=diagnostic[:800]
  raise RemoteFailure(next((name for marker,name in categories.items() if marker in r.stderr),'ssh_session_unavailable'))
 report['ssh_connected']=True
 if r.returncode:
  inventory=r"command -v php 2>/dev/null || true; php -n -v 2>/dev/null || true; find /usr/bin /usr/local /opt -maxdepth 6 \( -name php -o -name 'php[0-9]*' \) 2>/dev/null | head -60"
  details=subprocess.run(remote.ssh+[remote.target,'bash -se'],input=inventory,capture_output=True,text=True,timeout=45)
  import re
  report['php_inventory']=[line for line in details.stdout.splitlines() if re.match(r'^(PHP [0-9]|/(usr|opt)/[A-Za-z0-9_./+-]+$)',line)][:60]
  raise RemoteFailure('readable_php_cli_not_found')
 php=r.stdout.split('ND_SSH_OK',1)[1].strip()
 import re
 if not re.fullmatch(r'/[A-Za-z0-9_./+-]+',php):raise RemoteFailure('unexpected_php_command')
 report['diagnostic_php_binary']=php
 script=Path('scripts/deploy/readonly-probe.php').read_text()
 r=subprocess.run(remote.ssh+[remote.target,shlex.join([php,'/dev/stdin'])],input=script,capture_output=True,text=True,timeout=45)
 if r.returncode:raise RemoteFailure('readonly_probe_failed')
 report['host']=json.loads(r.stdout)
except Exception as error:report['error_type']=type(error).__name__;report['error']=str(error) if isinstance(error,RemoteFailure) else 'readonly_diagnostic_unavailable'
finally:
 if remote:remote.close()
publish(report)
print('Read-only diagnostic evidence returned; no application or database changes')
