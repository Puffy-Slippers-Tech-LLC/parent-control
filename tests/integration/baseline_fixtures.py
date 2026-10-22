"""Offline baseline-only reconciliation of the finite reusable fixture set."""
import hashlib
import json
from pathlib import Path
import re
import stat
from types import SimpleNamespace

from tests.fixtures import baseline_assets as assets
from tests.fixtures import native_assets
from tests.fixtures.native_trust import (
    TRUST_RECORD, TRUST_FILE, TRUST_PENDING, TRUST_PURPOSE,
    ForeignTrustMetadataError, OwnedTrustMetadataError, native_tool_paths, trust_entries,
    validate_trusted_record, validate_trusted_shape,
    BACKEND_CONFIG, BACKEND_RECORD, BACKEND_PENDING, BACKEND_PURPOSE,
    file_backend_config, file_backend_sources, validate_backend_record,
    validate_backend_provenance)
import prepare_vm

RECORD = '/var/lib/onpc-baseline-fixtures.json'
PURPOSE = 'onpc-reusable-fixtures-v1'
CLEAN_PURPOSE = 'onpc-baseline-environment-v1'
RETIRE_RECORD = '/var/lib/onpc-baseline-fixture-retirement.json'
NATIVE_RULES_RECORD = '/var/lib/onpc-baseline-native-rules.json'
NATIVE_RULES_PURPOSE = 'onpc-ubuntu-native-open-policy-v1'
NATIVE_RULES_ROOT = '/etc/fapolicyd/rules.d'
NATIVE_RULES_FILE = NATIVE_RULES_ROOT + '/95-allow-open.rules'
NATIVE_RULES_PENDING = NATIVE_RULES_FILE + '.onpc-baseline-new'
NATIVE_RULES_LEGACY = '/etc/fapolicyd/fapolicyd.rules'
NATIVE_RULES_COMPILED = '/etc/fapolicyd/compiled.rules'
NATIVE_RULES_SOURCE_PATTERN = (
    r'/usr/share/(?:fapolicyd|doc/fapolicyd)/(?:[A-Za-z0-9_.+-]+/)*95-allow-open[.]rules')


def environment_files(identities, os_id='ubuntu'):
    from tests.fixtures.baseline_environment import desktop_settings_files, automatic_update_files
    return desktop_settings_files(identities) | automatic_update_files(os_id)


def _clean_declaration(g):
    identities = accounts(g)
    return identities, environment_files(identities)


def movable_files(g):
    identities, environment = _clean_declaration(g)
    return {path: value for path, value in declared_files(g, identities).items()
            if path not in environment}


def _present(g, path):
    return g.exists(path) or g.is_symlink(path)


def _retirement_plan(g, script_digest):
    """Record the fully verified finite legacy closure before removing any file."""
    movable = movable_files(g)
    require(not any(_present(g, path) for path in (
        RECORD + '.new', TRUST_RECORD + '.new', TRUST_PENDING,
        *(path + '.onpc-baseline-new' for path in movable))), 'retirement-incomplete')
    allowed = set(movable) | {TRUST_RECORD, TRUST_FILE}
    if _present(g, RETIRE_RECORD):
        regular(g, RETIRE_RECORD, 0, 0, 0o600)
        plan = json.loads(g.read_file(RETIRE_RECORD))
        require(type(plan) is dict and set(plan) == {'purpose', 'files'}
                and plan['purpose'] == 'onpc-legacy-fixture-retirement-v1'
                and type(plan['files']) is dict and set(plan['files']) == allowed,
                'retirement-record')
    else:
        verify(g, script_digest)
        record = json.loads(g.read_file(RECORD))
        files = {path: record['files'][path] for path in movable}
        for path in (TRUST_RECORD, TRUST_FILE):
            info = g.lstatns(path)
            files[path] = {'sha256': g.checksum('sha256', path),
                           'mode': stat.S_IMODE(info['st_mode']),
                           'uid': info['st_uid'], 'gid': info['st_gid']}
        plan = {'purpose': 'onpc-legacy-fixture-retirement-v1', 'files': files}
        write_record(g, plan, RETIRE_RECORD)
    # Recheck every remaining member before resuming any removal. Missing files
    # are authorized only by this durable, already verified retirement intent.
    for path, spec in plan['files'].items():
        require(type(spec) is dict and set(spec) == {'sha256', 'mode', 'uid', 'gid'}
                and type(spec['sha256']) is str
                and re.fullmatch('[0-9a-f]{64}', spec['sha256']) is not None,
                'retirement-record')
        if path in movable:
            _, mode, role = movable[path]
            account = accounts(g)[role]
            require((spec['mode'], spec['uid'], spec['gid']) ==
                    (mode, account.pw_uid, account.pw_gid), 'retirement-record')
        else:
            require(spec['uid'] == 0 and spec['mode'] == 0o600
                    and type(spec['gid']) is int and spec['gid'] >= 0,
                    'retirement-record')
        if _present(g, path):
            directory(g, str(Path(path).parent), spec['uid'], spec['gid'])
            regular(g, path, spec['uid'], spec['gid'], spec['mode'])
            require(g.checksum('sha256', path) == spec['sha256'], 'retirement-substituted')
    verify_foreign_trust(g)
    preflight_backend(g)
    return plan


