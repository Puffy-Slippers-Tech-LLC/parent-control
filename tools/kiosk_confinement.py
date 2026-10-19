#!/usr/bin/python3 -I
"""Prepare immutable, independently labelled executables for the kiosk PAM gate.

The native PAM caller holds the preparation lock and installs these files in its
own mount namespace. No shared distribution executable is relabelled or changed.
"""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import pwd
import shutil
import stat
import subprocess
import sys
import tempfile
import re


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
RUNTIME = Path('/run/oh-no-parent-control-confinement')
ACCOUNT = 'oh-no-parent-control'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
PREPARATION_STAGES = frozenset((
    'identity', 'attestation', 'payload', 'enforcement', 'executable-inventory',
    'privileged-inventory', 'directory-layout', 'manager-generation', 'runtime',
    'recovery', 'generation-create', 'generation-verify', 'bindings'))
PREPARATION_REASONS = frozenset((
    'invalid-caller', 'invalid-arguments', 'unowned-account', 'substituted-path',
    'untrusted-path', 'untrusted-ancestor', 'unexpected-file-type',
    'unexpected-executable-mode', 'non-native-executable', 'source-changed',
    'invalid-executable-substitution', 'missing-executable', 'conflicting-executable-roles',
    'unexpected-preserved-executable', 'preserved-executable-label',
    'preserved-executable-changed', 'preserved-executable-layout',
    'inventory-outside-usr', 'unsafe-directory-entry', 'directory-inventory-too-large',
    'directory-generation-changed', 'selinux-not-enforcing', 'selinux-query-unavailable',
    'selinux-domain-not-enforcing', 'apparmor-not-enforcing', 'unknown-backend',
    'manager-unavailable', 'manager-identity', 'manager-not-confined', 'manager-exited',
    'mounted-preparation', 'linked-preparation', 'unknown-preparation-file',
    'unowned-preparation', 'policy-snapshot-not-attested', 'runtime-mode',
    'executable-inventory-too-large', 'copy-changed', 'generation-changed',
    'executable-label-changed'))


def preparation_log(fields):
    try:
        # Never queue diagnostics in Python's stderr buffer: a failed write
        # retried at interpreter shutdown can change successful exit to 120.
        os.write(2, ('onpc.kiosk confinement ' + fields + '\n').encode('ascii'))
    except OSError:
        pass  # Unavailable diagnostic output must not change admission policy.


def report_preparation_failure(error, role='other'):
    """Keep failure locations and closed reasons, never exception text/paths."""
    role = role if role in ('manager', 'gate') else 'other'
    stage, line = 'arguments', None
    frame = error.__traceback__
    while frame is not None:
        if frame.tb_frame.f_code.co_filename == __file__:
            line = frame.tb_lineno
            if frame.tb_frame.f_code.co_name == 'prepare':
                candidate = frame.tb_frame.f_locals.get('stage')
                stage = (candidate if isinstance(candidate, str) and candidate in PREPARATION_STAGES
                         else 'other')
        frame = frame.tb_next
    reason, details = 'verification', ''
    if isinstance(error, ValueError) and error.args and isinstance(error.args[0], str):
        value = error.args[0]
        if value in PREPARATION_REASONS:
            reason = value
        elif value == 'manager-generation-stale':
            reason = 'stale-manager-reboot-required'
        elif value == 'generation-limit-reboot-required':
            reason = value
    elif isinstance(error, subprocess.TimeoutExpired):
        reason = 'command-timeout'
    elif isinstance(error, subprocess.CalledProcessError):
        reason = 'command-failed'
        if type(error.returncode) is int and -255 <= error.returncode <= 255:
            details = f' status={error.returncode}'
    elif isinstance(error, OSError):
        reason = 'os-error'
        if type(error.errno) is int and 0 <= error.errno <= 4095:
            details = f' errno={error.errno}'
    if line is not None:
        details += f' source=kiosk-confinement line={line}'
    preparation_log(f'preparation outcome=denied role={role} stage={stage} reason={reason}{details}')


