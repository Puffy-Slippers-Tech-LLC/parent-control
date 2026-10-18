"""Read-only, offline admission checks for the two reviewed native input pairs.

The artifact builder authenticates the bundle.  This module binds that verified
selection to the *actual* installed database and baseline, without installing a
package, changing trust, downloading dependencies, or establishing generation A.
The later scenario owns the real old/new transactions and trigger completion.
"""

from contextlib import contextmanager
from email.parser import Parser
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tomllib


SCHEMA = 1
REFRESH = '; refresh prerequisites through tools/prepare-vm, then retry'
RPM_TAGS = (
    'requirename', 'requireversion', 'requireflags',
    'providename', 'provideversion', 'provideflags',
    'conflictname', 'conflictversion', 'conflictflags',
    'obsoletename', 'obsoleteversion', 'obsoleteflags',
    'triggername', 'triggerversion', 'triggerflags', 'triggerindex',
    'triggerscripts', 'triggerscriptprog', 'triggerscriptflags',
    'filetriggername', 'filetriggerindex', 'filetriggerflags',
    'filetriggerversion', 'filetriggerscripts', 'filetriggerscriptprog',
    'filetriggerscriptflags', 'filetriggerpriorities',
    'transfiletriggername', 'transfiletriggerindex', 'transfiletriggerflags',
    'transfiletriggerversion', 'transfiletriggerscripts', 'transfiletriggerscriptprog',
    'transfiletriggerscriptflags', 'transfiletriggerpriorities',
    'prein', 'postin', 'preun', 'postun', 'pretrans', 'posttrans',
)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     ensure_ascii=True).encode()).hexdigest()


def provenance_digest(value):
    if isinstance(value, dict) and value:
        return digest(value)
    require(isinstance(value, str) and re.fullmatch(r'[a-f0-9]{64}', value),
            'baseline-provenance')
    return value


def require(condition, category):
    if not condition:
        raise ValueError('native-preflight:' + category + REFRESH)


class Runner:
    def run(self, arguments, *, timeout=120, pass_fds=()):
        return subprocess.run(arguments, check=False, text=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, pass_fds=pass_fds,
                              env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'})


def command(runner, arguments, *, pass_fds=(), empty=False):
    options = {'timeout': 120}
    if pass_fds:
        options['pass_fds'] = pass_fds
    try:
        result = runner.run(arguments, **options)
    except (OSError, subprocess.SubprocessError) as error:
        raise ValueError('native-preflight:command-unavailable' + REFRESH) from error
    require(result.returncode == 0, 'native-command-failed:' + arguments[0])
    require(not empty or not result.stdout.strip(), 'package-health')
    return {'argv': arguments, 'stdout': result.stdout, 'stderr': result.stderr,
            'returncode': result.returncode}


def read_file(path, *, optional=False):
    """Pin regular database/configuration files; never follow a final symlink."""
    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC)
    except FileNotFoundError:
        require(optional, 'missing-file:' + str(path))
        return None
    except OSError as error:
        raise ValueError('native-preflight:unsafe-file' + REFRESH) from error
    try:
        before = os.fstat(descriptor)
        require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'unsafe-file')
        with os.fdopen(descriptor, 'rb', closefd=False) as stream:
            contents = stream.read()
        after = os.fstat(descriptor)
        require((before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) ==
                (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns),
                'file-changed')
        return contents
    finally:
        os.close(descriptor)


def configuration_record(root, relative, *, optional=False):
    """Retain exact native definition bytes plus their trusted file metadata."""
    path = root / relative
    try:
        before = path.lstat()
    except FileNotFoundError:
        require(optional, 'missing-native-configuration')
        return None
    require(before.st_uid == root.stat().st_uid and not before.st_mode & 0o022,
            'unsafe-native-configuration')
    data = read_file(path)
    after = path.lstat()
    require((before.st_dev, before.st_ino, before.st_mtime_ns, before.st_mode,
             before.st_uid, before.st_gid) ==
            (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_mode,
             after.st_uid, after.st_gid), 'native-configuration-changed')
    return {'sha256': hashlib.sha256(data).hexdigest(), 'definition': data.decode(),
            'uid': before.st_uid, 'gid': before.st_gid, 'mode': stat.S_IMODE(before.st_mode)}