def reconcile_clean(g, script_digest=None):
    """Ubuntu-only environment reconciliation and resumable exact retirement."""
    require(prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode()))[0] == 'ubuntu', 'clean-target')
    identities, declaration = _clean_declaration(g)
    previous = None
    if _present(g, RECORD):
        regular(g, RECORD, 0, 0, 0o600)
        previous = json.loads(g.read_file(RECORD))
    if previous and previous.get('purpose') == PURPOSE:
        plan = _retirement_plan(g, script_digest)
        for path in plan['files']:
            if _present(g, path):
                g.rm(path)
                g.sync()
    else:
        require(previous is None or (type(previous) is dict and set(previous) == {'purpose', 'files', 'pending'}
                and previous['purpose'] == CLEAN_PURPOSE and previous['pending'] is None
                and set(previous['files']) == set(declaration)), 'environment-record')
        require(not any(_present(g, path) for path in
                        (*movable_files(g), TRUST_RECORD, TRUST_FILE, TRUST_PENDING)),
                'clean-fixture-collision')
    desired = {}
    for path, (data, mode, role) in declaration.items():
        account = identities[role]
        spec = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode,
                'uid': account.pw_uid, 'gid': account.pw_gid}
        desired[path] = spec
        ancestor = Path(path).parent
        while not _present(g, str(ancestor)):
            ancestor = ancestor.parent
        directory(g, str(ancestor), spec['uid'], spec['gid'])
        if _present(g, path):
            regular(g, path, spec['uid'], spec['gid'], mode)
            require(previous is not None and previous['files'].get(path) == spec
                    and g.read_file(path) == data, 'environment-collision')
        temporary = path + '.onpc-baseline-new'
        if _present(g, temporary):
            require(previous is not None and previous['files'].get(path) == spec,
                    'environment-staging-collision')
            info = g.lstatns(temporary)
            if info['st_uid'] == info['st_gid'] == 0 and stat.S_IMODE(info['st_mode']) == 0o600:
                regular(g, temporary, 0, 0, 0o600)
            else:
                require(stat.S_IMODE(info['st_mode']) in (0o600, mode),
                        'environment-staging-collision')
                regular(g, temporary, spec['uid'], spec['gid'], stat.S_IMODE(info['st_mode']))
                require(g.read_file(temporary) == data, 'environment-staging-collision')
    # Backend configuration is environment-owned; retire only exact fixture
    # admissions and retain the native file backend and its recovery receipt.
    reconcile_backend(g)
    final = {'purpose': CLEAN_PURPOSE, 'files': desired, 'pending': None}
    if previous != final:
        # The finite desired identities own partially placed environment files
        # if a subsequent write is interrupted. Verification still requires all.
        write_record(g, final)
    for path, (data, mode, role) in declaration.items():
        if _present(g, path):
            continue
        spec = desired[path]
        directory(g, str(Path(path).parent), spec['uid'], spec['gid'], create=True)
        temporary = path + '.onpc-baseline-new'
        if _present(g, temporary):
            g.rm(temporary)
        g.umask(0o077)
        g.write(temporary, data)
        g.chown(0, 0, temporary)
        g.chmod(0o600, temporary)
        require(g.read_file(temporary) == data, 'environment-staging-substituted')
        g.chown(spec['uid'], spec['gid'], temporary)
        g.chmod(mode, temporary)
        g.sync()
        g.mv(temporary, path)
        g.sync()
    verify_clean(g)
    return declaration


def verify_clean(g):
    """Read-only proof of persistent settings and complete movable absence."""
    identities, declaration = _clean_declaration(g)
    regular(g, RECORD, 0, 0, 0o600)
    record = json.loads(g.read_file(RECORD))
    require(type(record) is dict and set(record) == {'purpose', 'files', 'pending'}
            and record['purpose'] == CLEAN_PURPOSE and record['pending'] is None
            and set(record['files']) == set(declaration), 'environment-record')
    for path, (data, mode, role) in declaration.items():
        account = identities[role]
        expected = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode,
                    'uid': account.pw_uid, 'gid': account.pw_gid}
        require(record['files'][path] == expected, 'environment-record')
        directory(g, str(Path(path).parent), account.pw_uid, account.pw_gid)
        regular(g, path, account.pw_uid, account.pw_gid, mode)
        require(g.read_file(path) == data, 'environment-substituted')
    require(not any(_present(g, path) for path in
                    (*movable_files(g), TRUST_RECORD, TRUST_FILE, TRUST_PENDING,
                     *(path + '.onpc-baseline-new' for path in declaration),
                     *(path + '.onpc-baseline-new' for path in movable_files(g)))),
            'clean-fixture-present')
    verify_foreign_trust(g)
    state = preflight_backend(g)
    require(state['complete'] and g.read_file(BACKEND_CONFIG) == bytes.fromhex(state['after_hex'])
            and not _present(g, BACKEND_PENDING), 'backend-incomplete')


def require(value, category='unsafe-or-stale'):
    if not value:
        raise ValueError('baseline:fixtures-' + category + '; run tools/prepare-vm')


def build_payload():
    """Compile only native inputs using the maintained builder and disk scratch."""
    import tempfile
    from tools.test_storage import scratch_directory
    from tests.fixtures.build_test_applications import _compile_native, GUI_SOURCE, GTK_AUTOMATION_SOURCE
    with tempfile.TemporaryDirectory(prefix='baseline-native-', dir=scratch_directory()) as temporary:
        root = Path(temporary)
        result = {role: _compile_native(root, identity=role).read_bytes()
                  for role, *_ in assets.ASSETS}
        result['mechanical'] = _compile_native(root, headless=True).read_bytes()
        for identity in assets.TRUSTED_NATIVE:
            result[identity] = _compile_native(root, headless=True, identity=identity).read_bytes()
        result['trusted-activity'] = _compile_native(root, identity='trusted-activity').read_bytes()
        result['onpc-test-gui.py'] = GUI_SOURCE.read_bytes()
        result['gtk_automation.py'] = GTK_AUTOMATION_SOURCE.read_bytes()
    require(len({result[role] for role, *_ in assets.ASSETS}) == 4)
    require(len({result[key] for key in ('mechanical', *assets.TRUSTED_NATIVE, 'trusted-activity',
                                        *(role for role, *_ in assets.ASSETS))}) == 8)
    return result


