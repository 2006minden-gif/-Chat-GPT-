"""One-time verified-delivery promotion. No production SSH or secret access; admin grant required for variables."""
import argparse
import io
import json
from pathlib import Path
import re
import subprocess
import zipfile
from control import REPO,GitHubFailure,api,required_policy,verify_environment,set_variable

def verify_report(report,sha):
    if not isinstance(report,dict) or report.get('revision')!=sha or report.get('mode')!='bootstrap' or report.get('result')!='deployed_and_verified':raise GitHubFailure('Bootstrap deployment did not succeed for the expected revision')
    for phase in ['before','after']:
        health=report.get(phase,{})
        if health.get('ok') is not True or health.get('complete') is not True or not health.get('checks') or not all(c.get('ok') is True for c in health['checks'].values()):raise GitHubFailure('Bootstrap health is not verified')
    apply=report.get('apply',{});final=report.get('finalize',{})
    if apply.get('revision')!=sha or apply.get('backup_verified') is not True or apply.get('recovery_verified') is not True or apply.get('migrations')!=[]:raise GitHubFailure('Bootstrap backup/recovery or migration guard was not verified')
    hashes=apply.get('files_sha256',{})
    policy=json.loads((Path(__file__).resolve().parents[2]/'scripts/deploy/policy.json').read_text())
    expected={prefix+'/'+name for prefix,key in [('public_html','public_files'),('private','private_files')] for name in policy[key]}
    if set(hashes)!=expected or any(not isinstance(v,str) or not re.fullmatch('[a-f0-9]{64}',v) for v in hashes.values()):raise GitHubFailure('Actual server file hashes are missing or incomplete')
    for path,digest in hashes.items():
        if path.startswith('public_html/') and path.endswith(('.js','.css')):
            if report['after']['checks'].get('/'+path.split('/',1)[1],{}).get('sha256')!=digest:raise GitHubFailure('Published asset revision is not verified')
    if final.get('revision')!=sha or final.get('files_verified') is not True:raise GitHubFailure('Bootstrap final server state is unverified')

def read_report(base,run_id):
    run=api('GET',base+'/actions/runs/'+run_id)
    if run.get('head_branch')!='main' or run.get('head_repository',{}).get('full_name')!=REPO or run.get('path')!='.github/workflows/deploy.yml' or run.get('event')!='workflow_dispatch' or run.get('conclusion')!='success':raise GitHubFailure('Only a successful trusted main bootstrap workflow can promote delivery')
    jobs=api('GET',base+'/actions/runs/'+run_id+'/jobs?per_page=100')['jobs']
    if not all(any(j['name']==name and j['conclusion']=='success' for j in jobs) for name in ['Validate','Publish approved main']):raise GitHubFailure('Main CI and publish jobs must both pass')
    artifacts=api('GET',base+'/actions/runs/'+run_id+'/artifacts?per_page=100')['artifacts']
    matches=[a for a in artifacts if a['name'].startswith('deployment-evidence-'+run_id+'-') and not a['expired']]
    artifact=max(matches,key=lambda a:a['id']) if matches else None
    if not artifact or artifact['size_in_bytes']>1048576:raise GitHubFailure('Bootstrap evidence artifact unavailable')
    r=subprocess.run(['gh','api',base+'/actions/artifacts/'+str(artifact['id'])+'/zip'],capture_output=True,timeout=45)
    if r.returncode or len(r.stdout)>1048576:raise GitHubFailure('Bootstrap evidence download failed')
    with zipfile.ZipFile(io.BytesIO(r.stdout)) as archive:
        if archive.namelist()!=['deployment-report.json'] or archive.getinfo('deployment-report.json').file_size>1048576:raise GitHubFailure('Unexpected bootstrap evidence file')
        report=json.loads(archive.read('deployment-report.json'))
    verify_report(report,run['head_sha']);return run,report

def promote(run_id):
    if not re.fullmatch('[0-9]+',run_id):raise GitHubFailure('Invalid bootstrap run ID')
    base='repos/'+REPO;repo=api('GET',base)
    if repo.get('full_name')!=REPO or not repo.get('permissions',{}).get('admin'):raise GitHubFailure('Repository administrator access required')
    required_policy(base)
    for env in ['production','automation']:verify_environment(base,env)
    run,report=read_report(base,run_id)
    if api('GET',base+'/git/ref/heads/main')['object']['sha']!=run['head_sha']:raise GitHubFailure('Main moved after bootstrap; verify the current main before promotion')
    # Only metadata/verification references, never a token, credential or plaintext private file.
    set_variable(base,'BOOTSTRAP_VERIFIED_RUN',run_id)
    set_variable(base,'BOOTSTRAP_VERIFIED_SHA',run['head_sha'])
    set_variable(base,'BOOTSTRAP_APPROVED_SHA','')
    set_variable(base,'AUTOMATION_READY','true')
    print(json.dumps({'result':'verified_bootstrap_promoted','run_id':run_id,'revision':run['head_sha'],'files_verified':len(report['apply']['files_sha256'])}))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('operation',choices=['check','promote']);parser.add_argument('--run-id');parser.add_argument('--apply',action='store_true');args=parser.parse_args()
    try:
        if args.operation=='check':verify_environment('repos/'+REPO,'production');print('Production environment remains main-only; no settings changed')
        elif not args.apply:raise GitHubFailure('Promotion requires --apply and administrator authorization after successful smoke delivery')
        else:promote(args.run_id or '')
    except (GitHubFailure,ValueError,KeyError,TypeError,AttributeError,zipfile.BadZipFile,subprocess.TimeoutExpired) as error:print(str(error) if isinstance(error,GitHubFailure) else 'Bootstrap evidence validation failed');raise SystemExit(1)
