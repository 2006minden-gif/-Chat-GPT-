"""Trusted GitHub-hosted control relay. No hosting secrets, production writes or review bypass."""
import base64
import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request

REPO='2006minden-gif/-Chat-GPT-'
API='https://api.github.com/'
class Gateway:
 def __init__(self):self.token=os.environ['GH_TOKEN']
 def call(self,method,path,data=None):
  request=urllib.request.Request(API+path,method=method,data=json.dumps(data).encode() if data is not None else None,
   headers={'Authorization':'Bearer '+self.token,'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'})
  try:
   with urllib.request.urlopen(request,timeout=40) as response:
    body=response.read();return {'status':response.status,'data':json.loads(body) if body else None}
  except urllib.error.HTTPError as error:
   body=error.read(16384)
   try:message=json.loads(body).get('message','')
   except ValueError:message=''
   # API errors contain no request headers or secret values; retain only known diagnostics.
   allowed=['Resource not accessible by integration','GitHub Actions is not permitted to create or approve pull requests.','Not Found','Bad credentials','Upgrade to GitHub Pro or make this repository public to enable this feature.']
   return {'status':error.code,'error':message if message in allowed else 'github_request_rejected'}

 def inspect(self):
  base='repos/'+REPO;result={}
  repo=self.call('GET',base)
  result['repository']={k:repo.get('data',{}).get(k) for k in ['full_name','private','permissions','default_branch','allow_auto_merge','allow_squash_merge','allow_merge_commit']}
  result['repository']['http_status']=repo['status']
  for name,path in [('protection','branches/main/protection'),('rules','rules/branches/main'),('workflow_permissions','actions/permissions/workflow'),('variables','actions/variables'),('environments','environments')]:
   response=self.call('GET',base+'/'+path)
   if name=='variables' and response.get('data'):
    response['data']={'variables':[{'name':v['name'],'value':v['value'] if v['name'] in ['AUTOMATION_READY','AUTOMERGE_ENABLED','DEPLOY_PAUSED','AUTOMERGE_APP_ID'] else '<not-exported>'} for v in response['data'].get('variables',[])]}
   result[name]=response
  prs=self.call('GET',base+'/pulls?state=open&per_page=30')
  result['open_prs']={'status':prs['status'],'pulls':[{k:p.get(k) for k in ['number','title','state','draft','html_url','merge_commit_sha']}|{'head':{'ref':p['head']['ref'],'sha':p['head']['sha']},'base':{'ref':p['base']['ref'],'sha':p['base']['sha']}} for p in prs.get('data',[])] if isinstance(prs.get('data'),list) else []}
  result['stage3']={}
  for name,path in [('pr','pulls/4'),('reviews','pulls/4/reviews?per_page=100')]:
   response=self.call('GET',base+'/'+path)
   if name=='pr' and response.get('data'):
    p=response['data'];response['data']={k:p.get(k) for k in ['number','title','state','draft','merged','mergeable','mergeable_state','auto_merge','merge_commit_sha','html_url']}|{'head':{'ref':p['head']['ref'],'sha':p['head']['sha']},'base':{'ref':p['base']['ref'],'sha':p['base']['sha']}}
   elif name=='reviews' and isinstance(response.get('data'),list):response['data']=[{'user':r['user']['login'],'state':r['state'],'commit_id':r['commit_id'],'submitted_at':r.get('submitted_at')} for r in response['data']]
   result['stage3'][name]=response
  runs=self.call('GET',base+'/actions/runs?per_page=15')
  result['runs']={'status':runs['status'],'runs':[]}
  for run in runs.get('data',{}).get('workflow_runs',[]):
   safe={k:run.get(k) for k in ['id','name','event','head_branch','head_sha','status','conclusion','html_url','path']}
   jobs=self.call('GET',base+'/actions/runs/'+str(run['id'])+'/jobs?per_page=30')
   safe['jobs']=[{'id':j['id'],'name':j['name'],'status':j['status'],'conclusion':j['conclusion'],'steps':[{'name':s['name'],'conclusion':s.get('conclusion'),'status':s['status']} for s in j.get('steps',[])]} for j in jobs.get('data',{}).get('jobs',[])]
   if run.get('head_branch') in ['ci/automatic-spaceweb','verify/stage3-integration'] and run.get('conclusion')=='failure':
    for job in safe['jobs']:
     if job['name']=='Validate' and job['conclusion']=='failure':job['diagnostics']=self.validation_errors(job['id'])
   result['runs']['runs'].append(safe)
  return result
 def validation_errors(self,job_id):
  # This job has synthetic loopback DB only and no production secrets.
  request=urllib.request.Request(API+'repos/'+REPO+'/actions/jobs/'+str(job_id)+'/logs',headers={'Authorization':'Bearer '+self.token})
  try:
   # Strip Authorization on cross-origin download redirects.
   class Redirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,request,fp,code,msg,headers,newurl):
     target=super().redirect_request(request,fp,code,msg,headers,newurl)
     if target and urllib.parse.urlparse(request.full_url).netloc!=urllib.parse.urlparse(newurl).netloc:target.remove_header('Authorization')
     return target
   with urllib.request.build_opener(Redirect()).open(request,timeout=40) as response:text=response.read(4000000).decode('utf-8','replace')
   # Only recognized test/CI failure windows, never arbitrary job/environment dumps.
   lines=text.splitlines();out=[]
   for index,line in enumerate(lines):
    if any(marker in line for marker in ['FAIL:', 'ERROR:', 'AssertionError:', 'ModuleNotFoundError:', 'RuntimeError:', 'FAILED (','No matching distribution']):
     window=lines[max(0,index-2):min(len(lines),index+7)]
     out.extend(window)
   safe=[]
   for line in list(dict.fromkeys(out))[:120]:
    line=line.replace(self.token,'<redacted>')
    line=re.sub(r'(gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)','<redacted>',line)
    safe.append(line[:500])
   return {'errors':safe}
  except Exception as error:return {'error_type':type(error).__name__}
 def prepare_pr(self):
  base='repos/'+REPO;head='ci/automatic-spaceweb'
  existing=self.call('GET',base+'/pulls?state=open&base=main&head='+urllib.parse.quote('2006minden-gif:'+head,safe=''))
  if existing.get('data'):
   p=existing['data'][0];return {'status':200,'number':p['number'],'html_url':p['html_url'],'created':False}
  response=self.call('POST',base+'/pulls',{'head':head,'base':'main','title':'Automate approved NeuroDelo releases with CI and verified recovery',
   'body':'Prepared via authorized GitHub Actions control relay. Local CI/CD tests and recovery checks are documented in docs/CICD-REPORT.md. No main merge, production publication or migration 004 is authorized by PR creation alone. Existing review and check requirements must pass.'})
  if response.get('data'):response['data']={k:response['data'][k] for k in ['number','html_url','state','draft']}
  return response