def paragraphs(contents):
    records = []
    for text in contents.split('\n\n'):
        if not text.strip():
            continue
        record = Parser().parsestr(text)
        require(all(len(record.get_all(key)) == 1 for key in record.keys()),
                'ambiguous-status')
        records.append(dict(record.items()))
    return records


def installed_deb(root):
    source = read_file(root / 'var/lib/dpkg/status').decode()
    records = paragraphs(source)
    selected = {}
    for record in records:
        require('Package' in record and 'Status' in record, 'malformed-status')
        # A removed package's residual configuration is ordinary healthy state.
        require(record['Status'] in ('install ok installed', 'deinstall ok config-files',
                                     'purge ok not-installed', 'deinstall ok not-installed'),
                'package-not-configured-or-held')
        require(not record.get('Triggers-Pending') and not record.get('Triggers-Awaited'),
                'pending-triggers')
        if record['Status'] == 'install ok installed':
            require(record.get('Architecture') and record.get('Version'), 'malformed-status')
            key = record['Package'] + ':' + record['Architecture']
            require(key not in selected, 'ambiguous-status')
            selected[key] = record
    for relative in ('var/lib/dpkg/updates',):
        path = root / relative
        require(path.is_dir() and not path.is_symlink() and not list(path.iterdir()),
                'package-updates-pending')
    pending = read_file(root / 'var/lib/dpkg/triggers/Unincorp', optional=True)
    require(not pending or not pending.strip(), 'pending-triggers')
    return source, selected


@contextmanager
def status_view(source):
    """APT reads a private anonymous status view, never a modified guest file."""
    descriptor = os.memfd_create('onpc-native-status', os.MFD_CLOEXEC)
    try:
        remaining = memoryview(source.encode())
        while remaining:
            written = os.write(descriptor, remaining)
            require(written > 0, 'incomplete-status-view')
            remaining = remaining[written:]
        os.lseek(descriptor, 0, os.SEEK_SET)
        yield descriptor
    finally:
        os.close(descriptor)


def replaced_status(source, metadata, package, architecture):
    records = paragraphs(source)
    result = []
    replaced = 0
    for record in records:
        if record.get('Package') == package and record.get('Architecture') == architecture:
            record = dict(metadata, Status='install ok installed')
            replaced += 1
        result.append('\n'.join(key + ': ' + value for key, value in record.items()))
    require(replaced == 1, 'selected-package-not-installed')
    return '\n\n'.join(result) + '\n\n'


def deb_plan(runner, source, path, package, architecture, version):
    with status_view(source) as descriptor:
        arguments = ['apt-get', '--simulate', '--no-download', '--no-install-recommends',
                     '-o', 'Debug::NoLocking=1', '-o', 'APT::Get::Show-Versions=true',
                     '-o', 'Dir::Etc::sourcelist=/dev/null',
                     '-o', 'Dir::Etc::sourceparts=-',
                     '-o', 'Dir::State::status=/proc/self/fd/' + str(descriptor),
                     'install', '--reinstall', '--allow-downgrades', str(path)]
        evidence = command(runner, arguments, pass_fds=(descriptor,))
    actions = [line for line in evidence['stdout'].splitlines()
               if re.match(r'^(Inst|Conf|Remv|Purg)\s', line)]
    installs = [line for line in actions if line.startswith('Inst ')]
    configures = [line for line in actions if line.startswith('Conf ')]
    require(len(installs) == len(configures) == 1 and len(actions) == 2,
            'additional-or-missing-native-changes')
    for line in actions:
        match = re.match(r'^(?:Inst|Conf) ([^\s]+)(?: \[[^]]+\])? \(([^\s)]+)', line)
        require(match is not None and match[1] in (package, package + ':' + architecture)
                and match[2] == version, 'unexpected-native-change')
    # Descriptor numbers are ephemeral, and must not become receipt identity.
    evidence['argv'] = [arg if not arg.startswith('Dir::State::status=') else
                        'Dir::State::status=<anonymous-status-view>' for arg in arguments]
    return evidence


