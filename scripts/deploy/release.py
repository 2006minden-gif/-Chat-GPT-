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
            and (parts[-1] == '.htaccess' or parts[-1].endswith(('.php', '.html', '.css', '.js'))))

def check_source_path(source, root):
    if any(p.is_symlink() for p in [source, *source.parents] if p == root or root in p.parents):
        raise ValueError('non_regular_release_source')

def policy_check(root=ROOT):
    policy = json.loads((root / 'scripts/deploy/policy.json').read_text())
    if policy.get('schema_version') != 1 or policy.get('keep_backups', 0) < 2:
        raise ValueError('invalid_release_policy')
    entries = policy.get('migrations', [])
    seen = set()
    previous = None
    for entry in entries:
        if 'operator' in entry:
            if entry.get('depends_on') != previous or not re.fullmatch(r'scripts/migrate(?:-[a-z]+)?\.php', entry['operator']):
                raise ValueError('invalid_migration_dependency_chain')
            if not (root / entry['operator']).is_file():
                raise ValueError('migration_operator_missing')
        previous = entry['version']
        version = entry['version']
        if not re.fullmatch(r'[0-9]{3}_[a-z_]+', version) or version in seen:
            raise ValueError('invalid_migration_version')
        seen.add(version)
        folder = root / 'database/migrations' / version
        for direction in ['up', 'down']:
            if digest(folder / (direction + '.sql')) != entry[direction + '_sha256']:
                raise ValueError('unreviewed_migration_checksum')
        if entry['automatic']:
            sql = re.sub(r'^--[^\n]*$', '', (folder / 'up.sql').read_text(), flags=re.M)
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            # Narrow automatic contract: only the tested, additive Stage 3 operator.
            if version != '004_crm_foundation' or entry['kind'] != 'additive' or not statements:
                raise ValueError('automatic_migration_not_supported')
            if any(not re.fullmatch(r'CREATE TABLE nd_[a-z_]+\s*\([\s\S]+\)\s*ENGINE=InnoDB[\s\S]*', s) for s in statements):
                raise ValueError('destructive_or_unreviewed_migration')
        if not isinstance(entry['automatic'], bool) or not isinstance(entry['required'], bool):
            raise ValueError('invalid_migration_flags')
    discovered = list((root / 'database/migrations').glob('*/up.sql'))
    if discovered and not all((root / p).is_file() for p in ['scripts/migrate.php', 'tests/test_crm_migrations.py', 'tests/test_prelaunch_foundation.py']):
        raise ValueError('migration_compatibility_tests_missing')
    if any('operator' in e for e in entries) and {p.parent.name for p in discovered} != seen:
        raise ValueError('migration_dependency_chain_incomplete')
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
    # Delivery is independent from execution approval. All versioned SQL/CLI stays private.
    for source in sorted((root / 'database').rglob('*.sql')):
        path=source.relative_to(root).as_posix()
        if not re.fullmatch(r'database/(schema\.sql|migrations/[0-9]{3}_[a-z_]+\.sql|migrations/[0-9]{3}_[a-z_]+/(up|down)\.sql)',path):
            raise ValueError('unapproved_sql_file_path')
        copy(source,path,tools)
    for source in sorted((root / 'scripts').glob('migrate*.php')):
        copy(source, 'scripts/' + source.name, tools)
    manifest = {'schema_version':1,'revision':revision,'files':files,'tools':tools,
                'keep_backups':policy['keep_backups'],'migrations':policy['migrations'],
                'verification_contract':'ci-mysql57-backup-restore-v1'}
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return manifest

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--check':
        policy_check(); print('Release and migration policy validated')
    else:
        build(Path(sys.argv[1]), sys.argv[2])