def trusted(path, *, directory=False, symlinks=False):
    """Validate distribution aliases, every indirection and resolved storage."""
    path = Path(path).absolute()
    if not symlinks and any(item.is_symlink() for item in (path, *path.parents)):
        raise ValueError('substituted-path')
    # Reject cycles before inspecting lexical target paths: a relative cycle
    # containing ../ can otherwise produce endlessly different spellings.
    resolved = path.resolve(strict=True)
    pending, inspected = [path, resolved], set()
    while pending:
        current = pending.pop()
        for ancestor in (current, *current.parents):
            if ancestor in inspected:
                continue
            inspected.add(ancestor)
            info = ancestor.lstat()
            if stat.S_ISLNK(info.st_mode):
                if not symlinks:
                    raise ValueError('substituted-path')
                # Symlink mode bits do not govern replacement. Its owner and
                # every directory along the original and target paths do.
                if info.st_uid != 0:
                    raise ValueError('untrusted-path')
                target = Path(os.readlink(ancestor))
                pending.append(target if target.is_absolute() else ancestor.parent / target)
            else:
                if info.st_uid != 0 or info.st_mode & 0o022:
                    raise ValueError('untrusted-path')
                if ancestor != current and not stat.S_ISDIR(info.st_mode):
                    raise ValueError('untrusted-ancestor')
    path = resolved
    info = path.stat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError('unexpected-file-type')
    return path


def source_record(role, source):
    path = trusted(source, symlinks=True)
    with path.open('rb') as stream:
        before = os.fstat(stream.fileno())
        if before.st_mode & 0o6000 or (role not in ('blocked', 'library') and not before.st_mode & 0o111):
            raise ValueError('unexpected-executable-mode')
        if stream.read(4) != b'\x7fELF':
            raise ValueError('non-native-executable')
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        after = os.fstat(stream.fileno())
    identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns,
                             item.st_ctime_ns)
    if identity(before) != identity(after):
        raise ValueError('source-changed')
    # File identity detects an in-flight update; only content and canonical
    # names define a generation, so same-byte reinstalls remain compatible.
    return {'role': role, 'path': str(path), 'sha256': digest}


def inventory(config):
    records = []
    seen = {}
    for entry in config['executables']:
        source = entry.get('source')
        if source is not None and (not isinstance(source, str) or not source or
                len(entry['paths']) != 1 or entry.get('optional') or entry.get('library_directory')):
            raise ValueError('invalid-executable-substitution')
        candidates = [Path(path) for path in entry['paths'] if Path(path).exists()]
        if entry.get('library_directory'):
            directory = trusted(entry['library_directory'], directory=True, symlinks=True)
            candidates = sorted(directory.glob('libsystemd-*.so'))
        if not candidates:
            if entry.get('optional', False):
                continue
            raise ValueError('missing-executable')
        # Alternative distro locations describe one program, never a wildcard
        # permission. Distinct installed alternatives are separately validated.
        for path in candidates:
            record = source_record(entry['role'], path if source is None else source)
            if source is not None:
                record['source'] = record['path']
                record['path'] = str(trusted(path, symlinks=True))
            if record['path'] in seen:
                if seen[record['path']] != record:
                    raise ValueError('conflicting-executable-roles')
                continue
            seen[record['path']] = record
            records.append(record)
    return records


def file_identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns,
            info.st_ctime_ns, info.st_mode, info.st_uid, info.st_gid)


