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

def safe_api_probe(token):
    """Read-only fallback diagnosis; never expose token, response body or proxy URLs."""
    if not token:
        return 'missing_token'
    import urllib.request
    import urllib.error
    request=urllib.request.Request(
        'https://api.github.com/repos/'+REPO,
        headers={'Authorization':'Bearer '+token,
                 'Accept':'application/vnd.github+json',
                 'User-Agent':'NeuroDelo-bootstrap-diagnostic'},
        method='GET')
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, request, fp, code, msg, headers, newurl):
            return None
    try:
        # A token must never follow a redirect, even to another GitHub hostname.
        with urllib.request.build_opener(NoRedirect()).open(request,timeout=12) as response:
            return 'direct_http_'+str(response.status)
    except urllib.error.HTTPError as error:
        return 'direct_http_'+str(error.code)
    except urllib.error.URLError:
        return 'direct_transport_failure'
    except ValueError:
        return 'direct_invalid_request_or_header'
    except OSError:
        return 'direct_connection_failure'

def api(method, path, payload=None, missing=False):
    command=['gh','api',path,'--method',method,'-H','Accept: application/vnd.github+json','-H','X-GitHub-Api-Version: 2022-11-28']
    if payload is not None:command+=['--input','-']
    runenv=None
    if method=='POST' and path=='repos/'+REPO+'/actions/workflows/deploy.yml/dispatches' and os.environ.get('GITHUB_DISPATCH_TOKEN'):
        runenv=dict(os.environ,GH_TOKEN=os.environ['GITHUB_DISPATCH_TOKEN'])
    # Pasted GitHub Actions secrets may contain leading/trailing whitespace/newlines.
    # Normalize a local copy before invoking gh; never print or persist the token.
    if runenv is None:
        runenv=dict(os.environ)
    if 'GH_TOKEN' in runenv:
        runenv['GH_TOKEN']=runenv['GH_TOKEN'].strip()
    r=subprocess.run(command,input=json.dumps(payload) if payload is not None else None,capture_output=True,text=True,timeout=45,env=runenv)
    if r.returncode:
        # Never expose gh stderr/headers: they can contain URLs, tokens or sensitive context.
        # Surface only a bounded HTTP code and a predetermined failure category.
        match=re.search(r'\bHTTP\s+(401|403|404|422|429)\b',r.stderr or '')
        status=match.group(1) if match else None
        if missing and status=='404':return None
        category={'401':'invalid_or_expired_token','403':'insufficient_permissions_or_policy','404':'not_found_or_not_authorized','422':'invalid_request','429':'rate_limited'}.get(status,'transport_or_unclassified_failure')
        token=(runenv or os.environ).get('GH_TOKEN') or (runenv or os.environ).get('GITHUB_TOKEN')
        probe=safe_api_probe(token) if status is None else 'not_needed'
        raise GitHubFailure('GitHub API access failed: '+method+' '+path.split('?',1)[0]+' [HTTP '+(status or 'unknown')+', '+category+', safe_probe='+probe+']')
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

def set_variable(base,name,value):
    current=api('GET',base+'/actions/variables/'+name,missing=True)
    # GitHub rejects empty variable values. Removing a temporary grant clears it.
    if value == '':
        if current:
            api('DELETE',base+'/actions/variables/'+name)
        return
    api('PATCH' if current else 'POST',base+'/actions/variables/'+name if current else base+'/actions/variables',{'name':name,'value':value})

def verify_environment(base,environment):
    endpoint=base+'/environments/'+environment
    config=api('GET',endpoint)
    if config.get('deployment_branch_policy')!={'protected_branches':False,'custom_branch_policies':True}:
        raise GitHubFailure(environment+' must have a custom main-only branch policy; existing settings were preserved')
    policies=pages(endpoint+'/deployment-branch-policies','branch_policies')
    if not policies or any(p['name']!='main' or p.get('type','branch')!='branch' for p in policies):
        raise GitHubFailure(environment+' must permit only branch main, not tags or wildcards')
    # Existing reviewer/wait protections are never reset by automation.
    return config