def accounts(g):
    rows = [line.split(':') for line in g.read_file('/etc/passwd').decode().splitlines()]
    result = {'system': SimpleNamespace(pw_uid=0, pw_gid=0, pw_dir='/')}
    for role, name in (('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
                       ('parent', 'onpc-parent-jamie')):
        matches = [row for row in rows if row[0] == name]
        require(len(matches) == 1 and len(matches[0]) == 7)
        row = matches[0]
        require(int(row[2]) >= 1000 and row[5] == '/home/' + name)
        result[role] = SimpleNamespace(pw_uid=int(row[2]), pw_gid=int(row[3]), pw_dir=row[5])
    return result


def directory(g, path, uid=0, gid=0, *, create=False):
    for candidate in reversed((Path(path), *Path(path).parents)):
        name = str(candidate)
        if not g.exists(name) and not g.is_symlink(name):
            require(create)
            g.mkdir(name)
            g.chown(uid, gid, name)
            g.chmod(0o755, name)
        info = g.lstatns(name)
        require(g.realpath(name) == name and stat.S_ISDIR(info['st_mode'])
                and info['st_uid'] in (0, uid) and not info['st_mode'] & 0o022)


def regular(g, path, uid, gid, mode):
    info = g.lstatns(path)
    require(g.realpath(path) == path and stat.S_ISREG(info['st_mode'])
            and info['st_nlink'] == 1 and info['st_uid'] == uid
            and info['st_gid'] == gid and stat.S_IMODE(info['st_mode']) == mode)


def owned_trust_file(g, service_gid, *, allow_legacy=False):
    """Strict fixed-fragment identity, with no permission repair on refusal."""
    info = g.lstatns(TRUST_FILE)
    canonical = g.realpath(TRUST_FILE) == TRUST_FILE
    if not (canonical and stat.S_ISREG(info['st_mode']) and info['st_nlink'] == 1
            and info['st_uid'] == 0 and info['st_gid'] in (
                (0, service_gid) if allow_legacy else (service_gid,))
            and stat.S_IMODE(info['st_mode']) == 0o600):
        raise OwnedTrustMetadataError(metadata=info, canonical=canonical, native_gid=service_gid)


def write_record(g, record, path=RECORD):
    """The fixed root-owned transaction file is atomically replaced."""
    temporary = path + '.new'
    if g.exists(temporary) or g.is_symlink(temporary):
        regular(g, temporary, 0, 0, 0o600)
    g.write(temporary, (json.dumps(record, sort_keys=True) + '\n').encode())
    g.chown(0, 0, temporary)
    g.chmod(0o600, temporary)
    g.sync()
    g.mv(temporary, path)
    g.sync()


def _native_open_rule(data):
    """Qualify only the vendor open-only policy, with no execution admissions."""
    require(isinstance(data, bytes) and 0 < len(data) <= 65536, 'native-rules-size')
    lines = [line.split('#', 1)[0].split() for line in data.decode('ascii').splitlines()]
    require([line for line in lines if line] ==
            [['allow', 'perm=open', 'all', ':', 'all']], 'native-rules-semantics')


def _native_rules_source(g):
    native = native_trust_provenance(g)
    require(native['os_id'] == 'ubuntu', 'native-rules-target')
    manifest = g.command(['dpkg-query', '--control-show', 'fapolicyd', 'md5sums'])
    require(isinstance(manifest, str) and 0 < len(manifest.encode()) <= 2 * 1024 * 1024,
            'native-rules-package')
    rows = [line.split() for line in manifest.splitlines()]
    require(all(len(row) == 2 for row in rows), 'native-rules-package')
    sources = [(digest, '/' + path) for digest, path in rows
               if re.fullmatch(NATIVE_RULES_SOURCE_PATTERN, '/' + path)]
    require(len(sources) == 1, 'native-rules-package')
    digest, path = sources[0]
    require(re.fullmatch('[0-9a-f]{32}', digest) is not None
            and g.command(['dpkg-query', '-S', path]).strip() == 'fapolicyd: ' + path,
            'native-rules-package')
    directory(g, str(Path(path).parent))
    info = g.lstatns(path)
    require(stat.S_IMODE(info['st_mode']) in (0o444, 0o644), 'native-rules-source-metadata')
    regular(g, path, 0, 0, stat.S_IMODE(info['st_mode']))
    require(g.filesize(path) <= 65536 and g.checksum('md5', path) == digest,
            'native-rules-package')
    data = g.read_file(path)
    _native_open_rule(data)
    return native, {'path': path, 'md5': digest, 'sha256': hashlib.sha256(data).hexdigest()}, data


def _native_rules_record(g, path, desired):
    regular(g, path, 0, 0, 0o600)
    require(g.filesize(path) <= 8192, 'native-rules-record')
    record = json.loads(g.read_file(path))
    require(type(record) is dict and set(record) == set(desired)
            and record['purpose'] == NATIVE_RULES_PURPOSE
            and type(record['complete']) is bool
            and type(record['source']) is dict and set(record['source']) == {'path', 'md5', 'sha256'}
            and type(record['source']['path']) is str
            and re.fullmatch(NATIVE_RULES_SOURCE_PATTERN, record['source']['path']) is not None
            and record['source']['sha256'] == desired['source']['sha256']
            and record['source']['md5'] == desired['source']['md5']
            and record['target'] == desired['target'], 'native-rules-record')
    native = record['native']
    require(type(native) is dict and set(native) == set(desired['native'])
            and all(native[key] == desired['native'][key] for key in ('os_id', 'package', 'service_gid'))
            and type(native['version']) is str
            and re.fullmatch('[A-Za-z0-9.+:~_-]{1,256}', native['version']) is not None
            and all(type(native[key]) is str and re.fullmatch('[0-9a-f]{64}', native[key]) is not None
                    for key in ('daemon_sha256', 'cli_sha256')), 'native-rules-record')
    return record


def _preflight_native_rules(g):
    """Read the complete finite policy boundary before any publication writes."""
    native, source, data = _native_rules_source(g)
    desired = {'purpose': NATIVE_RULES_PURPOSE, 'complete': True, 'native': native,
               'source': source, 'target': {'uid': 0, 'gid': native['service_gid'],
                                          'mode': 0o644, 'sha256': source['sha256']}}
    directory(g, '/var/lib')
    directory(g, '/etc/fapolicyd')
    previous = (_native_rules_record(g, NATIVE_RULES_RECORD, desired)
                if _present(g, NATIVE_RULES_RECORD) else None)
    receipt_stage = NATIVE_RULES_RECORD + '.new'
    if _present(g, receipt_stage):
        regular(g, receipt_stage, 0, 0, 0o600)
        if previous is None:
            # The first receipt write itself can stop before valid JSON exists.
            # Only an exact private prefix of this qualified intent is retryable;
            # the complete preflight below still forbids any unowned policy.
            intent = (json.dumps(desired | {'complete': False}, sort_keys=True) + '\n').encode()
            require(g.filesize(receipt_stage) <= len(intent)
                    and intent.startswith(g.read_file(receipt_stage)), 'native-rules-record')
    target_present = _present(g, NATIVE_RULES_FILE)
    stage_present = _present(g, NATIVE_RULES_PENDING)
    if _present(g, NATIVE_RULES_ROOT):
        directory(g, NATIVE_RULES_ROOT)
        names = g.find(NATIVE_RULES_ROOT)
        require(isinstance(names, list) and len(names) <= 2
                and all(type(name) is str for name in names), 'native-rules-inventory')
        names = [name.removeprefix('/') for name in names]
        allowed = {Path(NATIVE_RULES_FILE).name, Path(NATIVE_RULES_PENDING).name}
        expected = ({Path(NATIVE_RULES_FILE).name} if target_present else set()) | (
            {Path(NATIVE_RULES_PENDING).name} if stage_present else set())
        require(len(names) == len(set(names)) and set(names) <= allowed
                and set(names) == expected, 'native-rules-inventory')
    else:
        require(not target_present and not stage_present, 'native-rules-inventory')
    require(not _present(g, NATIVE_RULES_LEGACY), 'native-rules-legacy')
    if target_present:
        require(previous is not None, 'native-rules-collision')
        regular(g, NATIVE_RULES_FILE, 0, native['service_gid'], 0o644)
        require(g.filesize(NATIVE_RULES_FILE) == len(data)
                and g.read_file(NATIVE_RULES_FILE) == data, 'native-rules-substituted')
    else:
        require(previous is None or not previous['complete'], 'native-rules-missing')
    if stage_present:
        require(previous is not None and not previous['complete'] and not target_present,
                'native-rules-staging-collision')
        info = g.lstatns(NATIVE_RULES_PENDING)
        mode = stat.S_IMODE(info['st_mode'])
        require(info['st_gid'] in (0, native['service_gid']) and mode in (0o600, 0o644),
                'native-rules-staging-metadata')
        regular(g, NATIVE_RULES_PENDING, 0, info['st_gid'], mode)
        if mode != 0o600:
            require(g.filesize(NATIVE_RULES_PENDING) == len(data)
                    and g.read_file(NATIVE_RULES_PENDING) == data, 'native-rules-staging-substituted')
    if _present(g, NATIVE_RULES_COMPILED):
        # Startup alone owns compiler output. Never adopt unexplained output on
        # first placement; later accept only this same open-only policy.
        require(previous is not None and target_present, 'native-rules-compiled-collision')
        info = g.lstatns(NATIVE_RULES_COMPILED)
        require(info['st_gid'] in (0, native['service_gid'])
                and stat.S_IMODE(info['st_mode']) in (0o600, 0o640, 0o644),
                'native-rules-compiled-metadata')
        regular(g, NATIVE_RULES_COMPILED, 0, info['st_gid'], stat.S_IMODE(info['st_mode']))
        require(g.filesize(NATIVE_RULES_COMPILED) <= 65536, 'native-rules-size')
        _native_open_rule(g.read_file(NATIVE_RULES_COMPILED))
    return previous, desired, data


def reconcile_native_rules(g):
    """Bootstrap the absent Debian admin policy using one verified vendor unit."""
    previous, desired, data = _preflight_native_rules(g)
    if previous == desired:
        require(not _present(g, NATIVE_RULES_RECORD + '.new'), 'native-rules-incomplete')
        return desired
    g.umask(0o077)
    if not _present(g, NATIVE_RULES_FILE):
        write_record(g, desired | {'complete': False}, NATIVE_RULES_RECORD)
        directory(g, NATIVE_RULES_ROOT, 0, desired['native']['service_gid'], create=True)
        if _present(g, NATIVE_RULES_PENDING):
            g.chmod(0o600, NATIVE_RULES_PENDING)
            g.chown(0, 0, NATIVE_RULES_PENDING)
        g.write(NATIVE_RULES_PENDING, data)
        g.chown(0, 0, NATIVE_RULES_PENDING)
        g.chmod(0o600, NATIVE_RULES_PENDING)
        regular(g, NATIVE_RULES_PENDING, 0, 0, 0o600)
        require(g.filesize(NATIVE_RULES_PENDING) == len(data)
                and g.read_file(NATIVE_RULES_PENDING) == data, 'native-rules-staging-substituted')
        g.chown(0, desired['native']['service_gid'], NATIVE_RULES_PENDING)
        g.chmod(0o644, NATIVE_RULES_PENDING)
        regular(g, NATIVE_RULES_PENDING, 0, desired['native']['service_gid'], 0o644)
        require(g.read_file(NATIVE_RULES_PENDING) == data, 'native-rules-staging-substituted')
        g.sync()
        g.mv(NATIVE_RULES_PENDING, NATIVE_RULES_FILE)
        g.sync()
        regular(g, NATIVE_RULES_FILE, 0, desired['native']['service_gid'], 0o644)
        require(g.read_file(NATIVE_RULES_FILE) == data, 'native-rules-substituted')
    write_record(g, desired, NATIVE_RULES_RECORD)
    return verify_native_rules(g)


def verify_native_rules(g):
    """Read-only offline policy/provenance proof; never initialize the daemon."""
    previous, desired, _ = _preflight_native_rules(g)
    require(previous == desired and _present(g, NATIVE_RULES_FILE)
            and not any(_present(g, path) for path in
                        (NATIVE_RULES_PENDING, NATIVE_RULES_RECORD + '.new')),
            'native-rules-incomplete')
    return previous


def declared_files(g, identities, source_hashes=None, *, include_native_policy=True):
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    declaration = assets.files(identities) | assets.automatic_update_files(os_id)
    if os_id == 'fedora' and include_native_policy:
        if source_hashes is None:
            recorded = json.loads(g.read_file(RECORD))['files']
            require(type(recorded) is dict)
            source_hashes = {}
            for source, (path, _) in native_assets.source_destinations(identities['other'].pw_dir).items():
                if source in native_assets.runtime_sources():
                    require(type(recorded.get(path)) is dict and 'sha256' in recorded[path])
                    source_hashes[source] = recorded[path]['sha256']
        rules = native_assets.native_policy_files(source_hashes,
            (identities['child'].pw_uid, identities['other'].pw_uid))
        declaration.update({path: (data, 0o644, 'native-policy') for path, data in rules.items()})
    return declaration


def fixture_accounts(g):
    identities = accounts(g)
    # Native tmpfiles restores this fixed group recursively on every boot.
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    if os_id == 'fedora':
        identities['native-policy'] = SimpleNamespace(pw_uid=0,
            pw_gid=native_trust_provenance(g)['service_gid'])
    return identities


def verify_native_policy_sources(g, identities, previous=None, *, include_native_policy=True):
    """Product-free offline preflight refuses customized native rule policy."""
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    if os_id != 'fedora':
        return
    gid = identities['native-policy'].pw_gid
    def read(path, mode, group):
        directory(g, str(Path(path).parent))
        regular(g, path, 0, 0 if group == 'root' else gid, mode)
        require(g.filesize(path) <= 2 * 1024 * 1024, 'native-policy-oversized')
        return g.read_file(path)
    stock = native_assets.native_stock_rules(g.command(['rpm', '-q', '--queryformat',
        native_assets.NATIVE_RULE_MANIFEST, 'fapolicyd']), read)
    root = '/etc/fapolicyd/rules.d'
    directory(g, root)
    names = g.find(root)
    require(isinstance(names, list) and len(names) <= 128, 'native-policy-inventory')
    paths = [root + '/' + name.removeprefix('/') for name in names]
    permitted = set(stock) | (set(native_assets.NATIVE_POLICY_PATHS) if include_native_policy else set())
    if include_native_policy and previous and previous['pending'] in native_assets.NATIVE_POLICY_PATHS:
        permitted.add(previous['pending'] + '.onpc-baseline-new')
    require(len(paths) == len(set(paths)) and set(stock) <= set(paths)
            and set(paths) <= permitted, 'native-policy-inventory')
    require(not g.exists('/etc/fapolicyd/fapolicyd.rules')
            and not g.is_symlink('/etc/fapolicyd/fapolicyd.rules'), 'native-policy-legacy')
    for path, (data, mode) in stock.items():
        require(read(path, mode, 'fapolicyd') == data, 'native-policy-modified')


def reconcile(g, payload):
    """Repeat without writes; atomic owned upgrades and interrupted retries."""
    keys = ('mechanical', *assets.TRUSTED_NATIVE, 'trusted-activity',
            *(role for role, *_ in assets.ASSETS))
    require(all(isinstance(payload.get(key), bytes) and payload[key] for key in keys)
            and len({payload[key] for key in keys}) == len(keys))
    # Appliance-created staging files stay private even if writing is interrupted
    # before chmod. Guest modes are set explicitly before each atomic placement.
    g.umask(0o077)
    identities = fixture_accounts(g)
    source_keys = dict(zip(native_assets.executable_sources(),
                           (asset[0] for asset in native_assets.ASSETS)))
    source_keys.update({source: source.rsplit('/', 1)[-1] for source in native_assets.gui_sources()})
    source_hashes = {source: hashlib.sha256(payload[key]).hexdigest()
                     for source, key in source_keys.items()}
    declaration = declared_files(g, identities, source_hashes)
    desired = {}
    contents = {}
    for path, (source, mode, role) in declaration.items():
        data = source if isinstance(source, bytes) else payload[source]
        account = identities[role]
        desired[path] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode,
                         'uid': account.pw_uid, 'gid': account.pw_gid}
        contents[path] = data
    directory(g, '/var/lib')
    previous = {'purpose': PURPOSE, 'files': {}, 'pending': None}
    if g.exists(RECORD) or g.is_symlink(RECORD):
        regular(g, RECORD, 0, 0, 0o600)
        previous = json.loads(g.read_file(RECORD))
        require(set(previous) == {'purpose', 'files', 'pending'} and previous['purpose'] == PURPOSE
                and set(previous['files']) <= set(desired)
                and (previous['pending'] is None or previous['pending'] in desired))
    trusted = preflight_trusted(g)
    verify_native_policy_sources(g, identities, previous)
    # Preflight the whole finite set before any mutation, including unrelated collisions.
    for path, spec in desired.items():
        ancestor = Path(path).parent
        while not g.exists(str(ancestor)) and not g.is_symlink(str(ancestor)):
            ancestor = ancestor.parent
        directory(g, str(ancestor), spec['uid'], spec['gid'])
        if g.exists(path) or g.is_symlink(path):
            regular(g, path, spec['uid'], spec['gid'], spec['mode'])
            old = previous['files'].get(path)
            require(old is not None and set(old) == set(spec)
                    and {k: old[k] for k in ('mode', 'uid', 'gid')} ==
                        {k: spec[k] for k in ('mode', 'uid', 'gid')}
                    and g.checksum('sha256', path) in (old['sha256'], spec['sha256']))
        temporary = path + '.onpc-baseline-new'
        if g.exists(temporary) or g.is_symlink(temporary):
            require(previous['pending'] == path)
            info = g.lstatns(temporary)
            if info['st_uid'] == 0 and stat.S_IMODE(info['st_mode']) == 0o600:
                regular(g, temporary, 0, 0, 0o600)
            else:
                require(stat.S_IMODE(info['st_mode']) in (0o600, spec['mode']))
                regular(g, temporary, spec['uid'], spec['gid'], stat.S_IMODE(info['st_mode']))
                require(g.checksum('sha256', temporary) == spec['sha256'])
    record = {'purpose': PURPOSE, 'files': dict(previous['files']), 'pending': previous['pending']}
    for path, spec in desired.items():
        if g.exists(path) and g.checksum('sha256', path) == spec['sha256']:
            continue
        directory(g, str(Path(path).parent), spec['uid'], spec['gid'], create=True)
        record['pending'] = path
        # Retain the old digest until atomic replacement has completed.
        record['files'].setdefault(path, spec)
        write_record(g, record)
        temporary = path + '.onpc-baseline-new'
        g.write(temporary, contents[path])
        g.chown(0, 0, temporary)
        g.chmod(0o600, temporary)
        require(g.checksum('sha256', temporary) == spec['sha256'])
        g.chown(spec['uid'], spec['gid'], temporary)
        g.chmod(spec['mode'], temporary)
        g.sync()
        g.mv(temporary, path)
        record['files'][path] = spec
        record['pending'] = None
        write_record(g, record)
    final = {'purpose': PURPOSE, 'files': desired, 'pending': None}
    if previous != final:
        write_record(g, final)
    reconcile_trusted(g, trusted)
    verify(g)
    return declaration