def preserved_inventory(config):
    """Measure vendor privilege helpers without copying or relabelling them.

    Content and privilege metadata define the stable generation. The separate
    inode assertion binds the native caller to the exact file measured here.
    """
    records, identities = [], {}
    for entry in config.get('preserved_executables', []):
        path = trusted(entry['path'])
        with os.fdopen(os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC), 'rb') as stream:
            before = os.fstat(stream.fileno())
            if (before.st_uid != 0 or before.st_gid != 0 or before.st_nlink != 1 or
                    stat.S_IMODE(before.st_mode) != entry['mode'] or
                    stream.read(4) != b'\x7fELF' or
                    'security.capability' in os.listxattr(stream.fileno())):
                raise ValueError('unexpected-preserved-executable')
            label = (os.getxattr(stream.fileno(), 'security.selinux').rstrip(b'\0').decode('ascii')
                     if config['backend'] == 'selinux' else None)
            if label != entry['label']:
                raise ValueError('preserved-executable-label')
            stream.seek(0)
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            after = os.fstat(stream.fileno())
        if file_identity(before) != file_identity(after):
            raise ValueError('preserved-executable-changed')
        records.append(dict(path=str(path), sha256=digest, mode=entry['mode'],
                            uid=0, gid=0, label=label))
        identities[str(path)] = file_identity(after)
    return records, identities


def directory_layout(config, records):
    """Own every mountpoint dentry from /usr to each protected executable.

    Binding directly onto global file dentries is unsafe: OS package unlink or
    replacement detaches such mounts across namespaces. Independent directory
    entries keep the old executable and library views valid until reboot.
    """
    covered = {Path(record['path']).parent for record in records}
    covered.add(PAYLOAD)
    for name in config.get('reserved_directories', []):
        covered.add(trusted(name, directory=True, symlinks=True))
    for directory in tuple(covered):
        if directory != Path('/usr') and Path('/usr') not in directory.parents:
            raise ValueError('inventory-outside-usr')
        covered.update(parent for parent in directory.parents if parent != Path('/'))
    required = covered | {Path(record['path']) for record in records}
    # Include lexical executable aliases as well as their canonical storage.
    for entry in config.get('executables', []):
        required.update(Path(path) for path in entry['paths'])
    observations = {}

    def observe(child, info, action, reason):
        kind = ('unknown' if info is None else
                'directory' if stat.S_ISDIR(info.st_mode) else
                'file' if stat.S_ISREG(info.st_mode) else
                'link' if stat.S_ISLNK(info.st_mode) else 'special')
        owner = 'unknown' if info is None else 'root' if info.st_uid == 0 else 'non-root'
        access = ('unknown' if info is None else 'world-write' if info.st_mode & 0o002 else
                  'group-write' if info.st_mode & 0o020 else
                  'owner-change' if info.st_uid != 0 else 'read-only')
        area = child.parts[2] if len(child.parts) > 2 else 'usr'
        area = area if area in ('usr', 'bin', 'sbin', 'lib', 'lib64', 'libexec', 'share') else 'other'
        fields = (action, reason, kind, owner, access,
                  'required' if child in required else 'sibling', area)
        observations[fields] = observations.get(fields, 0) + 1

    def report():
        for (action, reason, kind, owner, access, scope, area), count in sorted(observations.items()):
            preparation_log(f'directory-entry action={action} reason={reason} kind={kind} '
                            f'ownership={owner} access={access} scope={scope} area={area} count={count}')

    entries, scanned = [], 0
    for directory in sorted(covered, key=str):
        trusted(directory, directory=True)
        for child in sorted(directory.iterdir()):
            scanned += 1
            if scanned > 32768:
                report()
                raise ValueError('directory-inventory-too-large')
            try:
                info = child.lstat()
            except OSError:
                observe(child, None, 'denied' if child in required else 'omitted', 'metadata-unavailable')
                if child in required:
                    report()
                    raise
                continue
            reason = ('unsupported-name' if '\t' in str(child) or '\n' in str(child) else
                      'non-root-owner' if info.st_uid != 0 else
                      'writable-entry' if not stat.S_ISLNK(info.st_mode) and info.st_mode & 0o022 else
                      'unsupported-type' if not (stat.S_ISREG(info.st_mode) or
                                                stat.S_ISDIR(info.st_mode) or
                                                stat.S_ISLNK(info.st_mode)) else None)
            if reason:
                # Ambient software is not an admission prerequisite. Never bind
                # an untrusted sibling, or copy an untrusted symlink. Required
                # native inputs retain the strict refusal, including late drift.
                action = ('denied' if child in required else
                          'masked' if stat.S_ISDIR(info.st_mode) and reason != 'unsupported-name' else 'omitted')
                observe(child, info, action, reason)
                if action == 'denied':
                    report()
                    raise ValueError('unsafe-directory-entry')
                if action == 'masked':
                    entries.append({'path': str(child), 'kind': 'empty-directory'})
                continue
            if stat.S_ISLNK(info.st_mode):
                try:
                    target = os.readlink(child)
                except OSError:
                    observe(child, info, 'denied' if child in required else 'omitted', 'metadata-unavailable')
                    if child in required:
                        report()
                        raise
                    continue
                entries.append({'path': str(child), 'kind': 'link', 'link': target})
            else:
                # The containing directory and all its ancestors were checked
                # above. lstat identifies this immediate non-link child; do
                # not resolve and recheck the same ancestry for every sibling.
                entries.append({'path': str(child), 'kind': 'tree' if child in covered else
                                'directory' if stat.S_ISDIR(info.st_mode) else 'file'})
    report()
    return entries