def secret_metadata(base,repo_id):
    repository={v['name'] for v in pages(base+'/actions/secrets','secrets')}
    production={v['name'] for v in pages('repositories/'+str(repo_id)+'/environments/production/secrets','secrets')}
    expected={'SSH_HOST','SSH_PORT','SSH_USER','DEPLOY_PATH','SSH_PRIVATE_KEY','SSH_KNOWN_HOSTS'}
    missing=expected-(repository|production)
    if missing:raise GitHubFailure('Missing production secret names in both supported scopes: '+','.join(sorted(missing)))
    return {'repository':repository,'production':production}

def bootstrap():
    base='repos/'+REPO;repo=api('GET',base)
    if repo.get('full_name')!=REPO or not repo.get('permissions',{}).get('admin'):raise GitHubFailure('Repository administrator access required')
    # Never publishes or promotes READY. Valid names are metadata, not proof of a working key/server.
    set_variable(base,'AUTOMATION_READY','false')
    required_delivery_policy(base)
    for environment in ['production','automation']:verify_environment(base,environment)
    scopes=secret_metadata(base,repo['id'])
    app=api('GET',base+'/actions/variables/AUTOMERGE_APP_ID',missing=True)
    if app and app.get('value'):
        automation={v['name'] for v in pages('repositories/'+str(repo['id'])+'/environments/automation/secrets','secrets')}
        if not app['value'].isdigit() or 'AUTOMERGE_APP_PRIVATE_KEY' not in (automation|scopes['repository']):
            raise GitHubFailure('Configured GitHub App requires valid ID and available key metadata')
    set_variable(base,'BOOTSTRAP_CONFIGURED_SHA',api('GET',base+'/git/ref/heads/main')['object']['sha'])
    set_variable(base,'BOOTSTRAP_APPROVED_SHA','')
    # Initial installations start disabled. Preserve a previously verified
    # setting; integration has a separate policy/configuration job.
    if api('GET',base+'/actions/variables/AUTOMERGE_ENABLED',missing=True) is None:
        set_variable(base,'AUTOMERGE_ENABLED','false')
    print('Strict release protection and secret scopes verified; merge setting preserved; AUTOMATION_READY remains false until verified bootstrap delivery')

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
        if status['context']!=REQUIRED_CHECK:passed.add(status['context'])
    return set(required_checks)<=passed