def deb_triggers(root, installed, paths):
    registrations = configuration_record(root, 'var/lib/dpkg/triggers/File', optional=True)
    raw = registrations['definition'] if registrations else ''
    definitions = []
    owners = {record['Package']: record for record in installed.values()}
    owners.update(installed)
    for line in raw.splitlines():
        parts = line.split()
        require(len(parts) >= 2 and parts[0].startswith('/'), 'unknown-trigger-definition')
        trigger = parts[0]
        if not any(path == trigger or path.startswith(trigger.rstrip('/') + '/')
                   for path in paths):
            continue
        for registration in parts[1:]:
            owner = registration.removesuffix('/noawait')
            require(owner in owners and re.fullmatch(r'[a-z0-9][a-z0-9+.-]*(?::[a-z0-9]+)?', owner),
                    'unknown-trigger-owner')
            record = owners[owner]
            controls = {}
            for kind in ('triggers', 'postinst'):
                controls[kind] = configuration_record(root,
                    'var/lib/dpkg/info/' + owner + '.' + kind)
            # 004a reviewed only man-db. A different matching owner needs an
            # explicit future review, rather than accidental admission here.
            require(record['Package'] == 'man-db' and trigger == '/usr/share/man',
                    'unreviewed-external-trigger:' + owner)
            definitions.append({'owner': owner, 'version': record['Version'],
                                'architecture': record['Architecture'], 'path': trigger,
                                'registration': registration, 'controls': controls})
    require(any(item['path'] == '/usr/share/man' for item in definitions),
            'missing-reviewed-man-db-trigger')
    auto = root / 'var/lib/man-db/auto-update'
    exists = auto.exists() or auto.is_symlink()
    auto_record = configuration_record(root, 'var/lib/man-db/auto-update', optional=True)
    return {'registrations': registrations,
            'applicable': definitions, 'man_db_auto_update': exists,
            'auto_update_configuration': auto_record,
            'completion_required': bool(definitions) and exists,
            'completion_path': '/var/cache/man'}


def rpm_value(header, tag):
    try:
        value = header[tag]
    except (KeyError, ValueError, TypeError):
        value = None
    if value is None:
        return []
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [item.decode() if isinstance(item, bytes) else item for item in value]


def rpm_inventory(rpm_module):
    transaction = rpm_module.TransactionSet()
    result = []
    try:
        for header in transaction.dbMatch():
            record = {key: header[key] for key in ('name', 'version', 'release', 'arch')}
            record['epoch'] = header['epoch'] or 0
            record.update({tag: rpm_value(header, tag) for tag in RPM_TAGS})
            record['identity'] = (record['name'] + '-' + str(record['epoch']) + ':' +
                                  record['version'] + '-' + record['release'] + '.' + record['arch'])
            result.append(record)
    finally:
        transaction.closeDB()
    result.sort(key=lambda record: record['identity'])
    require(len({record['identity'] for record in result}) == len(result), 'ambiguous-rpm-status')
    return result


def rpm_triggers(installed, selection, payload_paths):
    applicable = []
    for record in installed:
        for prefix in ('filetrigger', 'transfiletrigger', 'trigger'):
            names = record[prefix + 'name']
            if prefix == 'trigger':
                matches = [name for name in names if name == selection['package']]
            else:
                matches = [name for name in names if any(
                    path.startswith(name) for path in payload_paths)]
            if not matches:
                continue
            require(record['name'] == 'man-db' and prefix != 'trigger' and
                    all(name == '/usr/share/man' for name in matches),
                    'unreviewed-external-trigger:' + record['name'])
            applicable.append({'owner': record['identity'], 'kind': prefix, 'matches': matches,
                               'definitions': {tag: record[tag] for tag in RPM_TAGS
                                               if tag.startswith(prefix)}})
    require(any(record['kind'] == 'transfiletrigger' for record in applicable),
            'missing-reviewed-man-db-trigger')
    return {'applicable': applicable, 'completion_required': bool(applicable),
            'completion_unit': 'man-db-cache-update.service', 'completion_path': '/var/cache/man'}


