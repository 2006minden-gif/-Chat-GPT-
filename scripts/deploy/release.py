"""Build an immutable, allowlisted release. No production configuration is read."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

FORBIDDEN_NAMES = {'config.php', 'config.example.php', 'privacy-policy.txt', 'setup.php', '.user.ini'}

def safe_application_path(name):
    parts = name.split('/')
    return (bool(parts) and all(re.fullmatch(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*|\.htaccess', p)
            and p not in {'.', '..'} for p in parts)
            and parts[-1] not in FORBIDDEN_NAMES
            and (parts[-1] == '.htaccess' or parts[-1].endswith(('.php', '.html', '.css', '.js')) or name in {'favicon.svg','favicon.ico','sitemap.xml','robots.txt'}))

def check_source_path(source, root):
    if any(p.is_symlink() for p in [source, *source.parents] if p == root or root in p.parents):
        raise ValueError('non_regular_release_source')

def policy_check(root=ROOT):
    policy = json.loads((root / 'scripts/deploy/policy.json').read_text())
    if policy.get('schema_version') != 1 or policy.get('keep_backups', 0) < 2:
        raise ValueError('invalid_release_policy')
    if not isinstance(policy.get('database_recovery_required',False),bool):raise ValueError('invalid_database_recovery_policy')
    if policy.get('migrations') != []:raise ValueError('schema_migrations_forbidden')
    for folder in ['public', 'private']:
        names = policy.get(folder + '_files', [])
        if len(names) != len(set(names)) or any(not safe_application_path(n) for n in names):
            raise ValueError('forbidden_release_path')
        discovered = set()
        for source in (root / folder).rglob('*'):
            check_source_path(source, root)
            if source.is_file() and source.name not in FORBIDDEN_NAMES:
                discovered.add(source.relative_to(root / folder).as_posix())
        if discovered != set(names):
            raise ValueError('application_release_closure_mismatch')
    return policy

def build(output, revision, root=ROOT):
    if not re.fullmatch(r'[0-9a-f]{40}', revision): raise ValueError('invalid_revision')
    if output.exists(): raise ValueError('release_directory_already_exists')
    policy = policy_check(root)
    output.mkdir(parents=True)
    files, tools = {}, {}
    def copy(source, destination, mapping):
        check_source_path(source, root)
        if source.is_symlink() or not source.is_file(): raise ValueError('non_regular_release_source')
        target = output / destination; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target); mapping[destination] = digest(target)
    for source_dir, prefix, names in [('public', 'public_html', policy['public_files']), ('private', 'private', policy['private_files'])]:
        for name in names:
            if not safe_application_path(name):
                raise ValueError('forbidden_release_path')
            copy(root / source_dir / name, prefix + '/' + name, files)
    copy(root / 'scripts/deploy/remote.php', 'remote.php', tools)
    copy(root / 'scripts/deploy/recovery.php', 'recovery.php', tools)
    copy(root / 'scripts/deploy/portfolio-retirement.php', 'portfolio-retirement.php', tools)
    copy(root / 'database/schema.sql', 'database/schema.sql', tools)
    manifest = {'schema_version':1,'revision':revision,'files':files,'tools':tools,
                'keep_backups':policy['keep_backups'],'migrations':[],
                'portfolio_retirement':json.loads((root/'scripts/deploy/retirement-policy.json').read_text()),
                'database_recovery_required':policy.get('database_recovery_required',False),
                'verification_contract':'ci-mysql57-backup-restore-v1'}
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return manifest

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--check':
        policy_check(); print('Release and migration policy validated')
    else:
        build(Path(sys.argv[1]), sys.argv[2])