def ensure_pr_for_validated_branch(run_id=None):
    """Create PR only; deliberately independent of merge policy and production secrets."""
    base='repos/'+REPO
    event_run=None
    if run_id is None:
        event_path=os.environ.get('GITHUB_EVENT_PATH')
        if os.environ.get('GITHUB_EVENT_NAME')!='workflow_run' or not event_path:return
        event_run=json.loads(Path(event_path).read_text()).get('workflow_run',{})
        if event_run.get('event')!='push' or event_run.get('conclusion')!='success' or event_run.get('head_branch')=='main' or event_run.get('head_repository',{}).get('full_name')!=REPO:return
        run_id=str(event_run.get('id',''))
    if not re.fullmatch('[0-9]+',str(run_id)):raise GitHubFailure('Invalid validated run ID')
    run=api('GET',base+'/actions/runs/'+str(run_id))
    branch=run.get('head_branch','');sha=run.get('head_sha','')
    if (run.get('event')!='push' or run.get('status')!='completed' or run.get('conclusion')!='success'
        or run.get('head_repository',{}).get('full_name')!=REPO or run.get('repository',{}).get('full_name')!=REPO
        or run.get('path')!='.github/workflows/deploy.yml'):
        raise GitHubFailure('Untrusted or unsuccessful validation run; PR not created')
    if not branch or branch=='main' or not re.fullmatch('[a-f0-9]{40}',sha):raise GitHubFailure('Invalid validated branch identity')
    if event_run and any(event_run.get(k)!=run.get(k) for k in ['head_sha','head_branch','workflow_id']):raise GitHubFailure('Validation event does not match authoritative run')
    workflow=api('GET',base+'/actions/workflows/deploy.yml')
    if run.get('workflow_id')!=workflow.get('id'):raise GitHubFailure('Untrusted workflow ID')
    jobs=pages(base+'/actions/runs/'+str(run_id)+'/jobs','jobs')
    if not any(j.get('name')==REQUIRED_CHECK and j.get('conclusion')=='success' for j in jobs):raise GitHubFailure('Validate job must succeed; skipped jobs are not validation')
    current_path=base+'/git/ref/heads/'+quote(branch,safe='')
    if api('GET',current_path)['object']['sha']!=sha:
        print('PR creation skipped: validated branch head is stale');return
    # Retain stacked PRs and drafts, including those deliberately targeting another base.
    pr_path=base+'/pulls?state=open&head='+quote(REPO.split('/')[0]+':'+branch,safe='')
    existing=api('GET',pr_path)
    if existing:
        print('PR already exists for validated branch',branch);return existing[0]
    main=api('GET',base+'/git/ref/heads/main')['object']['sha']
    comparison=api('GET',base+'/compare/'+main+'...'+sha)
    if comparison.get('ahead_by',0)<=0:
        print('PR creation skipped: branch has no changes ahead of main');return
    # Same path/name is insufficient if a branch rewrote Validate into a no-op.
    import base64
    definitions=[]
    for revision in [main,sha]:
        value=api('GET',base+'/contents/.github/workflows/deploy.yml?ref='+revision)
        try:definitions.append(base64.b64decode(value['content'],validate=False))
        except (KeyError,ValueError,TypeError):raise GitHubFailure('Cannot verify trusted CI definition')
    if definitions[0]!=definitions[1]:raise GitHubFailure('CI definition changed; independent workflow review required before automatic PR creation')
    if api('GET',current_path)['object']['sha']!=sha:
        print('PR creation skipped: branch moved before PR creation');return
    try:
        created=api('POST',base+'/pulls',{'head':branch,'base':'main','title':'NeuroDelo: '+branch,
            'draft':branch.startswith(('draft/','wip/')),
            'body':'Created automatically after trusted Validate run '+str(run_id)+' passed for '+sha+'. Required repository checks and review rules remain enforced. No deployment from this branch.'})
    except GitHubFailure as error:
        if 'HTTP 422' in str(error):
            existing=api('GET',pr_path)
            if existing:
                print('Concurrent PR creation detected; existing PR preserved');return existing[0]
        if 'HTTP 403' in str(error):
            raise GitHubFailure('PR creation denied (HTTP 403). Verify pull_requests:write for the selected token/App installation and repository Actions permission to create PRs; no protection or credentials were changed.') from error
        raise
    print('Created PR',created['number'],'for validated SHA',sha,'run',run_id)
    if os.environ.get('GITHUB_TOKEN_FALLBACK')=='true':
        # Native token PR events do not start CI. Dispatch existing validation-only
        # branch path; deploy.yml refuses production outside main.
        api('POST',base+'/actions/workflows/deploy.yml/dispatches',{'ref':branch,'inputs':{'operation':'preview','expected_revision':sha}})
        print('Requested required validation for native-token PR',created['number'])
    return created

def required_delivery_policy(base):
    """Check protected, strict Actions Validate for publication; no PR automation implied.

    Releasing a reviewed/merged main revision and automatically merging new PRs
    have separate requirements. Keep independent reviews mandatory for auto_merge().
    Never change GitHub branch protection or permit unvalidated code to deploy.
    """
    try:
        protection=api('GET',base+'/branches/main/protection')
    except GitHubFailure:
        # Only accept an actual strict, active ruleset; never guess from a 403.
        rules=api('GET',base+'/rules/branches/main')
        checks=next((r.get('parameters',{}) for r in rules if r.get('type')=='required_status_checks'),{})
        requirements=checks.get('required_status_checks',[])
        valid=checks.get('strict_required_status_checks_policy') and any(
            c.get('context')==REQUIRED_CHECK and c.get('integration_id')==15368 for c in requirements)
        if not valid:
            raise GitHubFailure('Cannot verify strict GitHub Actions Validate protection on main; deployment remains disabled')
    else:
        checks=protection.get('required_status_checks') or {}
        valid=checks.get('strict') and any(
            c.get('context')==REQUIRED_CHECK and c.get('app_id')==15368 for c in checks.get('checks',[]))
        if not valid:
            raise GitHubFailure('Main must require strict GitHub Actions Validate for releases')
    return True

