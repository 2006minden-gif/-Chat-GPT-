"""CI deployment coordinator. SSH credentials exist only in a temporary runner directory."""
import argparse
import contextlib
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import tempfile
import time
import health

ACCOUNT='/home/n/neurodepro'
class RemoteFailure(RuntimeError):
    def __init__(self, message, details=None): super().__init__(message); self.details=details or {}

def validate_bundle(bundle, revision):
    m=json.loads((bundle/'manifest.json').read_text())
    if m['revision']!=revision or not re.fullmatch('[a-f0-9]{40}',revision): raise ValueError('artifact_revision_mismatch')
    expected=set(m['files'])|set(m['tools'])|{'manifest.json'}
    actual=set()
    for p in bundle.rglob('*'):
        if p.is_symlink(): raise ValueError('artifact_symlink')
        if p.is_file(): actual.add(p.relative_to(bundle).as_posix())
    if actual!=expected: raise ValueError('artifact_file_list_mismatch')
    for path,digest in {**m['files'],**m['tools']}.items():
        if Path(path).is_absolute() or '..' in Path(path).parts or hashlib.sha256((bundle/path).read_bytes()).hexdigest()!=digest:
            raise ValueError('artifact_checksum_mismatch')
    return m

class Remote:
    def __init__(self, bundle, revision, release_id):
        self.bundle=bundle; self.revision=revision; self.id=release_id
        self.tmp=tempfile.TemporaryDirectory(); folder=Path(self.tmp.name);folder.chmod(0o700)
        host=os.environ['SSH_HOST'];user=os.environ['SSH_USER'];port=os.environ['SSH_PORT']
        if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*',host) or not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_-]*',user) or not port.isdigit() or not 1<=int(port)<=65535:
            raise ValueError('invalid_ssh_target')
        if os.environ.get('DEPLOY_PATH')!=ACCOUNT+'/public_html': raise ValueError('unexpected_deployment_path')
        self.php=os.environ.get('PHP_CLI') or '/usr/bin/php8.4'
        if not re.fullmatch(r'[A-Za-z0-9_/][A-Za-z0-9_./-]*',self.php):raise ValueError('invalid_php_command')
        key=os.environ['SSH_PRIVATE_KEY'];known=os.environ['SSH_KNOWN_HOSTS']
        if not key.strip() or not known.strip(): raise ValueError('ssh_credentials_missing')
        for name,value in [('key',key),('known_hosts',known)]:
            p=folder/name;p.write_text(value+'\n');p.chmod(0o600)
        self.ssh=['ssh','-p',port,'-i',str(folder/'key'),'-o','IdentitiesOnly=yes','-o','BatchMode=yes',
                  '-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(folder/'known_hosts'),'-o','ConnectTimeout=20']
        self.target=user+'@'+host
        self.candidate=ACCOUNT+'/.neurodelo-deploy/incoming/'+self.id
    def close(self): self.tmp.cleanup()
    def command(self, command, input=None, json_output=False):
        try:r=subprocess.run(self.ssh+[self.target,command],input=input,text=True,capture_output=True,timeout=600)
        except (OSError,subprocess.TimeoutExpired) as error:raise RemoteFailure('ssh_transport_failed') from error
        value={}
        if json_output:
            try:value=json.loads(r.stdout)
            except ValueError:pass
        if r.returncode or (json_output and value.get('ok') is not True):
            raise RemoteFailure('remote_operation_failed',value)
        return value if json_output else None
    def preflight(self):
        return self.command(shlex.join([self.php,'/dev/stdin','preflight',ACCOUNT,self.id]),
                            (self.bundle/'remote.php').read_text(),True)
    def sync(self, source, destination, preview=False):
        cmd=['rsync','-rz','--checksum','--delay-updates','--safe-links','--chmod=D700,F600']
        if preview:cmd+=['--dry-run']
        try:r=subprocess.run(cmd+['-e',shlex.join(self.ssh),str(source),self.target+':'+destination],capture_output=True,text=True,timeout=600)
        except (OSError,subprocess.TimeoutExpired) as error:raise RemoteFailure('release_transfer_failed') from error
        if r.returncode:raise RemoteFailure('release_transfer_failed')
    def preview(self):
        for directory in ['public_html','private']:
            self.sync(str(self.bundle/directory)+'/',ACCOUNT+'/'+directory+'/',True)
    def stage(self, baseline):
        # Paths and ID are validated locally; never reuse a staging directory.
        script='set -eu\numask 077\n'
        for folder in [ACCOUNT,ACCOUNT+'/.neurodelo-deploy',ACCOUNT+'/.neurodelo-deploy/incoming']:
            q=shlex.quote(folder);script+=f'test ! -L {q}\n'
        script+='test -d '+shlex.quote(ACCOUNT)+'\n'
        script+='mkdir -p '+shlex.quote(ACCOUNT+'/.neurodelo-deploy/incoming')+'\n'
        script+='chmod 700 '+shlex.quote(ACCOUNT+'/.neurodelo-deploy')+' '+shlex.quote(ACCOUNT+'/.neurodelo-deploy/incoming')+'\n'
        script+='test ! -e '+shlex.quote(self.candidate)+'\nmkdir '+shlex.quote(self.candidate)+'\n'
        self.command('bash -se',script)
        self.sync(str(self.bundle)+'/',self.candidate+'/')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'baseline.json';p.write_text(json.dumps(baseline))
            self.sync(p,self.candidate+'/baseline.json')
    def evidence(self, report):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'after-health.json';path.write_text(json.dumps(report))
            self.sync(path,self.candidate+'/after-health.json')
    def action(self,operation, release_id=None):
        command=shlex.join(['env','NEURO_PHP_BIN='+self.php,self.php,self.candidate+'/remote.php',operation,ACCOUNT,release_id or self.id])
        return self.command(command,json_output=True)

def coordinate(remote, mode='deploy', snapshot=health.snapshot, attempts=3, delay=2, expected_assets=None, revision_snapshot=None):
    report={'mode':mode,'result':'failed','rollback_verified':False}
    before=snapshot();report['before']=before
    if not before.get('complete'):
        report['error']='baseline_transport_unavailable';return report
    if mode=='rollback':
        try:
            remote.stage(before);restored=remote.action('recover');report['restore']=restored
            after=snapshot();report['after']=after
            if health.same_baseline(restored['baseline'],after):
                remote.action('confirm-rollback',restored['id']);report['rollback_verified']=True
                report['result']='rollback_verified_to_baseline' if after['ok'] else 'rollback_verified_unhealthy_baseline'
            else:report['error']='rollback_health_not_verified'
        except RemoteFailure as error:report['error']=str(error);report['remote']=error.details
        return report
    try:
        report['preflight']=remote.preflight()
        if mode=='bootstrap' and not before['ok']:
            report['error']='bootstrap_requires_healthy_baseline';return report
        if mode=='preview':
            remote.preview();report['result']='preview_passed' if before['ok'] else 'preview_unhealthy';return report
        remote.stage(before)
    except RemoteFailure as error:
        report['error']=str(error);report['remote']=error.details;return report
    try:
        report['apply']=remote.action('apply')
        for attempt in range(attempts):
            after=health.require_asset_revision((revision_snapshot or snapshot)(),expected_assets);report['after']=after
            if after['ok']:break
            if attempt+1<attempts:time.sleep(delay)
        if not after['ok']:
            if health.only_preexisting_failures(before,after):
                remote.evidence(after);report['unhealthy_release']=remote.action('mark-unhealthy')
                report['error']='preexisting_health_failures_persist';report['preexisting_failures']=[p for p,r in before['checks'].items() if not r['ok']]
                report['approved_files_retained_without_new_regression']=True
                return report
            raise RemoteFailure('post_deployment_health_failed')
        remote.evidence(after)
        report['finalize']=remote.action('finalize');report['result']='deployed_and_verified';return report
    except RemoteFailure as error:
        report['error']=str(error);report['remote']=error.details
        report['preexisting_failures']=[p for p,r in before['checks'].items() if not r['ok']]
        try:
            report['restore']=restored=remote.action('rollback')
            rolled_back=snapshot();report['after_rollback']=rolled_back
            if health.same_baseline(before,rolled_back):
                remote.action('confirm-rollback',restored['id']);report['rollback_verified']=True
            else:report['rollback_error']='rollback_health_not_verified'
        except RemoteFailure as rollback_error:
            report['rollback_error']=str(rollback_error);report['rollback_remote']=rollback_error.details
        return report

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--revision',required=True)
    parser.add_argument('--operation',choices=['deploy','preview','rollback','bootstrap'],default='deploy');parser.add_argument('--report',type=Path,required=True)
    args=parser.parse_args();report={'result':'failed'}
    try:
        manifest=validate_bundle(args.bundle,args.revision)
        if args.operation=='bootstrap' and manifest.get('migrations'):raise ValueError('bootstrap_migrations_forbidden')
        run=os.environ.get('GITHUB_RUN_ID','local');attempt=os.environ.get('GITHUB_RUN_ATTEMPT','1')
        if not run.isdigit() or not attempt.isdigit():raise ValueError('invalid_github_run_identity')
        release_id=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ')+'-r'+run+'-a'+attempt+'-'+args.revision[:12]
        remote=Remote(args.bundle,args.revision,release_id)
        expected_assets={'/'+p.split('/',1)[1]:h for p,h in manifest['files'].items() if (p.startswith('public_html/') and p.endswith(('.js','.css'))) or p in ['public_html/favicon.svg','public_html/favicon.ico','public_html/sitemap.xml','public_html/robots.txt']}
        try:
            report=coordinate(remote,args.operation,expected_assets=expected_assets,revision_snapshot=lambda:health.snapshot(extra_assets=expected_assets))
            if report['result']=='deployed_and_verified' and 'private/workflow/prepare.php' in manifest['files']:
                try:
                    prepared=remote.command(shlex.join([remote.php,ACCOUNT+'/private/workflow/prepare.php']),json_output=True)
                    report['draft_preparation']={k:prepared[k] for k in ['ok','legal_draft_prepared','service_drafts_created','published','error'] if k in prepared}
                except Exception:
                    report['draft_preparation']={'ok':False,'error':'draft_preparation_unavailable'}
            if report['result']=='deployed_and_verified' and 'private/workflow/diagnostics.php' in manifest['files']:
                try:
                    gates=remote.command(shlex.join([remote.php,ACCOUNT+'/private/workflow/diagnostics.php']),json_output=True)
                    # Explicit safe field selection; never echo arbitrary remote settings or failures.
                    report['workflow_gates']={k:gates[k] for k in ['ok','launch_readiness','legal','document_templates','owner_details_reviewed','mail_verified','repeat_mail_verification_required','capabilities','remaining_actions'] if k in gates}
                except Exception:
                    report['workflow_gates']={'ok':False,'error':'gate_evidence_unavailable'}
        finally:remote.close()
        report['revision']=args.revision;report['release_id']=release_id
    except Exception as error:
        report={'result':'failed','error_type':type(error).__name__}
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(report,indent=2,ensure_ascii=False))
    print(json.dumps({'result':report['result'],'rollback_verified':report.get('rollback_verified',False),**({'workflow_gates':report['workflow_gates']} if 'workflow_gates' in report else {})}))
    raise SystemExit(0 if report['result'] in ['deployed_and_verified','preview_passed','rollback_verified_to_baseline'] else 1)