def verify(g, script_digest=None):
    """Inspect current fixtures or an unchanged recorded pre-admission baseline.

    Restoration passes the recorded preparation digest. A previous Fedora
    baseline may omit both new admissions solely for that read-only inspection;
    new acquisition independently requires the current preparation digest.
    """
    regular(g, RECORD, 0, 0, 0o600)
    record = json.loads(g.read_file(RECORD))
    require(type(record) is dict and set(record) == {'purpose', 'files', 'pending'}
            and record['purpose'] == PURPOSE and record['pending'] is None
            and type(record['files']) is dict)
    identities = fixture_accounts(g)
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    legacy = (os_id == 'fedora' and type(script_digest) is str
              and re.fullmatch('[0-9a-f]{64}', script_digest) is not None
              and script_digest != prepare_vm.preparation_digest()
              and not set(native_assets.NATIVE_POLICY_PATHS) & set(record['files']))
    if legacy:
        require(not any(g.exists(path) or g.is_symlink(path)
                        for target in native_assets.NATIVE_POLICY_PATHS
                        for path in (target, target + '.onpc-baseline-new')),
                'legacy-native-policy-collision')
    declaration = declared_files(g, identities, include_native_policy=not legacy)
    verify_native_policy_sources(g, identities, include_native_policy=not legacy)
    require(set(record['files']) == set(declaration))
    for path, (source, mode, role) in declaration.items():
        spec = record['files'][path]
        account = identities[role]
        require(set(spec) == {'sha256', 'mode', 'uid', 'gid'} and spec['mode'] == mode
                and spec['uid'] == account.pw_uid and spec['gid'] == account.pw_gid)
        directory(g, str(Path(path).parent), account.pw_uid, account.pw_gid)
        regular(g, path, account.pw_uid, account.pw_gid, mode)
        require(g.checksum('sha256', path) == spec['sha256'])
        if isinstance(source, bytes):
            require(g.read_file(path) == source)
    verify_trusted(g, script_digest)