def rpm_trigger_idle(runner):
    evidence = command(runner, ['systemctl', 'show', 'man-db-cache-update.service',
        '--property=LoadState,ActiveState,SubState,Result,Job'])
    values = {}
    for line in evidence['stdout'].splitlines():
        key, separator, value = line.partition('=')
        require(separator and key not in values, 'trigger-service-state')
        values[key] = value
    require(values.get('LoadState') == 'loaded' and values.get('ActiveState') == 'inactive'
            and values.get('SubState') == 'dead' and values.get('Result') == 'success'
            and values.get('Job') == '', 'pending-or-failed-trigger-work')
    return values


def validate_manifest(manifest, bundle):
    require(isinstance(manifest, dict) and manifest.get('schema_version') == 1,
            'input-manifest-schema')
    fields = {key: value for key, value in manifest.items() if key != 'binding_sha256'}
    require(manifest.get('binding_sha256') == digest(fields), 'native-input-binding')
    selection = manifest['selection']
    packages = manifest['packages']
    paths = {}
    for phase in ('old', 'new'):
        relative = Path(packages[phase]['path'])
        require(not relative.is_absolute() and len(relative.parts) == 1,
                'unsafe-package-path')
        paths[phase] = Path(bundle) / relative
        data = read_file(paths[phase])
        require(hashlib.sha256(data).hexdigest() == packages[phase]['sha256'] ==
                selection[phase]['sha256'], 'package-digest')
        require((packages[phase]['name'], packages[phase]['version'], packages[phase]['architecture']) ==
                (selection['package'], selection[phase]['version'], selection['architecture']),
                'wrong-package-identity')
    require(packages['old']['version'] != packages['new']['version'] and
            packages['old']['executable']['sha256'] != packages['new']['executable']['sha256'],
            'same-native-generation')
    return selection, packages, paths


