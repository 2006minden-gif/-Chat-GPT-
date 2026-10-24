"""Build an immutable, allowlisted release. No production configuration is read."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import sys

ROOT = Path(__file__).resolve().parents[2]

def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def policy_check(root=ROOT):
    policy = json.loads((root / 'scripts/deploy/policy.json').read_text())
    if policy.get('schema_version') != 1 or policy.get('keep_backups', 0) < 2:
        raise ValueError('invalid_release_policy')
    entries = policy.get('migrations', [])
    seen = set()
    for entry in entries:
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
    return policy

def build(output, revision, root=ROOT):
    if not re.fullmatch(r'[0-9a-f]{40}', revision): raise ValueError('invalid_revision')
    if output.exists(): raise ValueError('release_directory_already_exists')
    policy = policy_check(root)
    output.mkdir(parents=True)
    files, tools = {}, {}
    def copy(source, destination, mapping):
        if source.is_symlink() or not source.is_file(): raise ValueError('non_regular_release_source')
        target = output / destination; target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target); mapping[destination] = digest(target)
    for source_dir, prefix, names in [('public', 'public_html', policy['public_files']), ('private', 'private', policy['private_files'])]:
        for name in names:
            if not re.fullmatch(r'[A-Za-z0-9_.-]+', name) or name in ['config.php','config.example.php','privacy-policy.txt','setup.php','.user.ini']:
                raise ValueError('forbidden_release_path')
            copy(root / source_dir / name, prefix + '/' + name, files)
    copy(root / 'scripts/deploy/remote.php', 'remote.php', tools)
    if policy['migrations']:
        copy(root / 'scripts/migrate.php', 'scripts/migrate.php', tools)
        for entry in policy['migrations']:
            for direction in ['up', 'down']:
                path = 'database/migrations/' + entry['version'] + '/' + direction + '.sql'
                copy(root / path, path, tools)
    manifest = {'schema_version':1,'revision':revision,'files':files,'tools':tools,
                'keep_backups':policy['keep_backups'],'migrations':policy['migrations']}
    (output / 'manifest.json').write_text(json.dumps(manifest, sort_keys=True, indent=2))
    return manifest

if __name__ == '__main__':
    if len(sys.argv) == 2 and sys.argv[1] == '--check':
        policy_check(); print('Release and migration policy validated')
    else:
        build(Path(sys.argv[1]), sys.argv[2])