def native_trust_provenance(g):
    """Read native package identity and both exact tool payload identities."""
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    # Native init/fapolicyd-tmpfiles.conf has `Z /etc/fapolicyd - root
    # fapolicyd -`: boot recursively restores this group without changing modes.
    # Resolve only that fixed system group; never adopt an observed fragment gid.
    directory(g, '/etc')
    group_info = g.lstatns('/etc/group')
    require(group_info['st_uid'] == 0 and not group_info['st_mode'] & 0o022,
            'native-service-group')
    regular(g, '/etc/group', 0, group_info['st_gid'], stat.S_IMODE(group_info['st_mode']))
    require(g.filesize('/etc/group') <= 1024 * 1024, 'native-service-group')
    groups = [line.split(':') for line in g.read_file('/etc/group').decode('utf-8').splitlines()
              if line.split(':', 1)[0] == 'fapolicyd']
    require(len(groups) == 1 and len(groups[0]) == 4 and groups[0][2].isascii()
            and groups[0][2].isdigit() and 0 < int(groups[0][2]) < 2 ** 32,
            'native-service-group')
    service_gid = int(groups[0][2])
    tools = native_tool_paths(os_id)
    for path in tools.values():
        directory(g, str(Path(path).parent))
        regular(g, path, 0, 0, 0o755)
    if os_id == 'fedora':
        alias = '/usr/sbin'
        require(g.exists(alias) or g.is_symlink(alias), 'native-tool-alias')
        info = g.lstatns(alias)
        require(stat.S_ISLNK(info['st_mode']) and info['st_uid'] == info['st_gid'] == 0
                and g.realpath(alias) == '/usr/bin', 'native-tool-alias')
        for path in tools.values():
            require(g.realpath(alias + '/' + Path(path).name) == path, 'native-tool-alias')
    if os_id == 'ubuntu':
        for path in tools.values():
            require(g.command(['dpkg-query', '-S', path]).strip() == 'fapolicyd: ' + path)
        identity = g.command(['dpkg-query', '-W', '-f=${Package} ${Version}\n', 'fapolicyd'])
        manifest = g.command(['dpkg-query', '--control-show', 'fapolicyd', 'md5sums'])
        require(isinstance(manifest, str) and 0 < len(manifest.encode()) <= 2 * 1024 * 1024)
        algorithm, width = 'md5', 32
        rows = [line.split() for line in manifest.splitlines()]
        require(all(len(row) == 2 for row in rows))
        checksums = {path: [row[0] for row in rows if row[1] == path.lstrip('/')]
                     for path in tools.values()}
    else:
        for path in tools.values():
            require(g.command(['rpm', '-qf', '--queryformat', '%{NAME}', path]).strip() == 'fapolicyd')
        identity = g.command(['rpm', '-q', '--queryformat', '%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}\n', 'fapolicyd'])
        manifest = g.command(['rpm', '-q', '--queryformat',
                              '%{FILEDIGESTALGO}\n[%{FILENAMES}\t%{FILEDIGESTS}\n]', 'fapolicyd'])
        require(isinstance(manifest, str) and 0 < len(manifest.encode()) <= 2 * 1024 * 1024)
        lines = manifest.splitlines()
        require(lines and lines[0] == '8')
        algorithm, width = 'sha256', 64
        rows = [line.split('\t') for line in lines[1:]]
        require(all(len(row) == 2 for row in rows))
        checksums = {path: [row[1] for row in rows if row[0] == path] for path in tools.values()}
    require(all(len(values) == 1 and re.fullmatch('[0-9a-f]{' + str(width) + '}', values[0]) is not None
                and g.checksum(algorithm, path) == values[0]
                for path, values in checksums.items()))
    require(isinstance(identity, str) and 0 < len(identity) <= 256)
    fields = identity.split()
    require(len(fields) == 2 and fields[0] == 'fapolicyd'
            and re.fullmatch('[A-Za-z0-9.+:~_-]+', fields[1]) is not None)
    return {'os_id': os_id, 'package': fields[0], 'version': fields[1],
            'service_gid': service_gid,
            'daemon_sha256': g.checksum('sha256', tools['daemon']),
            'cli_sha256': g.checksum('sha256', tools['cli'])}