def make_tree(destination, layout):
    destination.mkdir(mode=0o755)
    destination.chmod(0o755)
    for entry in sorted(layout, key=lambda item: (item['path'].count('/'), item['path'])):
        path = destination / Path(entry['path']).relative_to('/usr')
        if entry['kind'] == 'link':
            path.symlink_to(entry['link'])
        elif entry['kind'] in ('tree', 'directory', 'empty-directory'):
            path.mkdir(mode=0o755)
            path.chmod(0o755)
        else:
            path.touch(mode=0o644)


def verify_tree(root, layout):
    trusted(root, directory=True)
    expected = {entry['path'].removeprefix('/usr/'): entry for entry in layout}
    actual = {str(path.relative_to(root)): path for path in root.rglob('*')}
    if set(actual) != set(expected):
        raise ValueError('directory-generation-changed')
    for name, path in actual.items():
        entry = expected[name]
        info = path.lstat()
        if entry['kind'] == 'link':
            if not stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or os.readlink(path) != entry['link']:
                raise ValueError('directory-generation-changed')
        else:
            # rglob does not descend through directory symlinks. The complete
            # inventory checks every private ancestor as its own entry, while
            # trusted(root) checks the ancestors outside the tree once.
            if info.st_uid != 0 or info.st_mode & 0o022:
                raise ValueError('untrusted-path')
            directory = entry['kind'] in ('tree', 'directory', 'empty-directory')
            if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
                raise ValueError('unexpected-file-type')
            if entry['kind'] == 'file' and (info.st_nlink != 1 or info.st_size != 0):
                raise ValueError('directory-generation-changed')