def preflight(os_id, manifest, bundle, *, baseline_provenance, selected_input_sha256,
              runner=None, root=Path('/'), rpm_module=None):
    """Return a baseline/input-bound receipt; perform no native transaction.

    Call the bundle builder's verify() before this API. ``baseline_provenance``
    is the controller's independently verified accepted-baseline identity. The
    guest caller must already own its VM lease. No receipt is published here.
    """
    baseline_digest = provenance_digest(baseline_provenance)
    require(isinstance(selected_input_sha256, str) and
            re.fullmatch(r'[a-f0-9]{64}', selected_input_sha256), 'selected-input-binding')
    require(os_id in ('ubuntu', 'fedora'), 'unsupported-os')
    root = Path(root)
    runner = runner or Runner()
    selection, packages, paths = validate_manifest(manifest, bundle)
    expected = ('deb', 'bubblewrap', 'amd64') if os_id == 'ubuntu' else (
        'rpm', 'xdg-dbus-proxy', 'x86_64')
    require((manifest['package_format'], selection['package'], selection['architecture']) ==
            expected, 'unsupported-pair')
    versions = ('0.11.1-1', '0.11.1-1ubuntu0.3') if os_id == 'ubuntu' else (
        '0:0.1.6-4.fc44', '0:0.1.9-1.fc44')
    require(tuple(packages[phase]['version'] for phase in ('old', 'new')) == versions,
            'unsupported-native-versions')
    phases = {}
    if os_id == 'ubuntu':
        source, installed = installed_deb(root)
        command(runner, ['dpkg', '--audit'], empty=True)
        require(not command(runner, ['apt-mark', 'showhold'])['stdout'].strip(), 'held-packages')
        key = selection['package'] + ':' + selection['architecture']
        require(key in installed, 'selected-package-not-installed')
        controls = {}
        payload_paths = set(command(runner, ['dpkg-query', '--listfiles', key])['stdout'].splitlines())
        require(all(path.startswith('/') for path in payload_paths), 'installed-file-inventory')
        baseline_controls = {}
        for kind in ('preinst', 'postinst', 'prerm', 'postrm', 'triggers'):
            # Native dpkg names multiarch controls with :architecture; ordinary
            # packages use the unqualified name. Refuse either unreviewed form.
            for owner in (selection['package'], key):
                path = 'var/lib/dpkg/info/' + owner + '.' + kind
                evidence = configuration_record(root, path, optional=True)
                require(evidence is None, 'unreviewed-selected-package-script:' + kind)
                baseline_controls[path] = evidence
        for phase in ('old', 'new'):
            records = paragraphs(command(runner, ['dpkg-deb', '--field', str(paths[phase])])['stdout'])
            require(len(records) == 1, 'package-control')
            controls[phase] = records[0]
            require((records[0].get('Package'), records[0].get('Architecture'), records[0].get('Version')) ==
                    (selection['package'], selection['architecture'], packages[phase]['version']),
                    'wrong-package-identity')
            listing = command(runner, ['dpkg-deb', '--contents', str(paths[phase])])['stdout']
            for line in listing.splitlines():
                fields = line.split(maxsplit=5)
                require(len(fields) == 6 and fields[5].startswith('./'), 'package-file-inventory')
                payload_paths.add('/' + fields[5][2:].split(' -> ', 1)[0].rstrip('/'))
        command(runner, ['dpkg', '--compare-versions', packages['old']['version'],
                         'lt', packages['new']['version']])
        # --reinstall gives an exact selected-package plan even when the
        # accepted baseline already has A. New is simulated explicitly from A.
        phases['old'] = deb_plan(runner, source, paths['old'], selection['package'],
                                 selection['architecture'], packages['old']['version'])
        phases['new'] = deb_plan(runner, replaced_status(source, controls['old'],
            selection['package'], selection['architecture']), paths['new'], selection['package'],
            selection['architecture'], packages['new']['version'])
        triggers = deb_triggers(root, installed, payload_paths)
        require(installed_deb(root) == (source, installed), 'native-state-changed')
        require(deb_triggers(root, installed, payload_paths) == triggers,
                'native-trigger-state-changed')
        require({path: configuration_record(root, path, optional=True)
                 for path in baseline_controls} == baseline_controls, 'native-configuration-changed')
        require(not command(runner, ['apt-mark', 'showhold'])['stdout'].strip(), 'held-packages')
        native = {'installed': installed, 'status_sha256': hashlib.sha256(source.encode()).hexdigest(),
                  'triggers': triggers, 'selected_baseline_controls': baseline_controls}
    else:
        if rpm_module is None:
            try:
                import rpm as rpm_module
            except ImportError as error:
                raise ValueError('native-preflight:python3-rpm-missing' + REFRESH) from error
        installed = rpm_inventory(rpm_module)
        targets = [record for record in installed if record['name'] == selection['package']]
        require(len(targets) == 1 and targets[0]['arch'] == selection['architecture'],
                'selected-package-not-installed')
        require(not any(targets[0][tag] for tag in
                        ('prein', 'postin', 'preun', 'postun', 'pretrans', 'posttrans')),
                'unreviewed-selected-package-script')
        require(rpm_module.labelCompare(tuple(packages['old']['version'].split(':', 1)[0:1] +
                    packages['old']['version'].split(':', 1)[1].rsplit('-', 1)),
                tuple(packages['new']['version'].split(':', 1)[0:1] +
                    packages['new']['version'].split(':', 1)[1].rsplit('-', 1))) < 0,
                'native-version-order')
        command(runner, ['dnf', '--cacheonly', '--disablerepo=*', 'check'])
        # DNF5's maintained versionlock file is TOML, version 1.0. Read it
        # directly: an absent optional plugin must not require test repair.
        # https://dnf5.readthedocs.io/en/latest/commands/versionlock.8.html
        configuration_paths = ('etc/dnf/dnf.conf', 'etc/dnf/versionlock.toml',
                               'etc/dnf/plugins/versionlock.conf', 'etc/dnf/plugins/versionlock.list')
        configuration = {path: configuration_record(root, path, optional=True)
                         for path in configuration_paths}
        locks_record = configuration['etc/dnf/versionlock.toml']
        locks = locks_record['definition'] if locks_record else None
        if locks is not None:
            try:
                parsed_locks = tomllib.loads(locks)
            except (ValueError, UnicodeError) as error:
                raise ValueError('native-preflight:malformed-versionlocks' + REFRESH) from error
            require(parsed_locks.get('version') == '1.0' and
                    not parsed_locks.get('packages'), 'held-packages')
        # Do not accidentally bypass a legacy DNF4 versionlock configuration.
        legacy_record = configuration['etc/dnf/plugins/versionlock.list']
        legacy_locks = legacy_record['definition'] if legacy_record else None
        require(not legacy_locks or not any(line.strip() and not line.lstrip().startswith(b'#')
                                           for line in legacy_locks.encode().splitlines()), 'held-packages')
        payload_paths = set(command(runner, ['rpm', '-ql', selection['package']])['stdout'].splitlines())
        require(all(path.startswith('/') for path in payload_paths), 'installed-file-inventory')
        providers = {}
        for phase in ('old', 'new'):
            native_identity = command(runner, ['rpm', '-qp', '--queryformat',
                '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\n', str(paths[phase])])
            require(native_identity['stdout'].strip().split('\t') == [selection['package'],
                    packages[phase]['version'], selection['architecture']], 'wrong-package-identity')
            payload_paths.update(command(runner, ['rpm', '-qpl', str(paths[phase])])['stdout'].splitlines())
            requirements = command(runner, ['rpm', '-qp', '--requires', str(paths[phase])])['stdout'].splitlines()
            providers[phase] = {}
            for requirement in requirements:
                if requirement.startswith('rpmlib('):
                    providers[phase][requirement] = ['native-rpm-engine:checked-by-rpm-test']
                    continue
                provider = command(runner, ['rpm', '-q', '--whatprovides', requirement,
                    '--queryformat', '%{NAME}\t%{EPOCHNUM}:%{VERSION}-%{RELEASE}\t%{ARCH}\n'])
                providers[phase][requirement] = sorted(provider['stdout'].splitlines())
                require(providers[phase][requirement] and all(
                    len(row.split('\t')) == 3 for row in providers[phase][requirement]),
                    'native-provider-inventory')
            # rpm does not resolve/download companion packages. Exactly one
            # supplied artifact plus --test checks its complete replacement,
            # including installed reverse dependencies and engine capabilities.
            phases[phase] = command(runner, ['rpm', '--upgrade', '--test', '--oldpackage',
                                              '--replacepkgs', str(paths[phase])])
        triggers = rpm_triggers(installed, selection, payload_paths)
        triggers['baseline_service_state'] = rpm_trigger_idle(runner)
        require(rpm_inventory(rpm_module) == installed, 'native-state-changed')
        require({path: configuration_record(root, path, optional=True)
                 for path in configuration_paths} == configuration, 'native-configuration-changed')
        native = {'installed': installed, 'providers': providers, 'triggers': triggers,
                  'configuration': configuration}
    receipt = {'schema_version': SCHEMA, 'package_format': expected[0],
               'pair_id': manifest['pair_id'], 'baseline_provenance_sha256': baseline_digest,
               'selected_input_sha256': selected_input_sha256, 'native_state': native,
               'native_manifest_sha256': digest(manifest),
               'native_binding_sha256': manifest['binding_sha256'],
               'phases': phases, 'read_only': True,
               'old_generation_established': False, 'live_transaction_qualified': False}
    receipt['binding_sha256'] = digest(receipt)
    return receipt


def verify_receipt(receipt, os_id, manifest, bundle, *, baseline_provenance,
                   selected_input_sha256, **options):
    """Reprobe actual native state; a stored digest alone is never readiness."""
    require(isinstance(receipt, dict) and receipt.get('schema_version') == SCHEMA,
            'receipt-schema')
    require(receipt.get('binding_sha256') == digest({key: value for key, value in receipt.items()
                                                   if key != 'binding_sha256'}), 'receipt-binding')
    require(receipt.get('baseline_provenance_sha256') == provenance_digest(baseline_provenance),
            'baseline-provenance-mismatch')
    require(receipt.get('selected_input_sha256') == selected_input_sha256,
            'selected-input-mismatch')
    require(receipt.get('native_manifest_sha256') == digest(manifest) and
            receipt.get('native_binding_sha256') == manifest.get('binding_sha256'),
            'native-input-mismatch')
    actual = preflight(os_id, manifest, bundle, baseline_provenance=baseline_provenance,
                       selected_input_sha256=selected_input_sha256, **options)
    require(actual['native_state'] == receipt.get('native_state'), 'installed-baseline-mismatch')
    return actual