def preflight_trusted(g):
    """Audit trust collisions before reconciliation writes any declared file."""
    directory(g, '/etc/fapolicyd/trust.d')
    native = native_trust_provenance(g)
    for path in (RECORD + '.new', TRUST_RECORD + '.new'):
        if g.exists(path) or g.is_symlink(path):
            regular(g, path, 0, 0, 0o600)
    transaction = {'purpose': TRUST_PURPOSE, 'complete': None, 'pending': None}
    if g.exists(TRUST_RECORD) or g.is_symlink(TRUST_RECORD):
        regular(g, TRUST_RECORD, 0, 0, 0o600)
        transaction = json.loads(g.read_file(TRUST_RECORD))
        require(isinstance(transaction, dict) and set(transaction) == {'purpose', 'complete', 'pending'}
                and transaction['purpose'] == TRUST_PURPOSE)
        for key in ('complete', 'pending'):
            if transaction[key] is not None:
                validate_trusted_shape(transaction[key], pending=key == 'pending', allow_legacy=True)
    if g.exists(TRUST_FILE) or g.is_symlink(TRUST_FILE):
        owned_trust_file(g, native['service_gid'], allow_legacy=True)
        digest = g.checksum('sha256', TRUST_FILE)
        matches = [state for state in (transaction['complete'], transaction['pending'])
                   if state and state['trust_file_sha256'] == digest]
        require(len(matches) >= 1)
        require(all('service_gid' not in state['native'] or
                    state['native']['service_gid'] == native['service_gid'] for state in matches),
                'native-service-group')
        owned_trust_file(g, native['service_gid'], allow_legacy=any(
            'trust_file_metadata' not in state for state in matches))
        require(any(trust_entries(g.read_file(TRUST_FILE)) == {
            path: {key: spec[key] for key in ('size', 'sha256')}
            for path, spec in state['files'].items()} for state in matches))
    else:
        require(transaction['complete'] is None)
    if g.exists(TRUST_PENDING) or g.is_symlink(TRUST_PENDING):
        require(transaction['pending'] is not None)
        staged = g.lstatns(TRUST_PENDING)
        gid = staged['st_gid']
        regular(g, TRUST_PENDING, 0, gid, 0o600)
        # The native recursive tmpfiles rule can also change an intent-owned
        # partial stage's group on the public retry boot. Mode0600 remains
        # private. Its bytes are discarded and regenerated, never adopted.
        require(gid in (0, native['service_gid']), 'trust-staging-group')
    verify_foreign_trust(g)
    preflight_backend(g)
    return transaction


