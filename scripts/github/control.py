"""GitHub governance helpers. Uses an existing secure gh login/GH_TOKEN; never reads secret values."""
import argparse
import json
import os
from pathlib import Path
import re
from urllib.parse import quote
import subprocess

REPO='2006minden-gif/-Chat-GPT-'
REQUIRED_CHECK='Validate'
class GitHubFailure(RuntimeError): pass

def api(method, path, payload=None, missing=False):
    command=['gh','api',path,'--method',method,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2022-11-28']
    if payload is not None:command+=['--input','-']
    r=subprocess.run(command,input=json.dumps(payload) if payload is not None else None,capture_output=True,text=True,timeout=45)
    if r.returncode:
        if missing and '(HTTP 404)' in r.stderr:return None
        raise GitHubFailure('GitHub API access failed: '+method+' '+path)
    return json.loads(r.stdout) if r.stdout.strip() else None

def pages(path, field=None):
    values=[];page=1
    while True:
        part=api('GET',path+('&' if '?' in path else '?')+'per_page=100&page='+str(page))
        if field:part=part[field]
        values.extend(part)
        if len(part)<100:return values
        page+=1

def protection_payload(old):
    old=old or {};status=old.get('required_status_checks') or {}
    checks=[{'context':c['context'],'app_id':c.get('app_id',-1)} for c in status.get('checks',[])]
    names={c['context'] for c in checks}
    for context in status.get('contexts',[]):
        if context not in names:checks.append({'context':context,'app_id':-1});names.add(context)
    checks=[c for c in checks if c['context']!=REQUIRED_CHECK]+[{'context':REQUIRED_CHECK,'app_id':15368}]
    review=old.get('required_pull_request_reviews') or {}
    reviews={key:value for key,value in review.items() if key in ['require_code_owner_reviews','require_last_push_approval']}
    reviews.update(dismiss_stale_reviews=True,required_approving_review_count=max(1,review.get('required_approving_review_count',0)))
    for key in ['dismissal_restrictions','bypass_pull_request_allowances']:
        if key in review:
            reviews[key]={'users':[u['login'] for u in review[key].get('users',[])], 'teams':[t['slug'] for t in review[key].get('teams',[])], 'apps':[a['slug'] for a in review[key].get('apps',[])]}
    reviews['bypass_pull_request_allowances']={'users':[],'teams':[],'apps':[]}
    restrictions=old.get('restrictions')
    if restrictions:restrictions={'users':[u['login'] for u in restrictions.get('users',[])],'teams':[t['slug'] for t in restrictions.get('teams',[])],'apps':[a['slug'] for a in restrictions.get('apps',[])]}
    payload={'required_status_checks':{'strict':True,'checks':checks},'enforce_admins':True,'required_pull_request_reviews':reviews,
             'restrictions':restrictions,'allow_force_pushes':False,'allow_deletions':False,'required_conversation_resolution':True}
    for key in ['required_linear_history','block_creations','lock_branch','allow_fork_syncing']:
        if key in old:payload[key]=old[key].get('enabled',False)
    if old.get('required_deployments',{}).get('environments'):
        raise GitHubFailure('Existing required deployments need reviewed rule reconciliation; not modified')
    return payload

def bootstrap():
    repo=api('GET','repos/'+REPO)
    if repo.get('full_name')!=REPO or not repo.get('permissions',{}).get('admin'):raise GitHubFailure('Repository administrator access required')
    base='repos/'+REPO
    old=api('GET',base+'/branches/main/protection',missing=True)
    payload=protection_payload(old)
    # Fail closed while the one-time settings are being applied.
    def variable(name,value):
        current=api('GET',base+'/actions/variables/'+name,missing=True)
        api('PATCH' if current else 'POST',base+'/actions/variables/'+name if current else base+'/actions/variables',{'name':name,'value':value})
    variable('AUTOMATION_READY','false')
    for environment in ['production','automation']:
        endpoint=base+'/environments/'+environment
        api('PUT',endpoint,{'wait_timer':0,'reviewers':[],'deployment_branch_policy':{'protected_branches':False,'custom_branch_policies':True}})
        policies=api('GET',endpoint+'/deployment-branch-policies')['branch_policies']
        for policy in policies:
            if policy['name']!='main' or policy.get('type','branch')!='branch':api('DELETE',endpoint+'/deployment-branch-policies/'+str(policy['id']))
        if not any(p['name']=='main' and p.get('type','branch')=='branch' for p in policies):api('POST',endpoint+'/deployment-branch-policies',{'name':'main','type':'branch'})
    api('PUT',base+'/branches/main/protection',payload)
    api('PATCH',base,{'allow_auto_merge':True})
    # Names/metadata only. Existing secret values are neither retrieved nor overwritten.
    secretsBase='repositories/'+str(repo['id'])+'/environments'
    production={v['name'] for v in api('GET',secretsBase+'/production/secrets')['secrets']}
    expected={'SSH_HOST','SSH_PORT','SSH_USER','DEPLOY_PATH','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS'}
    if not expected<=production:raise GitHubFailure('Missing environment-scoped production secret names: '+','.join(sorted(expected-production)))
    repository_secrets={v['name'] for v in api('GET',base+'/actions/secrets')['secrets']}
    if 'SSH_PRIVATE_KEY' in repository_secrets:raise GitHubFailure('After secure environment transfer, remove the legacy repository-scoped SSH_PRIVATE_KEY; no secret was deleted by this script')
    automation={v['name'] for v in api('GET',secretsBase+'/automation/secrets')['secrets']}
    if 'AUTOMERGE_APP_PRIVATE_KEY' not in automation:raise GitHubFailure('Missing automation environment AUTOMERGE_APP_PRIVATE_KEY')
    app=api('GET',base+'/actions/variables/AUTOMERGE_APP_ID',missing=True)
    if not app or not app.get('value','').isdigit():raise GitHubFailure('Set repository variable AUTOMERGE_APP_ID')
    verify_protection(api('GET',base+'/branches/main/protection'))
    variable('AUTOMERGE_ENABLED','true');variable('AUTOMATION_READY','true')
    print('Repository gates configured; real CI/deployment verification still required')

def verify_protection(protection):
    reviews=protection.get('required_pull_request_reviews') or {}
    checks=protection.get('required_status_checks') or {}
    if not (protection.get('enforce_admins',{}).get('enabled') and reviews.get('required_approving_review_count',0)>=1 and reviews.get('dismiss_stale_reviews') and checks.get('strict')):
        raise GitHubFailure('Main review/check protection is not configured')
    if not any(c['context']==REQUIRED_CHECK and c.get('app_id')==15368 for c in checks.get('checks',[])):
        raise GitHubFailure('Required GitHub Actions Validate check is missing')
    return reviews['required_approving_review_count'], [c['context'] for c in checks.get('checks',[])]

def eligible(pr,reviews,checks,statuses,permissions,required_count,required_checks):
    if pr['draft'] or pr.get('merged') or pr['base']['ref']!='main' or pr['head']['repo'] is None or pr['head']['repo']['full_name']!=REPO:return False
    latest={}
    for review in reviews:
        if review['state'] in ['APPROVED','CHANGES_REQUESTED','DISMISSED']:latest[review['user']['login']]=review
    valid=[r for user,r in latest.items() if user!=pr['user']['login'] and permissions.get(user) in ['admin','maintain','write']]
    if any(r['state']=='CHANGES_REQUESTED' for r in valid):return False
    if sum(r['state']=='APPROVED' and r['commit_id']==pr['head']['sha'] for r in valid)<required_count:return False
    passed=set()
    for check in checks:
        if check['head_sha']!=pr.get('checked_sha',pr['head']['sha']):continue
        if check['status']!='completed' or check['conclusion'] not in ['success','neutral','skipped']:return False
        if check['conclusion']=='success' and (check['name']!=REQUIRED_CHECK or check['app']['id']==15368):passed.add(check['name'])
    for status in statuses:
        if status['state']!='success':return False
        passed.add(status['context'])
    return set(required_checks)<=passed

def ensure_pr_for_validated_branch():
    # workflow_run is defined on trusted main. No branch artifact or source is executed here.
    event_path=os.environ.get('GITHUB_EVENT_PATH')
    if os.environ.get('GITHUB_EVENT_NAME')!='workflow_run' or not event_path:return
    event=json.loads(Path(event_path).read_text());run=event.get('workflow_run',{})
    branch=run.get('head_branch','');sha=run.get('head_sha','')
    if run.get('event')!='push' or run.get('conclusion')!='success' or branch=='main' or run.get('head_repository',{}).get('full_name')!=REPO:return
    if not branch or not re.fullmatch('[a-f0-9]{40}',sha):raise GitHubFailure('Invalid validated branch identity')
    base='repos/'+REPO
    checked=api('GET',base+'/actions/runs/'+str(int(run['id'])))
    if checked['head_sha']!=sha or checked['conclusion']!='success' or checked['path']!='.github/workflows/deploy.yml':raise GitHubFailure('Untrusted workflow identity')
    current=api('GET',base+'/git/ref/heads/'+quote(branch,safe=''))
    if current['object']['sha']!=sha:return
    existing=api('GET',base+'/pulls?state=open&base=main&head='+quote(REPO.split('/')[0]+':'+branch,safe=''))
    if existing:return
    comparison=api('GET',base+'/compare/main...'+sha)
    if comparison.get('ahead_by',0)==0:return
    api('POST',base+'/pulls',{'head':branch,'base':'main','title':'NeuroDelo: '+branch,
        'draft':branch.startswith(('draft/','wip/')),
        'body':'Created automatically after Validate passed for '+sha+'. Independent review is required before auto-merge. No deployment from this branch.'})
    print('Created review PR for validated branch',branch)

def auto_merge():
    base='repos/'+REPO;repo=api('GET',base)
    if not repo.get('allow_auto_merge'):raise GitHubFailure('Repository auto-merge is disabled')
    protection=api('GET',base+'/branches/main/protection');count,required=verify_protection(protection)
    ensure_pr_for_validated_branch()
    for pr in pages(base+'/pulls?state=open&base=main'):
        if pr['draft'] or pr['head']['repo'] is None or pr['head']['repo']['full_name']!=REPO:continue
        number=pr['number'];pr=api('GET',base+'/pulls/'+str(number))
        if pr.get('mergeable') is False:continue
        head=pr['head']['sha'];reviews=pages(base+'/pulls/'+str(number)+'/reviews')
        permissions={}
        for reviewer in {r['user']['login'] for r in reviews}:
            permission=api('GET',base+'/collaborators/'+reviewer+'/permission',missing=True)
            permissions[reviewer]=permission['permission'] if permission else 'none'
        checked=head
        merge=pr.get('merge_commit_sha')
        if merge:
            commit=api('GET',base+'/git/commits/'+merge)
            if {p['sha'] for p in commit['parents']}=={head,pr['base']['sha']}:
                merge_checks=pages(base+'/commits/'+merge+'/check-runs?filter=latest','check_runs')
                if any(c['name']==REQUIRED_CHECK for c in merge_checks):checked=merge
        pr['checked_sha']=checked
        checks=pages(base+'/commits/'+checked+'/check-runs?filter=latest','check_runs')
        statuses=pages(base+'/commits/'+checked+'/status','statuses')
        if not eligible(pr,reviews,checks,statuses,permissions,count,required):continue
        method='--squash' if repo.get('allow_squash_merge') else '--rebase' if repo.get('allow_rebase_merge') else '--merge'
        if method=='--merge' and protection.get('required_linear_history',{}).get('enabled'):raise GitHubFailure('No allowed linear merge method')
        r=subprocess.run(['gh','pr','merge',str(number),'--repo',REPO,'--auto',method,'--match-head-commit',head],capture_output=True,text=True,timeout=45)
        if r.returncode:raise GitHubFailure('Could not enable auto-merge for PR '+str(number))
        print('Auto-merge prepared for approved, passing PR',number)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['bootstrap','auto-merge']);parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    try:
        if args.operation=='bootstrap':
            if not args.apply:print(json.dumps({'repository':REPO,'required_check':REQUIRED_CHECK,'reviews':1,'environments':['production','automation'],'branch':'main','note':'Use --apply with administrator gh authentication. No secrets are read or changed.'},indent=2))
            else:bootstrap()
        else:auto_merge()
    except (GitHubFailure,subprocess.TimeoutExpired) as error:
        print(str(error));raise SystemExit(1)
