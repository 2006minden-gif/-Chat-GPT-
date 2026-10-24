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


 def prepare_customer_pr(self,expected_sha):
  base='repos/'+REPO;head='feature/stage-4-customer-auth'
  current=self.call('GET',base+'/git/ref/heads/'+urllib.parse.quote(head,safe=''))
  if current['status']!=200 or current.get('data',{}).get('object',{}).get('sha')!=expected_sha:
   return {'status':409,'error':'stage4_head_changed'}
  body=('Stage 4 customer registration and authentication. Depends on Stage 3 PR #4; do not merge before #4 and verified release pipeline. '
        'Preserves main CI/CD; migrations 004 and 005 execution flags remain false. No production deployment or data collection enabled. '
        'Isolated PHP 8.4 / MySQL 5.7 validation: 127 Python tests and 12 Node tests passed. '
        'See docs/STAGE-4-REPORT.md and docs/CUSTOMER-AUTH.md. Genuine independent review, SMTP staging and legal review are required.')
  existing=self.call('GET',base+'/pulls?state=open&base=main&head='+urllib.parse.quote('2006minden-gif:'+head,safe=''))
  if existing['status']!=200:return {'status':existing['status'],'error':'pr_lookup_unavailable'}
  if existing.get('data'):
   p=existing['data'][0]
   if not p.get('draft'):
    r=self.call('POST','graphql',{'query':'mutation($id:ID!){convertPullRequestToDraft(input:{pullRequestId:$id}){pullRequest{number isDraft}}}','variables':{'id':p['node_id']}})
    if r['status']!=200 or r.get('data',{}).get('errors'):return {'status':409,'error':'draft_conversion_unavailable'}
   response=self.call('PATCH',base+'/pulls/'+str(p['number']),{'title':'Stage 4: customer authentication (depends on #4)','body':body})
  else:response=self.call('POST',base+'/pulls',{'head':head,'base':'main','draft':True,'title':'Stage 4: customer authentication (depends on #4)','body':body})
  if response.get('data'):response['data']={k:response['data'].get(k) for k in ['number','html_url','state','draft']}
  return response



 def prepare_issue8_pr(self,expected_sha):
  base='repos/'+REPO;head='fix/issue-8-cicd-bootstrap'
  current=self.call('GET',base+'/git/ref/heads/'+urllib.parse.quote(head,safe=''))
  if current['status']!=200 or current.get('data',{}).get('object',{}).get('sha')!=expected_sha:return {'status':409,'error':'fix_head_changed'}
  body=('Refs #8. Separate fix from main; Stage 3 #4 and Stage 4 #7 remain drafts and unchanged. '
        'Accepts existing repo/environment SSH secret union; does not change protection or secrets; keeps READY false until proven bootstrap. '
        'SHA-bound native dispatch, manual-only administrative workflow, actual backup/recovery/hash proof and tested promotion gate. '
        '77 isolated Python tests and 12 Node tests passed locally. Production deployment has NOT occurred. '
        'Read-only SpaceWeb probe confirms PHP 8.4.27, valid SSH, and a pre-existing ParseError in private/config.php line 12; health remains red. '
        'Owner admin access/review and production repairs are still required. See docs/CICD-BOOTSTRAP-ISSUE-8.md. '
        'Do not close issue #8 or merge dependent stages merely because CI is green.')
  existing=self.call('GET',base+'/pulls?state=open&base=main&head='+urllib.parse.quote('2006minden-gif:'+head,safe=''))
  if existing['status']!=200:return {'status':existing['status'],'error':'pr_lookup_unavailable'}
  if existing.get('data'):
   p=existing['data'][0];return {'status':200,'data':{k:p.get(k) for k in ['number','html_url','state','draft']}}
  r=self.call('POST',base+'/pulls',{'head':head,'base':'main','draft':True,'title':'Fix #8: fail-closed CI/CD bootstrap and verified SHA-bound delivery','body':body})
  if r.get('data'):r['data']={k:r['data'].get(k) for k in ['number','html_url','state','draft']}
  return r


 def prepare_stage5_pr(self,expected_sha):
  base='repos/'+REPO;head='feature/stage-5-crm-operations'
  current=self.call('GET',base+'/git/ref/heads/'+urllib.parse.quote(head,safe=''))
  if current['status']!=200 or current.get('data',{}).get('object',{}).get('sha')!=expected_sha:return {'status':409,'error':'stage5_head_changed'}
  existing=self.call('GET',base+'/pulls?state=open&base=main&head='+urllib.parse.quote('2006minden-gif:'+head,safe=''))
  if existing.get('data'):
   p=existing['data'][0];return {'status':200,'number':p['number'],'html_url':p['html_url'],'created':False,'draft':p['draft']}
  body="""Implement the gated owner CRM and customer project portal on the Stage 3/4 dependency chain. Real SQL dashboard, customers and explicit lead links, sales pipeline with confirmed idempotent order conversion, orders/projects/milestones/tasks/employees, activity/notifications, and customer-scoped read projections.

Depends on #4 and #7; their commits are included only in this development branch. Do not merge into automatically publishing main until those dependencies, migrations, legal gates and a complete release manifest are separately approved. Production workflows and scripts/deploy remain identical to the starting main. No production writes, migrations, config/secret changes or signup activation.

Validation: 186 Python integration/security/migration/browser tests and 12 Node tests passed locally using isolated PHP 8.4/MySQL 5.7/Apache/Chromium. Migration 006 empty rollback and legacy preservation tested; populated or partial rollback refused. Hosted CI must pass for the final head as well.

See docs/STAGE-5-REPORT.md, docs/STAGE-5-ARCHITECTURE.md and docs/STAGE-5-UX.md for API contracts, actual tests, synthetic screenshots and deployment blockers. Current production allowlist intentionally does not ship the new CRM files; this draft is for development review, not release authorization."""
  response=self.call('POST',base+'/pulls',{'head':head,'base':'main','draft':True,'title':'Stage 5: gated owner CRM and customer project management','body':body})
  if response.get('data'):response['data']={k:response['data'][k] for k in ['number','html_url','state','draft']}
  return response

 def prepare_issue10_pr(self,expected_sha):
  base='repos/'+REPO;head='fix/issue-10-production-repair'
  current=self.call('GET',base+'/git/ref/heads/'+urllib.parse.quote(head,safe=''))
  if current['status']!=200 or current.get('data',{}).get('object',{}).get('sha')!=expected_sha:return {'status':409,'error':'repair_head_changed'}
  body=('Refs #10. Separate reviewed repair path from main; no Stage 3/4 or migrations. '
        'Read-only server diagnosis confirms ParseError line 12 from two unescaped existing apostrophes; a native syntax-valid candidate preserves declared value bytes. '
        'Actual GET and HEAD expose both backup URLs with 200. No production repair was applied. '
        'Adds server-local verified backup/recovery, restricted literal/escape repair, private quarantine, atomic writes, real GET+HEAD/HTTP confirmation and rollback. '
        'Manual repair job is main-only after full existing CI, with exact revision and prepared-plan checks; no automatic release enabled. '
        '87 Python and 12 Node tests passed locally, actual Apache and isolated MySQL 5.7 included. '
        'See docs/PRODUCTION-REPAIR-ISSUE-10.md. Review and controlled prepare/apply are required; do not close #10 until production baseline is genuinely healthy.')
  existing=self.call('GET',base+'/pulls?state=open&base=main&head='+urllib.parse.quote('2006minden-gif:'+head,safe=''))
  if existing['status']!=200:return {'status':existing['status'],'error':'repair_pr_lookup_failed'}
  if existing.get('data'):
   r={'status':200,'data':existing['data'][0]}
  else:r=self.call('POST',base+'/pulls',{'head':head,'base':'main','draft':False,'title':'Issue #10: secret-preserving production syntax repair and backup protection','body':body})
  if r.get('data'):r['data']={k:r['data'].get(k) for k in ['number','html_url','state','draft']}
  return r

 def issue8_audit(self):
  # Execute gh in the authorized Actions environment. All output selected below is metadata only.
  def gh(path,query=None):
   command=['gh','api',path]
   if query:command+=['--method','POST','--input','-']
   r=subprocess.run(command,input=json.dumps({'query':query}) if query else None,text=True,capture_output=True,timeout=45)
   if r.returncode:
    status=re.search(r'HTTP (\d+)',r.stderr)
    detail={'status':int(status.group(1)) if status else None,'available':False}
    if query:
     try:detail['graphql_errors']=[e.get('message','')[:250] for e in json.loads(r.stdout).get('errors',[])]
     except ValueError:pass
    return detail
   try:return {'status':200,'available':True,'data':json.loads(r.stdout)}
   except ValueError:return {'status':200,'available':False}
  base='repos/'+REPO;result={}
  for label,path in [('protection',base+'/branches/main/protection'),('rules',base+'/rules/branches/main'),('repository_secrets',base+'/actions/secrets'),('variables',base+'/actions/variables'),('workflow_permissions',base+'/actions/permissions/workflow')]:
   result[label]=gh(path)
   if label=='variables' and result[label].get('data'):
    result[label]['data']={'variables':[{'name':v['name'],'value':v['value'] if v['name'] in ['AUTOMATION_READY','AUTOMERGE_ENABLED','DEPLOY_PAUSED','PHP_CLI','BOOTSTRAP_APPROVED_SHA'] else '<not-exported>'} for v in result[label]['data'].get('variables',[])]}
  result['environments']={}
  repo=self.call('GET',base).get('data',{})
  for env in ['production','automation']:
   result['environments'][env]={'configuration':gh(base+'/environments/'+env),'branches':gh(base+'/environments/'+env+'/deployment-branch-policies'),'secret_names':gh('repositories/'+str(repo.get('id'))+'/environments/'+env+'/secrets')}
  query='query{repository(owner:"2006minden-gif",name:"-Chat-GPT-"){ref(qualifiedName:"refs/heads/main"){target{oid} branchProtectionRule{pattern isAdminEnforced requiresApprovingReviews requiredApprovingReviewCount dismissesStaleReviews requiresStrictStatusChecks requiresStatusChecks requiredStatusCheckContexts requiredStatusChecks{context app{databaseId}} allowsForcePushes allowsDeletions requiresConversationResolution requiresCodeOwnerReviews requiresLinearHistory}}}}'
  result['graphql_main_protection']=gh('graphql',query)
  return result

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
  git('config','user.name','github-actions[bot]');git('config','user.email','41898282+github-actions[bot]@users.noreply.github.com')
  name=os.environ['GITHUB_RUN_ID']+'-'+os.environ.get('GITHUB_RUN_ATTEMPT','1')+'.json';text=json.dumps(report,ensure_ascii=False,indent=2)
  for attempt in range(5):
   found=git('ls-remote','--heads','origin','refs/heads/'+ref)
   if found.stdout.strip():git('fetch','--depth=1','origin','refs/heads/'+ref);git('checkout','-B','evidence','FETCH_HEAD')
   else:git('checkout','--orphan','evidence')
   (work/'runs').mkdir(exist_ok=True);(work/'runs'/name).write_text(text);(work/'latest.json').write_text(text)
   git('add','runs/'+name,'latest.json');committed=git('commit','-m','Record authorized GitHub control evidence',check=False)
   pushed=git('push','origin','HEAD:refs/heads/'+ref,check=False)
   if pushed.returncode==0:break
  else:raise RuntimeError('evidence_publish_conflict')