def verify_foreign_trust(g, *, inactive=False):
    """Refuse duplicate exact targets in any foreign file-backend fragment.

    Native add deduplicates across the complete file backend, so silently
    adopting another fragment could falsely attribute its trust to our record.
    Audit the native trust.d traversal and legacy file without changing them.
    """
    root = str(Path(TRUST_FILE).parent)
    directory(g, root)
    names = g.find(root)
    require(isinstance(names, list) and len(names) <= 4096)
    candidates = ['/etc/fapolicyd/fapolicyd.trust']
    seen = set()
    for name in names:
        # find0 strips the starting directory but retains its separator; the
        # client find implementation forwards that optional leading slash.
        # Interpret only that one separator, never an arbitrary absolute path.
        require(isinstance(name, str), 'trust-enumeration-unsafe')
        name = name.removeprefix('/')
        require(name and '\x00' not in name and len(name) <= 4096
                and all(part not in ('', '.', '..') for part in name.split('/'))
                and name not in seen, 'trust-enumeration-unsafe')
        seen.add(name)
        path = root + '/' + name
        require(g.exists(path) or g.is_symlink(path), 'trust-enumeration-unsafe')
        if path in (TRUST_FILE, TRUST_PENDING):
            continue
        if g.is_dir(path):
            directory(g, path)
        else:
            candidates.append(path)
    targets = set(assets.trusted_file_modes()) | {
        assets.NATIVE[key][0] for key in ('command', 'whitespace')} | {
        assets.PREFIX + '/' + asset[1] for asset in assets.ASSETS} | set(assets.legacy_executable_paths())
    for path in candidates:
        if not g.exists(path) and not g.is_symlink(path):
            continue
        directory(g, str(Path(path).parent))
        info = g.lstatns(path)
        mode = stat.S_IMODE(info['st_mode'])
        canonical = g.realpath(path) == path
        if not (canonical and stat.S_ISREG(info['st_mode']) and info['st_nlink'] == 1
                and info['st_uid'] == 0 and mode in (0o600, 0o644)):
            raise ForeignTrustMetadataError(
                legacy=path == '/etc/fapolicyd/fapolicyd.trust', metadata=info, canonical=canonical)
        require(g.filesize(path) <= 2 * 1024 * 1024, 'foreign-trust-oversized')
        # Vendor configuration may be root:fapolicyd (upstream RPM metadata).
        # We only inspect these nonwritable root-owned files; their group grants
        # no write authority and neither their bytes nor ownership are adopted.
        regular(g, path, 0, info['st_gid'], mode)
        for line in g.read_file(path).decode('utf-8').splitlines():
            # Native trust rows end with size and digest. Split from the right
            # so the original whitespace witness retains its complete path.
            fields = line.rstrip().rsplit(None, 2)
            if fields and not line.startswith('#'):
                require(fields[0] not in targets)
            if inactive:
                require(not line.strip() or line.lstrip().startswith('#'), 'inactive-foreign-trust')


def preflight_backend(g):
    """Validate the exact config and any durable owned backend transaction."""
    directory(g, str(Path(BACKEND_CONFIG).parent))
    info = g.lstatns(BACKEND_CONFIG)
    metadata = {'mode': stat.S_IMODE(info['st_mode']), 'uid': info['st_uid'], 'gid': info['st_gid']}
    require(metadata['uid'] == 0 and metadata['mode'] in (0o600, 0o640, 0o644), 'backend-metadata')
    regular(g, BACKEND_CONFIG, 0, metadata['gid'], metadata['mode'])
    require(g.filesize(BACKEND_CONFIG) <= 65536, 'backend-oversized')
    current = g.read_file(BACKEND_CONFIG)
    os_id, _ = prepare_vm.release_identity(prepare_vm.parse_os_release(
        g.read_file('/etc/os-release').decode('utf-8')))
    after = file_backend_config(current, os_id)
    state = {'purpose': BACKEND_PURPOSE, 'os_id': os_id, 'before_hex': current.hex(),
             'after_hex': after.hex(), 'metadata': metadata, 'complete': False}
    if g.exists(BACKEND_RECORD) or g.is_symlink(BACKEND_RECORD):
        regular(g, BACKEND_RECORD, 0, 0, 0o600)
        require(g.filesize(BACKEND_RECORD) <= 300000, 'backend-record-oversized')
        state = validate_backend_record(json.loads(g.read_file(BACKEND_RECORD)))
        require(state['os_id'] == os_id and state['metadata'] == metadata
                and current in (bytes.fromhex(state['before_hex']), bytes.fromhex(state['after_hex'])),
                'backend-substituted')
    if g.exists(BACKEND_RECORD + '.new') or g.is_symlink(BACKEND_RECORD + '.new'):
        regular(g, BACKEND_RECORD + '.new', 0, 0, 0o600)
    if g.exists(BACKEND_PENDING) or g.is_symlink(BACKEND_PENDING):
        require(g.exists(BACKEND_RECORD) and not state['complete'], 'backend-staging-collision')
        require(current != bytes.fromhex(state['after_hex']), 'backend-staging-ambiguous')
        staged = g.lstatns(BACKEND_PENDING)
        mode = stat.S_IMODE(staged['st_mode'])
        require(staged['st_uid'] == 0 and staged['st_gid'] in (0, metadata['gid'])
                and mode in (0o600, metadata['mode']), 'backend-staging-metadata')
        regular(g, BACKEND_PENDING, 0, staged['st_gid'], mode)
        if mode != 0o600:
            require(g.read_file(BACKEND_PENDING) == bytes.fromhex(state['after_hex']), 'backend-staging-substituted')
    if file_backend_config(current, os_id) != current:
        # Existing fixture fragments have already passed their ownership/byte
        # preflight. Never enable unrelated records in the inactive file source.
        verify_foreign_trust(g, inactive=True)
    return validate_backend_record(state)


def reconcile_backend(g):
    """Publish a durable config intent before enabling exact native file trust."""
    state = preflight_backend(g)
    current = g.read_file(BACKEND_CONFIG)
    after = bytes.fromhex(state['after_hex'])
    if not state['complete'] or current != after:
        state['complete'] = False
        write_record(g, state, BACKEND_RECORD)
        if current != after:
            # Restrict an owned leftover before rewriting it, so a partial write
            # remains private and retryable even with a vendor config group.
            if g.exists(BACKEND_PENDING):
                g.chmod(0o600, BACKEND_PENDING)
                g.chown(0, 0, BACKEND_PENDING)
            g.write(BACKEND_PENDING, after)
            g.chown(0, 0, BACKEND_PENDING)
            g.chmod(0o600, BACKEND_PENDING)
            require(g.read_file(BACKEND_PENDING) == after, 'backend-staging-substituted')
            metadata = state['metadata']
            g.chown(0, metadata['gid'], BACKEND_PENDING)
            g.chmod(metadata['mode'], BACKEND_PENDING)
            g.sync()
            g.mv(BACKEND_PENDING, BACKEND_CONFIG)
            g.sync()
        # The public API checks its fixed live path; this guest is powered off.
        # A failed check retains the owned before/after intent for safe retry.
        g.command([native_tool_paths(state['os_id'])['cli'], '--check-config'])
        state['complete'] = True
        write_record(g, state, BACKEND_RECORD)
    else:
        g.command([native_tool_paths(state['os_id'])['cli'], '--check-config'])
    metadata = state['metadata']
    backend = {'config_sha256': hashlib.sha256(after).hexdigest(),
               'record_sha256': hashlib.sha256(g.read_file(BACKEND_RECORD)).hexdigest(),
               **metadata, 'sources': file_backend_sources(after, state['os_id'])}
    return validate_backend_provenance(backend, g.read_file(BACKEND_CONFIG),
                                       g.read_file(BACKEND_RECORD), state['os_id'])


