"""Run the deployed notification worker; no token/lead data leaves the host."""
from pathlib import Path
import shlex
import sys
import re
import os
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from client import Remote,ACCOUNT

def safe_diagnostic(value):
    """A compromised/old remote must not turn runner logs into a secret dump."""
    out={}
    source=value.get('max_diagnostic',{})
    if isinstance(source,dict):
        diag={k:v for k,v in source.items() if k in
              ('configured','enabled','owner_bound','is_bot','stored_bot_matches','site_webhook_present') and type(v) is bool}
        for key in ('stored_error','identity','subscriptions','error'):
            v=source.get(key)
            if v in ('','ok','max_connection_failed','max_auth_failed','max_rate_limited','max_api_failed','max_invalid_response','max_delivery_failed','diagnostic_failed','diagnostic_unavailable'):
                diag[key]=v
        if type(source.get('subscription_count')) is int and 0<=source['subscription_count']<=100:
            diag['subscription_count']=source['subscription_count']
        hosts=source.get('webhook_hosts',[])
        if isinstance(hosts,list):diag['webhook_hosts']=[h for h in hosts[:100] if isinstance(h,str) and re.fullmatch(r'[a-zA-Z0-9.-]{1,253}',h)]
        out['max_diagnostic']=diag
    network=value.get('max_network',{})
    if isinstance(network,dict):
        out['max_network']={}
        for host in ('platform-api2.max.ru','platform-api.max.ru','botapi.max.ru'):
            row=network.get(host,{})
            if not isinstance(row,dict):continue
            clean={k:v for k,v in row.items() if k in ('dns_ipv4_count','http_status') and type(v) is int and 0<=v<=599}
            if row.get('connection')=='failed':clean['connection']='failed'
            if row.get('failure_kind') in ('dns','tls','timeout','transport'):clean['failure_kind']=row['failure_kind']
            out['max_network'][host]=clean
    return out

if __name__=='__main__':
    remote=None
    try:
        remote=Remote(Path('.'),'','notifications')
        worker=ACCOUNT+'/private/notifications/worker.php'
        args=[remote.php,worker]
        if os.environ.get('MAX_RETRY_NOW')=='1':args.append('--retry-max-now')
        command='if [ -f '+shlex.quote(worker)+' ]; then '+shlex.join(args)+'''; else printf '%s' '{"ok":true,"not_installed":true}'; fi'''
        result=remote.command(command,json_output=True)
        # Explicit safe output allowlist: never print remote arbitrary payloads.
        import json
        print(json.dumps({k:result[k] for k in ['ok','sent','configured','deferred','busy','error_code','not_installed','email_jobs_processed','email_evidence','access_jobs_processed','support_jobs_processed'] if k in result}))
        if result.get('error_code','').startswith('max_') or result.get('deferred'):
            # Reviewed source travels via SSH stdin; no runtime secrets leave the host.
            diagnostic=remote.command(shlex.join([remote.php,'/dev/stdin']),
                input=Path(__file__).with_name('diagnose.php').read_text(),json_output=True)
            print(json.dumps(safe_diagnostic(diagnostic)))
        # Executing a worker is not evidence of successful delivery. Keep retries
        # scheduled, but make a persisted MAX delivery failure visible in Actions.
        if result.get('error_code','').startswith('max_'):
            sys.exit(1)
    except Exception:
        print('{"ok":false,"error":"notification_retry_failed"}');sys.exit(1)
    finally:
        if remote:remote.close()
