"""Read-only HTTP checks. No credentials, lead submissions, login attempts or response-body logs."""
import json
import hashlib
import re
import time
import urllib.error
import urllib.request

DENIED_PATHS=['/~.htaccess','/index~.html','/.htaccess','/private/config.php','/index.html','/crm.html']
ASSET_PATHS=['/styles.css','/crm.css','/script.js','/crm.js','/api-client.js']
PATHS=['/','/studio.php','/api.php?r=privacy','/privacy.php','/api.php?r=session','/api.php?r=leads']+DENIED_PATHS+ASSET_PATHS

def snapshot(base='https://neurodelo.pro', opener=urllib.request.urlopen, extra_assets=()):
    assets = list(dict.fromkeys(ASSET_PATHS + list(extra_assets)))
    if any(not re.fullmatch(r'/[A-Za-z0-9_-][A-Za-z0-9_./-]*\.(css|js)', p) or '..' in p.split('/') for p in assets):
        raise ValueError('unsafe_health_asset_path')
    rows = {}
    for path in list(dict.fromkeys(PATHS + assets)):
        head = path in DENIED_PATHS
        url = base.rstrip('/') + path + ('&' if '?' in path else '?') + '_nd_check=' + str(time.time_ns())
        try:
            req = urllib.request.Request(url, method='HEAD' if head else 'GET', headers={'Cache-Control':'no-cache','User-Agent':'NeuroDelo-deployment-health/1'})
            try: response = opener(req, timeout=15)
            except urllib.error.HTTPError as error: response = error
            body = b'' if head else response.read(131073)
            row = {'status':response.status,'content_type':response.headers.get('Content-Type','').split(';')[0].lower(),
                   'request_id':response.headers.get('X-Request-ID'),'transport_ok':True}
            # Redirects to another origin/path are not evidence that this endpoint works.
            row['redirected'] = response.url != url
            text = body.decode('utf-8','replace')
            if len(body) > 131072: row['oversized'] = True
            data = None
            if row['content_type']=='application/json':
                try: data=json.loads(text)
                except ValueError: pass
            if path in ['/', '/studio.php']:
                row['ok']=response.status==200 and row['content_type']=='text/html' and 'НейроДело' in text
            elif path=='/api.php?r=privacy':
                row['ok']=response.status==200 and isinstance(data,dict) and isinstance(data.get('enabled'),bool) and isinstance(data.get('version'),str) and data.get('url')=='/privacy.php'
                if row['ok']:
                    row['ok'] = bool(re.fullmatch(r'[A-Za-z0-9._-]{1,64}',data['version'])) if data['enabled'] else data['version']==''
                    row['enabled']=data['enabled'];row['version']=data['version']
            elif path=='/privacy.php':
                policy=rows.get('/api.php?r=privacy',{})
                row['ok']=policy.get('ok',False) and row['content_type']=='text/html' and (
                    (policy['enabled'] and response.status==200 and ('Версия: '+policy['version']) in text) or
                    (not policy['enabled'] and response.status==503 and 'Приём заявок через форму отключён' in text))
            elif path in ['/api.php?r=session','/api.php?r=leads']:
                row['ok']=response.status==401 and isinstance(data,dict) and isinstance(data.get('detail'),str)
            elif path in assets:
                expected=['text/css'] if path.endswith('.css') else ['application/javascript','text/javascript']
                row['ok']=response.status==200 and row['content_type'] in expected;row['sha256']=hashlib.sha256(body).hexdigest()
            else: row['ok']=response.status in [403,404]
            row['ok'] = bool(row['ok'] and not row['redirected'] and not row.get('oversized',False))
            response.close();rows[path]=row
        except Exception as error:
            rows[path]={'ok':False,'transport_ok':False,'error_type':type(error).__name__}
    return {'ok':all(row['ok'] for row in rows.values()),'complete':all(row['transport_ok'] for row in rows.values()),'checks':rows}

def same_baseline(before, after):
    if not before.get('complete') or not after.get('complete'): return False
    def semantic(report):
        return {path:{key:row.get(key) for key in ['ok','status','content_type','enabled','version','redirected','sha256']} for path,row in report['checks'].items()}
    return semantic(before)==semantic(after)


def only_preexisting_failures(before, after):
    if before.get('ok') or not before.get('complete') or not after.get('complete'):return False
    if set(before['checks'])!=set(after['checks']):return False
    for path,row in after['checks'].items():
        if row['ok']:continue
        original=before['checks'][path]
        if original['ok']:return False
        for key in ['status','content_type','enabled','version','redirected','sha256']:
            if row.get(key)!=original.get(key):return False
    return True


def require_asset_revision(report, expected):
    for path,digest in (expected or {}).items():
        row=report['checks'].get(path)
        if row is None or row.get('sha256')!=digest:
            if row is not None:row['ok']=False;row['error']='asset_revision_mismatch'
            report['ok']=False
    return report
