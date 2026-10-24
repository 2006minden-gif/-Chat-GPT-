"""Reviewed, one-time server-local repair coordinator; not a release or migration client."""
import argparse
import base64
import json
from pathlib import Path
import re
import shlex
import sys
import urllib.error
import urllib.parse
import urllib.request
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'deploy'))
from client import Remote,RemoteFailure,ACCOUNT
import health
ROOT=Path(__file__).resolve().parents[2]

class ServerRepair:
 def __init__(self,revision,plan_id):
  self.remote=Remote(ROOT,revision,plan_id or 'readonly-repair');self.remote.php='/usr/bin/php8.4'
 def close(self):self.remote.close()
 def rpc(self,operation,plan_id='',receipt=None):
  args=[self.remote.php,'/dev/stdin',operation,ACCOUNT,plan_id]
  if receipt is not None:args.append(base64.b64encode(json.dumps(receipt).encode()).decode())
  return self.remote.command(shlex.join(args),(ROOT/'scripts/repair/production.php').read_text(),True)

def probe_urls(plan_id):return ['/~.htaccess','/index~.html','/.nd-repair-'+plan_id+'.tmp','/nd-repair-'+plan_id+'.bak','/.nd-repair-'+plan_id+'/probe.txt']
def protection_probe(plan_id,base='https://neurodelo.pro'):
 class NoRedirect(urllib.request.HTTPRedirectHandler):
  def redirect_request(self,*args,**kwargs):return None
 opener=urllib.request.build_opener(NoRedirect());rows={}
 for path in probe_urls(plan_id)+['/.git/config','/.env','/config.php','/backup.zip']:
  rows[path]={}
  for method in ['GET','HEAD']:
   try:
    req=urllib.request.Request(base+path,method=method,headers={'Cache-Control':'no-cache','User-Agent':'NeuroDelo-repair-verification/1'})
    try:r=opener.open(req,timeout=15)
    except urllib.error.HTTPError as e:r=e
    # Even an unexpected public 200 is recorded WITHOUT reading its body.
    rows[path][method]=r.status;r.close()
   except Exception:rows[path][method]=0
 return rows

def coordinate(server,operation,plan_id='',snapshot=health.snapshot,probe=protection_probe):
 report={'operation':operation,'plan_id':plan_id,'result':'failed','automatic_release_enabled':False}
 if operation in ['inspect','prepare','status']:
  try:report['server']=server.rpc(operation,plan_id);report['result']={'inspect':'inspected','prepare':'prepared','status':'status_verified'}[operation]
  except RemoteFailure:report['error']='server_operation_failed'
  return report
 if operation=='rollback':
  try:report['server']=server.rpc('rollback',plan_id);report['after_rollback']=snapshot();report['result']='rollback_bytes_restored';report['healthy']=report['after_rollback']['ok']
  except RemoteFailure:report['error']='rollback_requires_attention'
  return report
 report['before']=snapshot()
 try:
  report['server']=server.rpc('apply',plan_id)
  after=snapshot();report['after']=after;protected=probe(plan_id);report['protection']=protected
  assets_unchanged=all(after['checks'].get(path,{}).get('sha256')==before.get('sha256') for path,before in report['before']['checks'].items() if path in health.ASSET_PATHS)
  ok=after['ok'] and after['complete'] and assets_unchanged and all(status in [403,404] for row in protected.values() for status in row.values())
  if not ok:raise RemoteFailure('post_repair_health_failed')
  report['confirmed']=server.rpc('confirm',plan_id,{'plan_id':plan_id,'ok':True,'health':after,'protection':protected})
  report['final_health']=snapshot()
  report['result']='repaired_and_verified' if report['final_health']['ok'] else 'failed'
  if report['result']=='failed':report['error']='confirmed_repair_health_changed'
 except RemoteFailure:
  report['error']='repair_or_verification_failed'
  try:report['rollback']=server.rpc('rollback',plan_id);report['after_rollback']=snapshot();report['rollback_bytes_verified']=report['rollback'].get('bytes_restored') is True
  except RemoteFailure:report['rollback_error']='rollback_requires_attention'
 return report

if __name__=='__main__':
 parser=argparse.ArgumentParser();parser.add_argument('--operation',choices=['inspect','prepare','apply','rollback','status'],default='inspect');parser.add_argument('--plan-id',default='');parser.add_argument('--revision',required=True);parser.add_argument('--report',type=Path,required=True);args=parser.parse_args()
 report={'result':'failed','error':'repair_client_failed'};server=None
 try:
  if not re.fullmatch('[a-f0-9]{40}',args.revision):raise ValueError('invalid_revision')
  if args.operation!='inspect' and not re.fullmatch('[a-z0-9][a-z0-9-]{0,79}',args.plan_id):raise ValueError('invalid_plan')
  server=ServerRepair(args.revision,args.plan_id);report=coordinate(server,args.operation,args.plan_id)
 except Exception:pass
 finally:
  if server:server.close()
  args.report.write_text(json.dumps(report,indent=2));print(json.dumps({'result':report.get('result'),'plan_id':args.plan_id}))
 raise SystemExit(0 if report['result'] in ['inspected','prepared','status_verified','repaired_and_verified','rollback_bytes_restored'] else 1)