def enforcing(config):
    if config['backend'] == 'apparmor':
        lines = Path('/sys/kernel/security/apparmor/profiles').read_text().splitlines()
        if any(f'{name} (enforce)' not in lines for name in config['apparmor_profiles']):
            raise ValueError('apparmor-not-enforcing')
    elif config['backend'] == 'selinux':
        library = ctypes.CDLL('libselinux.so.1', use_errno=True)
        if library.is_selinux_enabled() != 1 or library.security_getenforce() != 1:
            raise ValueError('selinux-not-enforcing')
        # The global enforcing flag does not exclude a permissive domain.
        class Decision(ctypes.Structure):
            _fields_ = [('allowed', ctypes.c_uint32), ('decided', ctypes.c_uint32),
                        ('auditallow', ctypes.c_uint32), ('auditdeny', ctypes.c_uint32),
                        ('seqno', ctypes.c_uint32), ('flags', ctypes.c_uint32)]
        library.string_to_security_class.argtypes = [ctypes.c_char_p]
        library.string_to_security_class.restype = ctypes.c_ushort
        library.string_to_av_perm.argtypes = [ctypes.c_ushort, ctypes.c_char_p]
        library.string_to_av_perm.restype = ctypes.c_uint32
        library.security_compute_av_flags_raw.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_ushort, ctypes.c_uint32,
            ctypes.POINTER(Decision)]
        cls = library.string_to_security_class(b'process')
        perm = library.string_to_av_perm(cls, b'ptrace')
        if not cls or not perm:
            raise ValueError('selinux-query-unavailable')
        contexts = [f'system_u:system_r:onpc_kiosk_{name.replace("-", "_")}_t:s0'
                    for name in config['domains']]
        if config.get('preserved_executables'):
            contexts.append('system_u:system_r:policykit_auth_t:s0')
        for context in contexts:
            context = context.encode()
            decision = Decision()
            if library.security_compute_av_flags_raw(
                    context, context, cls, perm, ctypes.byref(decision)) != 0 or decision.flags & 1:
                raise ValueError('selinux-domain-not-enforcing')
    else:
        raise ValueError('unknown-backend')


def label(path, role, backend):
    if backend != 'selinux':
        return
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    library.setfilecon_raw.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    context = f'system_u:object_r:onpc_kiosk_{role.replace("-", "_")}_exec_t:s0'
    if library.setfilecon_raw(os.fsencode(path), context.encode()) != 0:
        raise OSError(ctypes.get_errno(), 'executable-label-failed')


def verify_label(path, role, backend):
    if backend != 'selinux':
        return
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    context = ctypes.c_char_p()
    library.getfilecon_raw.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    library.freecon.argtypes = [ctypes.c_void_p]
    if library.getfilecon_raw(os.fsencode(path), ctypes.byref(context)) < 0:
        raise OSError(ctypes.get_errno(), 'executable-label-unavailable')
    try:
        expected = f'system_u:object_r:onpc_kiosk_{role.replace("-", "_")}_exec_t:s0'.encode()
        if context.value != expected:
            raise ValueError('executable-label-changed')
    finally:
        library.freecon(context)


def manager_generation(uid, digest, backend):
    result = subprocess.run(
        ['/usr/bin/systemctl', 'show', '--property=MainPID', '--value', f'user@{uid}.service'],
        env=ENV, check=True, capture_output=True, text=True, timeout=5)
    pid = int(result.stdout.strip())
    if pid <= 1:
        raise ValueError('manager-unavailable')
    # pidfd pins identity while reading its namespace and label; PID reuse can
    # never substitute another manager between the two observations.
    pidfd = os.pidfd_open(pid)
    try:
        import select
        poll = select.poll()
        poll.register(pidfd, select.POLLIN)
        proc = Path('/proc') / str(pid)
        identities = [line.split()[1:] for line in (proc / 'status').read_text().splitlines()
                      if line.startswith('Uid:')]
        if identities != [[str(uid)] * 4]:
            raise ValueError('manager-identity')
        marker = proc / 'root' / str(PAYLOAD / 'generation').lstrip('/')
        if marker.read_text() != digest + '\n':
            raise ValueError('manager-generation-stale')
        attribute = ('attr/apparmor/current' if backend == 'apparmor' else 'attr/current')
        expected = ('onpc-kiosk-manager (enforce)' if backend == 'apparmor'
                    else 'system_u:system_r:onpc_kiosk_manager_t:s0')
        if (proc / attribute).read_text().strip().rstrip('\x00') != expected:
            raise ValueError('manager-not-confined')
        if poll.poll(0):
            raise ValueError('manager-exited')
    finally:
        os.close(pidfd)


