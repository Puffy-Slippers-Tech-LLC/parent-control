"""Read-only native fixture verification and the bounded earlier-release control.

Preparation owns placement and trust admission. This installed qualification
only verifies the captured inputs and exercises public broker operations.
"""

import hashlib
import grp
import json
import os
from pathlib import Path
import pwd
import stat

import system_guest as guest
from system_assertions import accepted
from system_caller import FixturePassword, PersistentCaller, TextAgent
from system_enforcement import (
    TRUSTED_VARIANTS, call, native_paths, observe_launch, provision_native,
    record_execution_backend, record_rules,
)
try:
    from native_trust import (
        TRUST_FILE, TRUST_RECORD, TRUST_PENDING, TRUST_PURPOSE,
        BACKEND_CONFIG, BACKEND_RECORD, BACKEND_PENDING,
        native_tool_paths, trust_entries, validate_trusted_record, validate_backend_provenance,
        database_row,
    )
except ImportError:
    from tests.fixtures.native_trust import (
        TRUST_FILE, TRUST_RECORD, TRUST_PENDING, TRUST_PURPOSE,
        BACKEND_CONFIG, BACKEND_RECORD, BACKEND_PENDING,
        native_tool_paths, trust_entries, validate_trusted_record, validate_backend_provenance,
        database_row,
    )

FIXTURE_RECORD = Path('/var/lib/onpc-baseline-fixtures.json')


def root_file(path, mode, *, gid=0, limit=262144):
    """Read a small fixed root-owned file without following a substituted link."""
    path = Path(path)
    for parent in path.parents:
        info = parent.lstat()
        guest.require(stat.S_ISDIR(info.st_mode) and info.st_uid == 0
                      and not info.st_mode & 0o022, 'trusted-fixtures:unsafe-parent')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        guest.require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                      and info.st_uid == 0 and info.st_gid == gid
                      and stat.S_IMODE(info.st_mode) == mode and info.st_size <= limit,
                      'trusted-fixtures:record-metadata')
        raw = stream.read(limit + 1)
        guest.require(len(raw) <= limit, 'trusted-fixtures:record-size')
        return raw


def validate_database(raw, files, untrusted):
    """Require exact filedb rows, including refusal of duplicate/wrong rows."""
    paths = set(files) | set(untrusted)
    rows = {path: [] for path in paths}
    for line in raw.splitlines():
        fields = database_row(line)
        if fields is not None and fields[1] in paths:
            rows[fields[1]].append(fields)
    for path, spec in files.items():
        guest.require(rows[path] == [['filedb', path, str(spec['size']), spec['sha256']]],
                      'trusted-fixtures:native-trust-mismatch')
    guest.require(all(not rows[path] for path in untrusted),
                  'trusted-fixtures:untrusted-input-changed')


