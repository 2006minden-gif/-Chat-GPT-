"""Run the deployed notification worker; no token/lead data leaves the host."""
from pathlib import Path
import shlex
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from client import Remote,ACCOUNT
if __name__=='__main__':
    remote=None
    try:
        remote=Remote(Path('.'),'','notifications')
        worker=ACCOUNT+'/private/notifications/worker.php'
        command='if [ -f '+shlex.quote(worker)+' ]; then '+shlex.join([remote.php,worker])+'''; else printf '%s' '{"ok":true,"not_installed":true}'; fi'''
        result=remote.command(command,json_output=True)
        # Explicit safe output allowlist: never print remote arbitrary payloads.
        import json
        print(json.dumps({k:result[k] for k in ['ok','sent','configured','deferred','busy','error_code','not_installed','email_jobs_processed','email_evidence'] if k in result}))
    except Exception:
        print('{"ok":false,"error":"notification_retry_failed"}');sys.exit(1)
    finally:
        if remote:remote.close()