def reconcile_trusted(g, transaction):
    """Generate the finite file trust inventory through the native supported API.

    The guest is powered off. No daemon update, rule change or directory trust
    is needed: its next boot loads the atomically published trust fragment.
    A durable intent owns the private staging file across interrupted CLI writes.
    """
    backend = reconcile_backend(g)
    fixture_record = g.read_file(RECORD)
    fixture = json.loads(fixture_record)
    desired = {'purpose': TRUST_PURPOSE,
               'preparation_script_sha256': prepare_vm.preparation_digest(),
               'fixture_record_sha256': hashlib.sha256(fixture_record).hexdigest(),
               'files': {path: fixture['files'][path] | {'size': g.filesize(path)}
                         for path in assets.trusted_file_modes()},
               'native': native_trust_provenance(g), 'backend': backend, 'trust_file_sha256': None}
    desired['trust_file_metadata'] = {'mode': 0o600, 'uid': 0,
                                    'gid': desired['native']['service_gid']}
    old = transaction['complete']
    pending = transaction['pending']
    if (pending and pending['trust_file_sha256'] is not None and g.exists(TRUST_FILE)
            and g.checksum('sha256', TRUST_FILE) == pending['trust_file_sha256']
            and ('trust_file_metadata' not in pending or
                 g.lstatns(TRUST_FILE)['st_gid'] == pending['trust_file_metadata']['gid'])):
        # Atomic publication can precede the completed receipt. Preserve that
        # preflight-verified publication as the complete identity in the next
        # intent; a second interruption must not erase its only durable proof.
        old = pending
    if old and transaction['pending'] is None and all(
            desired[key] == old.get(key) for key in ('files', 'native', 'backend', 'trust_file_metadata')):
        # Changes elsewhere in the baseline only refresh the provenance binding;
        # the matching native fragment and payloads keep their file identities.
        desired['trust_file_sha256'] = old['trust_file_sha256']
        if desired != old:
            write_record(g, {'purpose': TRUST_PURPOSE, 'complete': desired,
                             'pending': None}, TRUST_RECORD)
        return
    # Commit the desired payload identities before creating/truncating staging.
    # A fully generated prior stage may already carry its final native group.
    # Return it to private root ownership before replacing the only digest proof
    # with a new intent; a second interruption must remain safely retryable.
    if g.exists(TRUST_PENDING):
        g.chown(0, 0, TRUST_PENDING)
    transaction = {'purpose': TRUST_PURPOSE, 'complete': old, 'pending': desired}
    write_record(g, transaction, TRUST_RECORD)
    # Native add deduplicates across *all* fragments. Seed an owned existing
    # fragment and update only this staging file on updates and published retry.
    published = g.exists(TRUST_FILE)
    g.write(TRUST_PENDING, g.read_file(TRUST_FILE) if published else b'')
    g.chown(0, 0, TRUST_PENDING)
    g.chmod(0o600, TRUST_PENDING)
    existing = trust_entries(g.read_file(TRUST_PENDING))
    for path in desired['files']:
        g.command([native_tool_paths(desired['native']['os_id'])['cli'],
                   '--file', 'update' if path in existing else 'add', path,
                   '--trust-file', Path(TRUST_PENDING).name])
        regular(g, TRUST_PENDING, 0, 0, 0o600)
    require(trust_entries(g.read_file(TRUST_PENDING)) == {
        path: {key: spec[key] for key in ('size', 'sha256')}
        for path, spec in desired['files'].items()})
    desired['trust_file_sha256'] = g.checksum('sha256', TRUST_PENDING)
    validate_trusted_record(desired, fixture_record, prepare_vm.preparation_digest())
    # Record the generated fragment's exact bytes before atomic publication.
    write_record(g, transaction, TRUST_RECORD)
    g.chown(0, desired['native']['service_gid'], TRUST_PENDING)
    g.sync()
    g.mv(TRUST_PENDING, TRUST_FILE)
    g.sync()
    write_record(g, {'purpose': TRUST_PURPOSE, 'complete': desired, 'pending': None}, TRUST_RECORD)


def verify_trusted(g, script_digest=None):
    """Read-only baseline verification; active daemon trust is a separate probe."""
    regular(g, TRUST_RECORD, 0, 0, 0o600)
    transaction = json.loads(g.read_file(TRUST_RECORD))
    require(isinstance(transaction, dict) and set(transaction) == {'purpose', 'complete', 'pending'}
            and transaction['purpose'] == TRUST_PURPOSE and transaction['pending'] is None)
    record = validate_trusted_record(transaction['complete'], g.read_file(RECORD),
                                    script_digest or prepare_vm.preparation_digest())
    require(not g.exists(TRUST_PENDING) and not g.is_symlink(TRUST_PENDING))
    directory(g, str(Path(TRUST_FILE).parent))
    owned_trust_file(g, record['native']['service_gid'])
    require(g.checksum('sha256', TRUST_FILE) == record['trust_file_sha256'])
    require(trust_entries(g.read_file(TRUST_FILE)) == {
        path: {key: spec[key] for key in ('size', 'sha256')}
        for path, spec in record['files'].items()})
    for path, spec in record['files'].items():
        directory(g, str(Path(path).parent))
        regular(g, path, 0, 0, assets.trusted_file_modes()[path])
        require(g.checksum('sha256', path) == spec['sha256'] and g.filesize(path) == spec['size'])
    require(native_trust_provenance(g) == record['native'])
    regular(g, BACKEND_RECORD, 0, 0, 0o600)
    backend = record['backend']
    require(not g.exists(BACKEND_PENDING) and not g.is_symlink(BACKEND_PENDING), 'backend-incomplete')
    directory(g, str(Path(BACKEND_CONFIG).parent))
    regular(g, BACKEND_CONFIG, backend['uid'], backend['gid'], backend['mode'])
    validate_backend_provenance(backend, g.read_file(BACKEND_CONFIG),
                                g.read_file(BACKEND_RECORD), record['native']['os_id'])
    verify_foreign_trust(g)
    return record