if __name__=='__main__':
 plan=json.loads(Path('.github/control-plan.json').read_text());gateway=Gateway()
 report={'schema_version':1,'nonce':plan['nonce'],'source_sha':os.environ['GITHUB_SHA'],'run_id':os.environ['GITHUB_RUN_ID'],
  'run_url':'https://github.com/'+REPO+'/actions/runs/'+os.environ['GITHUB_RUN_ID'],'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'production_touched':False}
 try:
  report['inspection']=gateway.inspect()
  if plan['action']=='prepare-stage5-pr':report['stage5_pr']=gateway.prepare_stage5_pr(plan['expected_sha'])
  elif plan['action']=='prepare-issue10-pr':report['issue10_pr']=gateway.prepare_issue10_pr(plan['expected_sha'])
  elif plan['action']=='prepare-issue8-pr':report['issue8_pr']=gateway.prepare_issue8_pr(plan['expected_sha'])
  elif plan['action']=='audit-issue8':report['issue8_audit']=gateway.issue8_audit()
  elif plan['action']=='prepare-ci-pr':report['prepare_pr']=gateway.prepare_pr()
  elif plan['action']=='prepare-stage4-pr':report['stage4_pr']=gateway.prepare_customer_pr(plan['expected_sha'])
  elif plan['action'] not in ['inspect','readonly-host','inspect-issue10']:raise ValueError('unsupported_control_action')
 except Exception as error:report['error_type']=type(error).__name__
 publish(report)
 print('Evidence published to automation/evidence; no production operation executed')