def required_policy(base):
    try:
        protection=api('GET',base+'/branches/main/protection')
        count,required=verify_protection(protection);return protection,count,required
    except GitHubFailure:
        rules=api('GET',base+'/rules/branches/main')
        reviews=next((r.get('parameters',{}) for r in rules if r['type']=='pull_request'),{})
        checks=next((r.get('parameters',{}) for r in rules if r['type']=='required_status_checks'),{})
        required=checks.get('required_status_checks',[])
        if reviews.get('required_approving_review_count',0)<1 or not reviews.get('dismiss_stale_reviews_on_push') or not checks.get('strict_required_status_checks_policy'):
            raise GitHubFailure('Active main ruleset must require current reviews and strict checks')
        if not any(c['context']==REQUIRED_CHECK and c.get('integration_id')==15368 for c in required):raise GitHubFailure('Required Actions Validate ruleset missing')
        return {},reviews['required_approving_review_count'],[c['context'] for c in required]

def ensure_main_ci():
    # Native GITHUB_TOKEN merges suppress push CI. Always dispatch an exact main SHA, never assume push ran.
    base='repos/'+REPO;head=api('GET',base+'/git/ref/heads/main')['object']['sha']
    ready=os.environ.get('AUTOMATION_READY')=='true'
    approved=os.environ.get('BOOTSTRAP_APPROVED_SHA')==head and os.environ.get('BOOTSTRAP_CONFIGURED_SHA')==head
    native=os.environ.get('GITHUB_TOKEN_FALLBACK')=='true'
    if ready and not native:return
    runs=api('GET',base+'/actions/workflows/deploy.yml/runs?branch=main&per_page=30')['workflow_runs']
    current=[r for r in runs if r['head_sha']==head]
    operation='deploy' if ready else 'preview'
    if not ready and approved:
        if any(r.get('event')=='workflow_dispatch' and r.get('display_title')=='bootstrap '+head for r in current):return
        validated=False
        for run in current:
            if run.get('status')!='completed' or run.get('conclusion')!='success':continue
            jobs=api('GET',base+'/actions/runs/'+str(run['id'])+'/jobs?per_page=100')['jobs']
            if any(j['name']=='Validate' and j['conclusion']=='success' for j in jobs):validated=True;break
        if validated:operation='bootstrap'
        elif current:return
    elif current or not native:return
    source=api('GET',base+'/contents/.github/workflows/deploy.yml?ref=main')
    import base64
    text=base64.b64decode(source['content']).decode()
    if 'name: NeuroDelo CI/CD' not in text or 'operation:' not in text or 'expected_revision:' not in text:raise GitHubFailure('SHA-gated delivery workflow not integrated yet')
    api('POST',base+'/actions/workflows/deploy.yml/dispatches',{'ref':'main','inputs':{'operation':operation,'expected_revision':head}})
    print('Requested tested main operation automatically:',operation,head)

def integration_policy(base):
    """Honor the actual server review rule; never invent or remove an approval."""
    try:
        protection=api('GET',base+'/branches/main/protection')
    except GitHubFailure:
        rules=api('GET',base+'/rules/branches/main')
        checks=next((r.get('parameters',{}) for r in rules if r.get('type')=='required_status_checks'),{})
        required=checks.get('required_status_checks',[])
        if not checks.get('strict_required_status_checks_policy') or not any(c.get('context')==REQUIRED_CHECK and c.get('integration_id')==15368 for c in required):
            raise GitHubFailure('Cannot verify active strict Actions Validate rule; integration blocked')
        review=next((r.get('parameters',{}) for r in rules if r.get('type')=='pull_request'),{})
        count=review.get('required_approving_review_count',0)
        if not isinstance(count,int) or count<0 or (count>0 and not review.get('dismiss_stale_reviews_on_push')):
            raise GitHubFailure('Cannot verify current review rule; integration blocked')
        return {},count,[c['context'] for c in required]
    checks=protection.get('required_status_checks') or {}
    if not (protection.get('enforce_admins',{}).get('enabled') and checks.get('strict') and any(c.get('context')==REQUIRED_CHECK and c.get('app_id')==15368 for c in checks.get('checks',[]))):
        observed={'enforce_admins':bool(protection.get('enforce_admins',{}).get('enabled')),'strict_checks':bool(checks.get('strict')),'actions_validate':any(c.get('context')==REQUIRED_CHECK and c.get('app_id')==15368 for c in checks.get('checks',[]))}
        raise GitHubFailure('Integration policy gate failed: '+json.dumps(observed,sort_keys=True)+'; existing protection preserved')
    review=protection.get('required_pull_request_reviews') or {};count=review.get('required_approving_review_count',0)
    if not isinstance(count,int) or count<0 or (count>0 and not review.get('dismiss_stale_reviews')):
        raise GitHubFailure('Cannot verify current review rule; integration blocked')
    return protection,count,list(dict.fromkeys(checks.get('contexts',[])+[c['context'] for c in checks.get('checks',[])]))