def publish(report):
 # The evidence ref is a separate managed namespace. Never write/force main or trigger production.
 ref='automation/evidence';url='https://github.com/'+REPO+'.git'
 with tempfile.TemporaryDirectory() as tmp:
  root=Path(tmp);work=root/'repo';work.mkdir();ask=root/'askpass'
  ask.write_text('#!/usr/bin/env python3\nimport os,sys\nprint("x-access-token" if "Username" in sys.argv[1] else os.environ["GH_TOKEN"])\n');ask.chmod(0o700)
  env=dict(os.environ,GIT_ASKPASS=str(ask),GIT_TERMINAL_PROMPT='0')
  def git(*args,check=True):return subprocess.run(['git',*args],cwd=work,env=env,text=True,capture_output=True,check=check)
  git('init','-q');git('remote','add','origin',url)
  found=git('ls-remote','--heads','origin','refs/heads/'+ref)
  if found.stdout.strip():git('fetch','--depth=1','origin','refs/heads/'+ref);git('checkout','-b','evidence','FETCH_HEAD')
  else:git('checkout','--orphan','evidence')
  git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
  name=os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')+'.json'
  (work/'runs').mkdir(exist_ok=True);text=json.dumps(report,ensure_ascii=False,indent=2)
  (work/'runs'/name).write_text(text);(work/'latest.json').write_text(text)
  git('add','runs/'+name,'latest.json');git('commit','-m','Record authorized GitHub control evidence')
  git('push','origin','HEAD:refs/heads/'+ref)

if __name__=='__main__':
 plan=json.loads(Path('.github/control-plan.json').read_text());gateway=Gateway()
 report={'schema_version':1,'nonce':plan['nonce'],'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
  'run_url':'https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'production_touched':False}
 try:
  report['inspection']=gateway.inspect()
  if plan['action']=='prepare-ci-pr':report['prepare_pr']=gateway.prepare_pr()
  elif plan['action'] not in ['inspect','readonly-host']:raise ValueError('unsupported_control_action')
 except Exception as error:report['error_type']=type(error).__name__
 publish(report)
 print('Evidence published to automation/evidence; no production operation executed')