def reclaim_interrupted():
    """The inherited exclusive lock proves no preparation still owns these.

    Completed generations stay mounted until their processes exit. Keep at most
    four per boot instead of deleting live executable inodes behind AppArmor.
    """
    mounts = [line.split()[4] for line in Path('/proc/self/mountinfo').read_text().splitlines()]
    for item in RUNTIME.iterdir():
        if not re.fullmatch(r'\.(?:prepare|bindings)-[a-zA-Z0-9_]+', item.name):
            continue
        if any(path == str(item) or path.startswith(str(item) + '/') for path in mounts):
            raise ValueError('mounted-preparation')
        if item.name.startswith('.bindings-'):
            trusted(item)
            if item.stat().st_nlink != 1:
                raise ValueError('linked-preparation')
            item.unlink()
            continue
        trusted(item, directory=True)
        children = list(item.rglob('*'))
        for child in children:
            relative = child.relative_to(item)
            if len(relative.parts) == 1 and not (child.name.isdecimal() or child.name in ('generation', 'records.json', 'tree')):
                raise ValueError('unknown-preparation-file')
            info = child.lstat()
            if info.st_uid != 0:
                raise ValueError('unowned-preparation')
            if stat.S_ISLNK(info.st_mode) and relative.parts[0] == 'tree':
                continue
            trusted(child, directory=stat.S_ISDIR(info.st_mode))
            if stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
                raise ValueError('linked-preparation')
        shutil.rmtree(item)