def configure_integration():
    """One-time enablement after validated main. Never edits branch protection."""
    base='repos/'+REPO;repo=api('GET',base)
    if repo.get('full_name')!=REPO or not repo.get('permissions',{}).get('admin'):
        raise GitHubFailure('Existing authorized administrative grant required to configure integration')
    if not repo.get('allow_auto_merge'):raise GitHubFailure('Repository native auto-merge setting is disabled; existing setting preserved')
    _,count,checks=integration_policy(base)
    verify_environment(base,'automation')
    expected=os.environ.get('VALIDATED_MAIN_SHA')
    if expected and (not re.fullmatch('[a-f0-9]{40}',expected) or api('GET',base+'/git/ref/heads/main')['object']['sha']!=expected):
        raise GitHubFailure('Validated main is stale; integration setting preserved')
    set_variable(base,'AUTOMERGE_ENABLED','true')
    print(json.dumps({'result':'protected_integration_enabled','required_approvals':count,'required_checks':checks,
        'unattended_without_reviewer':count==0,'branch_protection_modified':False}))

def auto_merge():
    base='repos/'+REPO;repo=api('GET',base)
    if not repo.get('allow_auto_merge'):raise GitHubFailure('Repository auto-merge is disabled')
    protection,count,required=integration_policy(base)
    for pr in pages(base+'/pulls?state=open&base=main'):
        if pr['draft'] or pr['head']['repo'] is None or pr['head']['repo']['full_name']!=REPO:continue
        number=pr['number'];pr=api('GET',base+'/pulls/'+str(number))
        if pr.get('mergeable') is False:continue
        head=pr['head']['sha'];reviews=pages(base+'/pulls/'+str(number)+'/reviews')
        review=api('POST','graphql',{'query':'query($n:Int!){repository(owner:"2006minden-gif",name:"-Chat-GPT-"){pullRequest(number:$n){reviewDecision headRefOid}}}','variables':{'n':number}})
        decision=review.get('data',{}).get('repository',{}).get('pullRequest',{})
        review_decision=decision.get('reviewDecision')
        if decision.get('headRefOid')!=head or review_decision not in [None,'APPROVED'] or (count>0 and review_decision!='APPROVED'):continue
        permissions={r['user']['login']:'write' if r.get('author_association') in ['OWNER','MEMBER','COLLABORATOR'] else 'none' for r in reviews}
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
    ensure_main_ci()

def report_failure(error):
    # Only bounded messages from the controller; never dump commands, env or traces.
    message=str(error) if isinstance(error,GitHubFailure) else 'GitHub operation timed out; retry after inspecting workflow status'
    if os.environ.get('GITHUB_ACTIONS')=='true':
        escaped=message.replace('%','%25').replace('\r','%0D').replace('\n','%0A')
        print('::error title=NeuroDelo automation::'+escaped)
    else:print(message)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['bootstrap','auto-merge','create-pr','configure-integration']);parser.add_argument('--apply',action='store_true');parser.add_argument('--run-id');args=parser.parse_args()
    try:
        if args.operation=='bootstrap':
            if not args.apply:print(json.dumps({'repository':REPO,'required_check':REQUIRED_CHECK,'reviews':1,'environments':['production','automation'],'branch':'main','note':'Use --apply with administrator gh authentication. No secrets are read or changed.'},indent=2))
            else:bootstrap()
        elif args.operation=='configure-integration':configure_integration()
        elif args.operation=='create-pr':ensure_pr_for_validated_branch(args.run_id)
        else:auto_merge()
    except (GitHubFailure,subprocess.TimeoutExpired) as error:
        report_failure(error);raise SystemExit(1)