def verify_runtime_trust(variant, preparation):
    """Audit Fedora removal's attempt-owned hard witness, not retired captures.

    The shared provisioner owns placement/readiness. Keep an independent
    comparison with its frozen build, exact native admission and backend/tool
    verification here before the case changes product policy.
    """
    guest.require(variant == 'trusted-hard' and guest.package_path().suffix == '.rpm'
                  and preparation['guest'].get('os_id') == 'fedora'
                  and preparation['guest'].get('version') == '44',
                  'trusted-fixtures:runtime-selection')
    target, _, _ = native_paths(variant)
    data = root_file(target, 0o755, limit=16777216)
    source = guest.PAYLOAD / 'fixtures/mechanical/identity-trusted-hard'
    guest.require(source.is_file() and not source.is_symlink()
                  and hashlib.sha256(data).hexdigest() == guest.sha(source),
                  'trusted-fixtures:payload-changed')
    files = {str(target): {'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}}
    service_gid = grp.getgrnam('fapolicyd').gr_gid
    trust = root_file('/etc/fapolicyd/trust.d/onpc-fixture-runtime.trust',
                      0o600, gid=service_gid)
    guest.require(trust_entries(trust) == files, 'trusted-fixtures:trust-fragment')
    guest.require(not os.path.lexists(BACKEND_PENDING)
                  and not os.path.lexists(TRUST_PENDING), 'trusted-fixtures:unfinished-backend')
    try:
        from native_trust import validate_backend_record, file_backend_config
    except ImportError:
        from tests.fixtures.native_trust import validate_backend_record, file_backend_config
    backend = validate_backend_record(json.loads(root_file(BACKEND_RECORD, 0o600, limit=300000)))
    metadata = backend['metadata']
    config = root_file(BACKEND_CONFIG, metadata['mode'], gid=metadata['gid'], limit=65536)
    guest.require(backend['complete'] and backend['os_id'] == 'fedora'
                  and bytes.fromhex(backend['after_hex']) == config
                  and file_backend_config(config, 'fedora') == config,
                  'trusted-fixtures:native-backend')
    checksums = guest.commands.run(['rpm', '-q', '--queryformat',
        '%{FILEDIGESTALGO}\n[%{FILENAMES}\t%{FILEDIGESTS}\n]', 'fapolicyd'],
        timeout=120, merge_stderr=False).decode().splitlines()
    guest.require(bool(checksums) and checksums[0] == '8', 'trusted-fixtures:native-tool-changed')
    rows = [line.split('\t') for line in checksums[1:]]
    guest.require(all(len(row) == 2 for row in rows), 'trusted-fixtures:native-tool-changed')
    for executable in native_tool_paths('fedora').values():
        guest.require((Path('/usr/sbin') / Path(executable).name).resolve() == Path(executable),
                      'trusted-fixtures:native-tool-alias')
        tool = root_file(executable, 0o755, limit=16777216)
        guest.require(guest.run(['rpm', '-qf', '--queryformat', '%{NAME}', executable]) == 'fapolicyd'
                      and [row[1] for row in rows if row[0] == executable]
                          == [hashlib.sha256(tool).hexdigest()], 'trusted-fixtures:native-tool-changed')
    guest.run([native_tool_paths('fedora')['cli'], '--check-config'])
    guest.require(guest.run(['systemctl', 'is-active', 'fapolicyd.service']) == 'active',
                  'trusted-fixtures:native-service')
    # Clean captures contain no legacy mechanical admissions. Preserve the
    # negative controls instead of requiring their retired payload records.
    untrusted = [str(native_paths(name)[0]) for name in ('command', 'whitespace')]
    database = guest.run([native_tool_paths('fedora')['cli'], '--dump-db'])
    validate_database(database, files, untrusted)
    return {'files': files, 'backend': backend}


def verify_trust(*, variant=None):
    """Verify exact prepared provenance and current native trust; never repair."""
    marker = guest.guard()
    guest.enable_diagnostics()
    preparation = json.loads(root_file(guest.BASELINE, 0o600))
    if variant is not None and preparation.get('schema_version') == 4:
        return {'baseline_sha256': marker['baseline_sha256'],
                'preparation_sha256': marker['preparation_sha256'],
                'selected_inputs_sha256': marker['selected_inputs_sha256'],
                'provenance': verify_runtime_trust(variant, preparation)}
    transaction = json.loads(root_file(TRUST_RECORD, 0o600))
    guest.require(isinstance(transaction, dict) and set(transaction) == {
        'purpose', 'complete', 'pending'} and transaction['purpose'] == TRUST_PURPOSE
        and transaction['pending'] is None and not os.path.lexists(TRUST_PENDING),
        'trusted-fixtures:unfinished-preparation')
    fixture_raw = root_file(FIXTURE_RECORD, 0o600)
    try:
        record = validate_trusted_record(transaction['complete'], fixture_raw,
                                        preparation['preparation_script_sha256'])
    except (ValueError, KeyError, TypeError):
        raise guest.GuestError('trusted-fixtures:baseline-provenance') from None
    native = record['native']
    try:
        service_gid = grp.getgrnam('fapolicyd').gr_gid
    except KeyError:
        raise guest.GuestError('trusted-fixtures:native-service-group') from None
    guest.require(service_gid == native['service_gid'],
                  'trusted-fixtures:native-service-group')
    trust_metadata = record['trust_file_metadata']
    trust = root_file(TRUST_FILE, trust_metadata['mode'], gid=trust_metadata['gid'])
    guest.require(hashlib.sha256(trust).hexdigest() == record['trust_file_sha256']
                  and trust_entries(trust) == {path: {key: spec[key] for key in ('size', 'sha256')}
                                              for path, spec in record['files'].items()},
                  'trusted-fixtures:trust-fragment')
    expected_os = 'fedora' if guest.package_path().suffix == '.rpm' else 'ubuntu'
    guest.require(native['os_id'] == expected_os, 'trusted-fixtures:native-platform')
    guest.require(not os.path.lexists(BACKEND_PENDING), 'trusted-fixtures:unfinished-backend')
    backend = record['backend']
    config = root_file(BACKEND_CONFIG, backend['mode'], gid=backend['gid'])
    backend_record = root_file(BACKEND_RECORD, 0o600, limit=300000)
    try:
        validate_backend_provenance(backend, config, backend_record, expected_os)
    except (ValueError, KeyError, TypeError):
        raise guest.GuestError('trusted-fixtures:native-backend') from None
    for label, executable in native_tool_paths(expected_os).items():
        alias = Path('/usr/sbin') / Path(executable).name
        guest.require(alias.resolve() == Path(executable), 'trusted-fixtures:native-tool-alias')
        # Native tools exceed the small-record bound, but their metadata and
        # bytes still have to match the exact preparation receipt.
        data = root_file(executable, 0o755, limit=16777216)
        guest.require(hashlib.sha256(data).hexdigest() == native[label + '_sha256'],
                      'trusted-fixtures:native-tool-changed')
        owner = guest.run(['rpm', '-qf', '--queryformat', '%{NAME}', executable]
                          if expected_os == 'fedora' else ['dpkg-query', '-S', executable])
        guest.require(owner == ('fapolicyd' if expected_os == 'fedora' else
                                'fapolicyd: ' + executable), 'trusted-fixtures:native-owner')
    identity = guest.run(['rpm', '-q', '--queryformat', '%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}\n',
                          'fapolicyd'] if expected_os == 'fedora' else
                         ['dpkg-query', '-W', '-f=${Package} ${Version}\n', 'fapolicyd'])
    guest.require(identity.split() == ['fapolicyd', native['version']],
                  'trusted-fixtures:native-package-changed')
    fixture = json.loads(fixture_raw)
    for variant in TRUSTED_VARIANTS:
        target, _, _ = native_paths(variant)
        data = root_file(target, 0o755, limit=16777216)
        source = guest.PAYLOAD / 'fixtures/mechanical' / ('identity-' + variant)
        spec = record['files'][str(target)]
        guest.require(len(data) == spec['size'] and hashlib.sha256(data).hexdigest() == spec['sha256']
                      and source.is_file() and not source.is_symlink()
                      and guest.sha(source) == spec['sha256'],
                      'trusted-fixtures:payload-changed')
    try:
        from native_assets import ACTIVITY_EXECUTABLE, ACTIVITY_PREFIX, GUI_FILES, activity_sources
    except ImportError:
        from tests.fixtures.native_assets import ACTIVITY_EXECUTABLE, ACTIVITY_PREFIX, GUI_FILES, activity_sources
    for target, source in zip((ACTIVITY_EXECUTABLE,
                              *(ACTIVITY_PREFIX + '/' + name for name in GUI_FILES)), activity_sources()):
        spec = record['files'][target]
        data = root_file(target, spec['mode'], limit=16777216)
        source = guest.PAYLOAD / source
        guest.require(len(data) == spec['size'] and hashlib.sha256(data).hexdigest() == spec['sha256']
                      and source.is_file() and not source.is_symlink()
                      and guest.sha(source) == spec['sha256'], 'trusted-fixtures:payload-changed')
    untrusted = []
    for variant in ('command', 'whitespace'):
        target, _, _ = native_paths(variant)
        spec = fixture['files'][str(target)]
        data = root_file(target, 0o755, limit=16777216)
        guest.require(hashlib.sha256(data).hexdigest() == spec['sha256']
                      == guest.sha(guest.PAYLOAD / 'fixtures/mechanical/onpc-test-application'),
                      'trusted-fixtures:untrusted-input-changed')
        untrusted.append(str(target))

    def diagnostic(raw):
        paths = set(record['files']) | set(untrusted)
        rows = [line for line in raw.decode('utf-8', errors='replace').splitlines()
                if (fields := database_row(line)) is not None and fields[1] in paths]
        return (f'database_bytes={len(raw)} sha256={hashlib.sha256(raw).hexdigest()}\n'
                + '\n'.join(rows) + '\n').encode()

    database = guest.run(['fapolicyd-cli', '--dump-db'], diagnostic_stdout=diagnostic)
    validate_database(database, record['files'], untrusted)
    return {'baseline_sha256': marker['baseline_sha256'],
            'preparation_sha256': marker['preparation_sha256'],
            'selected_inputs_sha256': marker['selected_inputs_sha256'],
            'provenance': record}


def qualify(record):
    """Install/boot is runner-owned; this phase never installs the candidate."""
    guest.guard()
    guest.wait_for_boot()
    previous = guest.PAYLOAD / ('previous-package' + guest.package_path().suffix)
    installed = json.loads((guest.PAYLOAD / 'results/previous-install.json').read_text())
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    guest.require(boot != installed['boot'] and guest.reboot_cleared(),
                  'trusted-fixtures:old-package-not-booted')
    guest.require(guest.sha(previous) == installed['previous_package_sha256'],
                  'trusted-fixtures:old-package-digest')
    guest.verify_package_files(previous, category='previous-package')
    old = guest.package_identity(previous, installed=True)
    guest.require(old != guest.package_identity(guest.package_path())
                  and not os.path.lexists(guest.KIOSK_CONFINEMENT_STATE),
                  'trusted-fixtures:requires-pinned-earlier-release')
    record('onpc.trusted-fixtures.previous.version', old)
    record('onpc.trusted-fixtures.previous.sha256', guest.sha(previous))
    before = verify_trust()
    record('onpc.trusted-fixtures.provenance', json.dumps(before, sort_keys=True))
    record_execution_backend(record)
    accounts = provision_native('trusted-hard')
    guest.require(provision_native('trusted-soft') == accounts,
                  'trusted-fixtures:account-identities')
    parent, child, other = (accounts[role] for role in ('parent', 'child', 'other'))
    preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    other_preferences = call(parent, 'GetPreferences', '(u)', (other,))[0]
    guest.require(not preferences['apps'] and not preferences['parent_control_enabled'],
                  'trusted-fixtures:requires-clean-policy')
    for variant in TRUSTED_VARIANTS:
        for role in ('child', 'other'):
            observe_launch(accounts[role], True, variant=variant)
            record(f'onpc.trusted-fixtures.unrestricted.{variant}.{role}', 'allowed')
        record_rules('unrestricted', child, False, record, variant=variant)
    call(parent, 'SetParentControl', '(ubu)', (child, True, 37))
    preferences = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    for variant, state in (('trusted-hard', 'permanent'), ('trusted-soft', 'conditional')):
        target, _, desktop = native_paths(variant)
        preferences['apps'][desktop] = {'state': state, 'targets': [str(target)],
                                       'patterns': [], 'user_saved_match_rule': False}
    call(parent, 'SetPreferences', '(us)', (child, json.dumps(preferences)))
    saved = json.loads(call(parent, 'GetPreferences', '(u)', (child,))[0])
    guest.require(saved['apps'] == preferences['apps'] and saved['parent_control_enabled'] is True,
                  'trusted-fixtures:policy-readback')
    for variant in TRUSTED_VARIANTS:
        record_rules('strict', child, True, record, variant=variant)
        observe_launch(child, False, variant=variant)
        observe_launch(other, True, variant=variant)
        record(f'onpc.trusted-fixtures.strict.{variant}', 'child-denied; other-allowed')
    password = FixturePassword()
    password.install(parent)
    other_parent = pwd.getpwnam('onpc-parent-casey').pw_uid
    with PersistentCaller(child) as caller, TextAgent(caller) as agent:
        caller.send({'kind': 'call', 'method': 'RequestOwnAccess',
                     'signature': '(uub)', 'args': (parent, 600, True)})
        agent.prompt(parent, other_parent)
        agent.authenticate(password)
        result = accepted(caller.receive())
        guest.require(result[1] == 'approved', 'trusted-fixtures:request-not-approved')
    for variant, allowed in (('trusted-hard', False), ('trusted-soft', True)):
        record_rules('approved', child, not allowed, record, variant=variant)
        observe_launch(child, allowed, variant=variant)
        observe_launch(other, True, variant=variant)
        record(f'onpc.trusted-fixtures.approved.{variant}',
               ('child-allowed' if allowed else 'child-denied') + '; other-allowed')
    guest.require(call(parent, 'GetPreferences', '(u)', (other,))[0] == other_preferences,
                  'trusted-fixtures:other-policy-changed')
    guest.require(verify_trust() == before, 'trusted-fixtures:provenance-changed')
    guest.verify_package_files(previous, category='previous-package')
    record('onpc.trusted-fixtures.result',
           'old-package-booted; exact-native-trust; unrestricted-controls; '
           'child-hard-and-strict-soft-denial; authenticated-soft-approval; unrelated-user-allowed')