def prepare(role):
    stage = 'identity'
    if os.geteuid() != 0 or role not in ('manager', 'gate'):
        raise ValueError('invalid-caller')
    os.umask(0o077)
    account = pwd.getpwnam(ACCOUNT)
    marker = trusted('/var/lib/oh-no-parent-control/package-created-kiosk-uid')
    if (account.pw_uid == 0 or stat.S_IMODE(marker.stat().st_mode) != 0o600 or
            marker.stat().st_nlink != 1 or marker.read_text().strip() != str(account.pw_uid)):
        raise ValueError('unowned-account')
    stage = 'attestation'
    attestation = subprocess.run(
        ['/usr/libexec/oh-no-parent-control-kiosk-confinement-integration', 'verify'],
        env=ENV, check=True, capture_output=True, text=True, timeout=5)
    stage = 'payload'
    config_path = trusted(PAYLOAD / 'config.json')
    config_bytes = config_path.read_bytes()
    config = json.loads(config_bytes)
    policy = trusted(PAYLOAD / ('onpc-kiosk.cil' if config['backend'] == 'selinux' else 'onpc-kiosk.apparmor')).read_bytes()
    # Bind these exact bytes to the verified loaded generation. Package unpack
    # does not hold the native preparation lock and can replace payload files
    # after verification. Changed bytes or an old/incomplete helper deny before
    # inventory or private-generation writes; identical-byte reinstall is safe.
    if attestation.stdout != ' '.join(hashlib.sha256(data).hexdigest()
                                     for data in (config_bytes, policy)) + '\n':
        raise ValueError('policy-snapshot-not-attested')
    stage = 'enforcement'
    enforcing(config)
    stage = 'executable-inventory'
    records = inventory(config)
    stage = 'privileged-inventory'
    preserved, identities = preserved_inventory(config)
    stage = 'directory-layout'
    layout = directory_layout(config, [*records, *preserved])
    masked = sum(entry['kind'] == 'empty-directory' for entry in layout)
    if masked:
        preparation_log('directory-view outcome=masked reason=writable-sibling-directory '
                        f'count={masked}')
    # A concurrent vendor update can remove or replace an entry after its
    # measurement. Every preserved executable must reach the signed native
    # binding route; a manifest record alone does not establish that binding.
    if any([entry['kind'] for entry in layout if entry['path'] == path] != ['file']
           for path in identities):
        raise ValueError('preserved-executable-layout')
    manifest = {'records': records, 'preserved': preserved, 'layout': layout}
    digest = hashlib.sha256(config_bytes + policy + json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    if role == 'gate':
        stage = 'manager-generation'
        manager_generation(account.pw_uid, digest, config['backend'])
    # The locked native PAM caller creates this directory before execing us,
    # preserving its named SELinux transition rather than the interpreter's.
    stage = 'runtime'
    trusted(RUNTIME, directory=True)
    if stat.S_IMODE(RUNTIME.stat().st_mode) != 0o700:
        raise ValueError('runtime-mode')
    stage = 'recovery'
    reclaim_interrupted()
    generation = RUNTIME / digest
    if not generation.exists():
        stage = 'generation-create'
        if sum(bool(re.fullmatch(r'[0-9a-f]{64}', item.name)) for item in RUNTIME.iterdir()) >= 4:
            raise ValueError('generation-limit-reboot-required')
        if sum(Path(record.get('source', record['path'])).stat().st_size for record in records) > 512 * 1024 * 1024:
            raise ValueError('executable-inventory-too-large')
        temporary = Path(tempfile.mkdtemp(prefix='.prepare-', dir=RUNTIME))
        try:
            for index, record in enumerate(records):
                destination = temporary / str(index)
                # Independent inodes are essential: SELinux labels on a hardlink
                # would relabel the distribution's original executable.
                with open(record.get('source', record['path']), 'rb') as source, destination.open('xb') as target:
                    shutil.copyfileobj(source, target)
                os.chmod(destination, 0o644 if record['role'] in ('blocked', 'library') else 0o755)
                if hashlib.sha256(destination.read_bytes()).hexdigest() != record['sha256']:
                    raise ValueError('copy-changed')
                label(destination, record['role'], config['backend'])
            (temporary / 'generation').write_text(digest + '\n')
            os.chmod(temporary / 'generation', 0o644)
            make_tree(temporary / 'tree', layout)
            (temporary / 'records.json').write_text(json.dumps(manifest, sort_keys=True))
            os.chmod(temporary / 'records.json', 0o600)
            temporary.rename(generation)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
    stage = 'generation-verify'
    trusted(generation, directory=True)
    if json.loads(trusted(generation / 'records.json').read_text()) != manifest:
        raise ValueError('generation-changed')
    verify_tree(generation / 'tree', layout)
    replacements = {}
    for index, record in enumerate(records):
        target = trusted(generation / str(index))
        if hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('copy-changed')
        verify_label(target, record['role'], config['backend'])
        replacements[record['path']] = target
    replacements[str(PAYLOAD / 'generation')] = generation / 'generation'
    stage = 'bindings'
    bindings = []
    for entry in layout:
        if entry['kind'] in ('tree', 'link', 'empty-directory'):
            continue
        source = replacements.get(entry['path'], entry['path'])
        target = generation / 'tree' / Path(entry['path']).relative_to('/usr')
        assertion = ('\t' + ' '.join(map(str, identities[entry['path']]))
                     if entry['path'] in identities else '')
        bindings.append(f'{source}\t{target}{assertion}\n')
    # Recursively attach the complete tree only after all subordinate mounts
    # use its independent dentries. /usr is the sole global mountpoint.
    bindings.append(f'{generation / "tree"}\t/usr\n')
    fd, name = tempfile.mkstemp(prefix='.bindings-', dir=RUNTIME)
    pending = Path(name)
    try:
        with os.fdopen(fd, 'w') as stream:
            stream.write(config['backend'] + '\n' + ''.join(bindings))
        pending.replace(RUNTIME / 'bindings')
    finally:
        pending.unlink(missing_ok=True)


def main():
    role = sys.argv[1] if len(sys.argv) == 2 else 'other'
    try:
        if len(sys.argv) != 2:
            raise ValueError('invalid-arguments')
        prepare(role)
    except Exception as error:
        report_preparation_failure(error, role)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
