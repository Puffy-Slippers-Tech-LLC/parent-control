#!/usr/bin/python3 -I
"""Prepare immutable, independently labelled executables for the kiosk PAM gate.

The native PAM caller holds the preparation lock and installs these files in its
own mount namespace. No shared distribution executable is relabelled or changed.
"""
import ctypes
import copy
import errno
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
import secrets


PAYLOAD = Path('/usr/share/oh-no-parent-control/confinement')
RUNTIME = Path('/run/oh-no-parent-control-confinement')
NATIVE_SUPPORT = Path('/usr/libexec/oh-no-parent-control-kiosk-support')
NATIVE_LOCKS = ((4, Path('/run/oh-no-parent-control-confinement.lock')),
                (5, Path('/run/oh-no-parent-control-kiosk-admission.lock')))
ACCOUNT = 'oh-no-parent-control'
ENV = {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LC_ALL': 'C'}
PROTOCOL_VERSION = 1
MAX_ROWS = 32768
MAX_MANIFEST = 64 * 1024 * 1024
MAX_PATH = 4096
MAX_COPY_BYTES = 512 * 1024 * 1024
RUNTIME_CONTEXT = b'system_u:object_r:onpc_kiosk_runtime_t:s0'
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
MATERIAL_FAILURE_REASONS = {
    'material-limit': 'executable-inventory-too-large',
    'material-source-trust': 'untrusted-path', 'material-source-changed': 'source-changed',
    'retained-layout': 'generation-changed', 'retained-source-identity': 'generation-changed',
    'retained-required-source': 'copy-changed', 'retained-source-changed': 'source-changed'}


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
        elif value in MATERIAL_FAILURE_REASONS:
            reason = MATERIAL_FAILURE_REASONS[value]
        elif value in ('manager-generation-stale', 'manager-material-stale'):
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
                previous = seen[record['path']]
                if {key: value for key, value in previous.items() if key != 'aliases'} != record:
                    raise ValueError('conflicting-executable-roles')
                record = previous
            else:
                seen[record['path']] = record
                records.append(record)
            # Retain selected lexical routes across the post-inventory boundary.
            # Re-discovering them with exists() would silently forget an alias
            # that disappeared, including an optional installed alternative.
            if str(path) != record['path']:
                record['aliases'] = sorted(set(record.get('aliases', [])) | {str(path)})
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


def layout_requirements(config, records):
    """Return concrete skeleton parents and the complete required trust walk."""
    paths = {Path(record['path']) for record in records} | {PAYLOAD}
    paths.update(Path(alias) for record in records for alias in record.get('aliases', []))
    paths.update(Path(name) for name in config.get('reserved_directories', []))
    for name in (PAYLOAD, *config.get('reserved_directories', [])):
        directory = trusted(name, directory=True, symlinks=True)
        if directory != Path('/usr') and Path('/usr') not in directory.parents:
            raise ValueError('inventory-outside-usr')
    # A sole mandatory route cannot disappear or become a dangling link.
    # Absent alternatives/optional routes are permitted only when inventory
    # never selected them; selected lexical aliases are retained above.
    for entry in config.get('executables', []):
        mandatory = not entry.get('optional', False) and len(entry['paths']) == 1
        paths.update(Path(name) for name in entry['paths'] if mandatory or Path(name).exists())
        if entry.get('library_directory'):
            paths.add(Path(entry['library_directory']))
    proofs = required_proofs(paths)
    return layout_proof_requirements(proofs)


def layout_proof_requirements(proofs):
    """Keep all material consumers' ancestors in the private skeleton."""
    by_path = {Path(path): (kind, link) for kind, path, link in proofs}
    concrete = {path: proof for path, proof in by_path.items()
                if path != Path('/usr') and Path('/usr') in path.parents and
                not any(by_path.get(parent, (None,))[0] == 'link' for parent in path.parents)}
    covered = {Path('/usr')} | {path for path, (kind, _) in concrete.items() if kind == 'directory'}
    return covered, by_path, concrete


def validate_required_layout(layout, concrete, records):
    """A missing/replaced required dentry must never become a sibling omission."""
    nodes = {}
    for entry in layout:
        path = Path(entry['path'])
        if path in nodes:
            raise ValueError('unsafe-directory-entry')
        nodes[path] = entry
    for path, (kind, link) in concrete.items():
        entry = nodes.get(path)
        expected = 'tree' if kind == 'directory' else kind
        if (entry is None or entry['kind'] != expected or
                kind == 'link' and entry.get('link') != link):
            raise ValueError('unsafe-directory-entry')
    if any(nodes.get(Path(record['path']), {}).get('kind') != 'file' for record in records):
        raise ValueError('unsafe-directory-entry')


def directory_layout(config, records, *, material_proofs=None, source_assertions=None):
    """Own every mountpoint dentry from /usr to each protected executable.

    Binding directly onto global file dentries is unsafe: OS package unlink or
    replacement detaches such mounts across namespaces. Independent directory
    entries keep the old executable and library views valid until reboot.
    """
    for record in records:
        if Path('/usr') not in Path(record['path']).parents:
            raise ValueError('inventory-outside-usr')
    covered, required, concrete = (layout_requirements(config, records)
                                   if material_proofs is None else
                                   layout_proof_requirements(material_proofs))
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
            if scanned > MAX_ROWS:
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
            try:
                protocol_text(str(child), absolute=True)
                representable = True
            except ValueError:
                representable = False
            reason = ('unsupported-name' if not representable else
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
                try:
                    protocol_text(target)
                except ValueError:
                    observe(child, info, 'denied' if child in required else 'omitted', 'unsupported-name')
                    if child in required:
                        report()
                        raise ValueError('unsafe-directory-entry')
                    continue
                entries.append({'path': str(child), 'kind': 'link', 'link': target})
            else:
                # The containing directory and all its ancestors were checked
                # above. lstat identifies this immediate non-link child; do
                # not resolve and recheck the same ancestry for every sibling.
                entries.append({'path': str(child), 'kind': 'tree' if child in covered else
                                'directory' if stat.S_ISDIR(info.st_mode) else 'file'})
            if source_assertions is not None:
                # Capture provenance with the inventory observation. Never
                # reopen an ambient name later to substitute a newer inode.
                source_assertions[str(child)] = file_identity(info)
    report()
    validate_required_layout(entries, concrete, records)
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
            path.chmod(0o644)


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


def runtime_label(path, backend, *, verify=False):
    """Label private dentries individually without hiding bound source labels."""
    if backend != 'selinux':
        return
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    library.lsetfilecon_raw.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
    library.lgetfilecon_raw.argtypes = [ctypes.c_char_p, ctypes.POINTER(ctypes.c_char_p)]
    library.freecon.argtypes = [ctypes.c_void_p]
    if not verify and library.lsetfilecon_raw(os.fsencode(path), RUNTIME_CONTEXT) != 0:
        raise OSError(ctypes.get_errno(), 'runtime-label-failed')
    context = ctypes.c_char_p()
    if library.lgetfilecon_raw(os.fsencode(path), ctypes.byref(context)) < 0:
        raise OSError(ctypes.get_errno(), 'runtime-label-unavailable')
    try:
        if context.value != RUNTIME_CONTEXT:
            raise ValueError('runtime-label-changed')
    finally:
        library.freecon(context)


def verify_invocation_root(backend):
    """Require the empty tmpfs mounted by this invocation's native caller.

    The caller owns namespace and mount identity lifetime. Never manufacture a
    disk-backed substitute here, or adopt a previous preparation's publication.
    """
    root = trusted(RUNTIME / 'native-view', directory=True)
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        info = os.fstat(fd)
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or
                stat.S_IMODE(info.st_mode) != 0o700 or os.listdir(fd)):
            raise ValueError('invocation-root-state')
        mount_id = [line.split()[1] for line in Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
                    if line.startswith('mnt_id:')]
        mounts = [line.split() for line in Path('/proc/self/mountinfo').read_text().splitlines()]
        selected = [row for row in mounts if mount_id == [row[0]]]
        if len(selected) != 1:
            raise ValueError('invocation-root-mount')
        row = selected[0]
        # The fixed product path needs no mountinfo escaping. Fixtures use an
        # explicit precondition double rather than qualifying kernel operations.
        if row[4] != str(root) or row[row.index('-') + 1] != 'tmpfs':
            raise ValueError('invocation-root-mount')
        limits = os.fstatvfs(fd)
        if (limits.f_blocks == 0 or limits.f_frsize == 0 or
                limits.f_blocks * limits.f_frsize > 512 * 1024 * 1024 or
                limits.f_files > MAX_ROWS + 8 or limits.f_files == 0):
            raise ValueError('invocation-root-bounds')
        runtime_label(root, backend, verify=True)
        return root
    finally:
        os.close(fd)


def protocol_text(value, *, absolute=False, relative=False):
    if (not isinstance(value, str) or not value or any(ord(c) < 32 or ord(c) == 127 for c in value)):
        raise ValueError('binding-protocol-path')
    try:
        if len(value.encode('utf-8')) >= MAX_PATH:
            raise ValueError('binding-protocol-path')
    except UnicodeEncodeError:
        raise ValueError('binding-protocol-path') from None
    if absolute or relative:
        parts = value.split('/')
        if absolute:
            if not value.startswith('/'):
                raise ValueError('binding-protocol-path')
            parts = parts[1:]
            if value == '/':
                parts = []
        elif value.startswith('/'):
            raise ValueError('binding-protocol-path')
        if any(part in ('', '.', '..') for part in parts):
            raise ValueError('binding-protocol-path')
    return value


def required_proofs(paths):
    """Record every checked component, including lexical alias target chains."""
    proofs = {}
    def remember(path):
        info = path.lstat()
        kind = ('link' if stat.S_ISLNK(info.st_mode) else
                'directory' if stat.S_ISDIR(info.st_mode) else
                'file' if stat.S_ISREG(info.st_mode) else 'other')
        if info.st_uid != 0 or (kind != 'link' and info.st_mode & 0o022) or kind == 'other':
            raise ValueError('untrusted-path')
        link = protocol_text(os.readlink(path)) if kind == 'link' else '-'
        record = (kind, str(path), link)
        if str(path) in proofs and proofs[str(path)] != record:
            raise ValueError('binding-proof-changed')
        proofs[str(path)] = record
        if len(proofs) > MAX_ROWS:
            raise ValueError('binding-protocol-limit')
        return kind, link
    for path in sorted(set(map(str, paths))):
        protocol_text(path, absolute=True)
        pending, current, links = path.split('/')[1:], Path('/'), 0
        while True:
            kind, link = remember(current)
            if kind == 'link':
                links += 1
                if links > 40:
                    raise ValueError('binding-proof-cycle')
                target = link.split('/')
                if link.startswith('/'):
                    current, target = Path('/'), target[1:]
                else:
                    current = current.parent
                pending = target + pending
            elif pending and kind != 'directory':
                raise ValueError('untrusted-ancestor')
            elif not pending:
                break
            if not pending:
                continue
            component = pending.pop(0)
            if component in ('', '.'):
                continue
            current = current.parent if component == '..' else current / component
        # A symlink in an ancestor changes the descriptor walk's spelling.
        # Retain the original required destination as an explicit assertion too.
        remember(Path(path))
    return [proofs[path] for path in sorted(proofs)]


def binding_protocol(config, records, preserved, identities, layout, generation, role):
    """Derive closed trust roles from attested configuration and measured inputs."""
    if (config['backend'] not in ('apparmor', 'selinux') or role not in ('manager', 'gate') or
            not re.fullmatch(r'[0-9a-f]{64}', generation.name)):
        raise ValueError('binding-protocol-header')
    if set(identities) != {record['path'] for record in preserved}:
        raise ValueError('binding-protocol-identity')
    covered, required, concrete = layout_requirements(config, [*records, *preserved])
    validate_required_layout(layout, concrete, [*records, *preserved])
    nodes, roots, replacements = {}, {}, {}
    for entry in layout:
        protocol_text(entry['path'], absolute=True)
        relative = protocol_text(str(Path(entry['path']).relative_to('/usr')), relative=True)
        kind = entry['kind']
        if kind not in ('tree', 'directory', 'empty-directory', 'file', 'link') or relative in nodes:
            raise ValueError('binding-protocol-layout')
        nodes[relative] = (kind, protocol_text(entry['link']) if kind == 'link' else '-')
    if len(nodes) > MAX_ROWS:
        raise ValueError('binding-protocol-limit')
    def root(path, kind, source='-'):
        path = protocol_text(str(path), absolute=True)
        if source != '-':
            source = protocol_text(str(source), absolute=True)
        previous = roots.get(path)
        if previous is None:
            roots[path] = (kind, str(source))
        elif previous != (kind, str(source)):
            if kind not in ('covered', 'alias', 'reserved'):
                raise ValueError('binding-protocol-overlap')
            priority = {'covered': 0, 'alias': 1, 'reserved': 2,
                        'native': 3, 'preserved': 3, 'marker': 3}
            if priority[kind] > priority[previous[0]]:
                roots[path] = (kind, str(source))
    for index, record in enumerate(records):
        source = generation / str(index)
        root(record['path'], 'native', source)
        replacements[record['path']] = str(source)
    for record in preserved:
        root(record['path'], 'preserved', record['path'])
        if record['path'] not in identities:
            raise ValueError('binding-protocol-identity')
    marker = str(PAYLOAD / 'generation')
    root(marker, 'marker', generation / 'generation')
    replacements[marker] = str(generation / 'generation')
    # Match each configured installed destination to the measured inventory;
    # the stream cannot independently rediscover an omitted configured root.
    measured = {record['path']: record for record in records}
    for entry in config.get('executables', []):
        paths = ([str(path) for path in trusted(entry['library_directory'], directory=True,
                                               symlinks=True).glob('libsystemd-*.so')]
                 if entry.get('library_directory') else entry['paths'])
        installed = 0
        selected = set(paths) & {alias for record in records for alias in record.get('aliases', [])}
        selected.update(name for name in paths if Path(name).exists())
        for name in sorted(selected):
            canonical = str(trusted(name, symlinks=True))
            if canonical not in measured or measured[canonical]['role'] != entry['role']:
                raise ValueError('binding-protocol-inventory')
            if entry.get('source') is not None and measured[canonical].get('source') != str(
                    trusted(entry['source'], symlinks=True)):
                raise ValueError('binding-protocol-inventory')
            installed += 1
            # Below an aliased directory the lexical leaf is a proof, not a
            # second dentry in the private tree. Its concrete link and target
            # dependencies are declared below, without following private links.
            if Path(name) in concrete:
                root(name, 'alias')
        if not installed and not entry.get('optional', False):
            raise ValueError('missing-executable')
    for entry in config.get('preserved_executables', []):
        if entry['path'] not in {record['path'] for record in preserved}:
            raise ValueError('binding-protocol-inventory')
    for name in config.get('reserved_directories', []):
        if Path(name) in concrete or name == '/usr':
            root(name, 'reserved')
        root(trusted(name, directory=True, symlinks=True), 'reserved')
    for directory in sorted(covered, key=str):
        root(directory, 'covered')
    for path, (kind, _) in concrete.items():
        if kind != 'link':
            continue
        try:
            trusted(path, directory=True, symlinks=True)
        except ValueError as error:
            if str(error) != 'unexpected-file-type':
                raise
            root(path, 'alias')
        else:
            root(path, 'covered')
    if len(roots) > MAX_ROWS:
        raise ValueError('binding-protocol-limit')
    for path, (kind, source) in roots.items():
        if path == '/usr':
            continue
        relative = protocol_text(str(Path(path).relative_to('/usr')), relative=True)
        if relative not in nodes:
            raise ValueError('binding-protocol-coverage')
        node = nodes[relative][0]
        if kind in ('native', 'preserved', 'marker') and node != 'file':
            raise ValueError('binding-protocol-coverage')
        if kind in ('covered', 'reserved') and node not in ('tree', 'link'):
            raise ValueError('binding-protocol-coverage')
    for relative in nodes:
        parent = Path(relative).parent
        while parent != Path('.'):
            if nodes.get(str(parent), (None,))[0] != 'tree':
                raise ValueError('binding-protocol-coverage')
            parent = parent.parent
    proof_paths = [path for path, (kind, _) in roots.items() if kind != 'marker']
    proof_paths.extend(map(str, required))
    proof_paths.extend(replacements.values())
    proof_paths.extend(record.get('source', record['path']) for record in records)
    proofs = required_proofs(proof_paths)
    final_proofs = {Path(path): (kind, link) for kind, path, link in proofs}
    if any(final_proofs.get(path) != proof for path, proof in required.items()):
        raise ValueError('binding-proof-changed')
    rows = [f'ONPC-KIOSK\t{PROTOCOL_VERSION}\t{config["backend"]}\t{role}\t{generation.name}\n']
    rows += [f'root\t{kind}\t{path}\t{source}\n' for path, (kind, source) in sorted(roots.items())]
    rows += [f'node\t{kind}\t{path}\t{link}\n' for path, (kind, link) in sorted(nodes.items())]
    rows += [f'proof\t{kind}\t{path}\t{link}\n' for kind, path, link in proofs]
    binds = 0
    for relative, (kind, _) in sorted(nodes.items()):
        if kind in ('tree', 'link', 'empty-directory'):
            continue
        path = '/usr/' + relative
        required = path in roots
        assertion = '-'
        if path in identities:
            values = identities[path]
            if (not required or len(values) != 8 or any(type(value) is not int or value < 0 or
                    value > 2**64 - 1 for value in values)):
                raise ValueError('binding-protocol-identity')
            assertion = ' '.join(map(str, values))
        rows.append(f'bind\t{"required" if required else "ambient"}\t{kind}\t'
                    f'{replacements.get(path, path)}\t{relative}\t{assertion}\n')
        binds += 1
    if binds > MAX_ROWS:
        raise ValueError('binding-protocol-limit')
    rows.append('attach\t/usr\n')
    data = ''.join(rows).encode('utf-8')
    if len(data) > MAX_MANIFEST:
        raise ValueError('binding-protocol-limit')
    return data


# The retained-material primitives below are deliberately not called by
# prepare(). Native M/V/ready composition belongs to 006. Selection below grants
# no admission authority without that transaction and its verified live clone.
# In particular, a published disk copy is never a retained mount source.
RUNTIME_COPY_FORMAT = 1
RUNTIME_ROLES = frozenset(('script', 'module', 'asset', 'wellbeing', 'unit', 'session-data'))
RUNTIME_KIOSK_MODULES = (
    '__init__ agent_locale chrome duration_controls floating_islands preference_dialog '
    'preset_dialog lava lava_artwork lightning main model request_content selection_store '
    'session_logout snowflakes thunder notifications whats_new whats_new_dialog').split()
RUNTIME_COMMON_MODULES = (
    '__init__ about accessibility gtk_automation app_policy diagnostic_events diagnostic_bundle '
    'diagnostic_privacy diagnostic_report diagnostics system_info duration errors feedback '
    'feedback_transport rich_text_editor user_icon languages localization message messages '
    'translation_widgets reboot application_ui application_ui_client whats_new release_markdown').split()
RUNTIME_LOCALES = (
    'ar be bg bn ca cs da de el en eo es et eu fa fi fr fur gl he hi hr hu id is it ja '
    'ka kk ko lt lv ml mr ms nb ne nl nn oc pa pl pt pt_BR ro ru sk sl sr sr_Latn '
    'sv ta te th tr ug uk ur uz vi zh_Hans zh_Hant').split()
# Packaging compiles every historical PO domain. The package-map regression
# requires deliberate updates when that finite production membership changes.
RUNTIME_RELEASE_CATALOGS = {'1.4': tuple(name for name in RUNTIME_LOCALES if name != 'en')}


def runtime_input_specs(distribution):
    """Exact production membership; keep aligned with Makefile's public payload.

    Only these two product trees are enumerated. In particular, this never
    recursively inventories Python/GI, distribution units or extension siblings.
    A future attested configuration must bind this membership before selection.
    """
    if distribution not in ('ubuntu', 'fedora'):
        raise ValueError('runtime-distribution')
    specs = {}

    def add(path, role, kind='file', link=None):
        specs[path] = dict(kind=kind, role=role)
        if link is not None:
            specs[path]['link'] = link

    def tree(root, members, role):
        add(root, role, 'directory')
        for name in members:
            relative = Path(name)
            for parent in reversed(relative.parents):
                if parent != Path('.'):
                    add(root + '/' + str(parent), role, 'directory')
            add(root + '/' + name, role)

    add('/usr/bin/oh-no-parent-control', 'script')
    add('/usr/bin/gnome-service-client', 'script')
    kiosk = '/usr/lib/oh-no-parent-control/kiosk'
    tree(kiosk, ['oh_no_parent_control_kiosk/' + name + '.py' for name in RUNTIME_KIOSK_MODULES] +
         ['oh_no_parent_control_kiosk/' + name for name in (
             'style.css', 'kiosk-background-still.png', 'kiosk-background-scenery-clear.png',
             'request-options.json', 'lava-heat.bin', 'fonts/Monocraft.ttf', 'fonts/OFL.txt')], 'module')
    common = '/usr/lib/oh-no-parent-control/common'
    tree(common, ['__init__.py'] +
         ['oh_no_parent_control_ui/' + name + '.py' for name in RUNTIME_COMMON_MODULES] +
         ['oh_no_parent_control_ui/' + name for name in (
             'diagnostic_catalog.json', 'diagnostic_timezones.json', 'languages.json',
             'feedback.css', 'rich_editor/application_ui.js', 'rich_editor/quill.js',
             'rich_editor/quill.snow.css', 'rich_editor/quill.js.LICENSE.txt',
             'rich_editor/LICENSE')], 'module')
    catalogs = ['oh_no_parent_control_ui/locale/' + name +
                '/LC_MESSAGES/oh-no-parent-control.mo' for name in RUNTIME_LOCALES]
    catalogs += ['oh_no_parent_control_ui/locale/' + language +
                 '/LC_MESSAGES/oh-no-parent-control-whats-new-' + release + '.mo'
                 for release, languages in RUNTIME_RELEASE_CATALOGS.items() for language in languages]
    tree(common, catalogs, 'module')
    for path, spec in specs.items():
        if path.startswith((kiosk + '/', common + '/')) and spec['kind'] == 'file' and not path.endswith(
                ('.py', '.js')):
            spec['role'] = 'asset'
    extension = '/usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com/'
    for name in ('wellbeingService.js', 'wellbeingLogic.mjs', 'schemas/gschemas.compiled'):
        add(extension + name, 'wellbeing')
    units = ['org.gnome.Kiosk@wayland.service.d/90-kiosk-confinement.conf']
    units += (['dbus-broker.service.d/90-kiosk-confinement.conf'] if distribution == 'fedora' else
              [name + '.d/90-kiosk-confinement.conf' for name in (
                  'dbus.service', 'oh-no-parent-control-wellbeing.service', 'wireplumber.service')])
    tree(str(PAYLOAD / 'user-units'), units, 'unit')
    if distribution == 'ubuntu':
        for name in ('snapd.session-agent.service', 'snapd.session-agent.socket',
                     'snap.snapd-desktop-integration.snapd-desktop-integration.service',
                     'snap.prompting-client.daemon.service',
                     'snap.firmware-updater.firmware-notifier.service',
                     'snap.firmware-updater.firmware-notifier.timer'):
            add(str(PAYLOAD / 'user-units' / name), 'unit', 'link', '/dev/null')
        tree(str(PAYLOAD / 'session-data'),
             ['dbus-1/services/' + name + '.service' for name in (
                 'io.snapcraft.Settings', 'io.snapcraft.Launcher')], 'session-data')
    return specs


def runtime_canonical(value):
    """One length-delimited, domain-separated encoding, without inode hashes."""
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')
    if len(data) > MAX_MANIFEST:
        raise ValueError('runtime-manifest-limit')
    return b'ONPC-KIOSK-RUNTIME\0' + len(data).to_bytes(8, 'big') + data


def runtime_identity(info):
    return tuple(file_identity(info))


def runtime_walk_identity(info):
    # Directory sibling changes do not replace the selected path or alter its
    # trust. Exact named payload-directory membership is measured separately;
    # files retain all eight transaction-local source assertion fields.
    if stat.S_ISDIR(info.st_mode):
        return info.st_dev, info.st_ino, info.st_mode, info.st_uid, info.st_gid
    return runtime_identity(info)


def runtime_mount_id(fd):
    rows = Path(f'/proc/self/fdinfo/{fd}').read_text().splitlines()
    identities = [line.split()[1] for line in rows if line.startswith('mnt_id:')]
    if len(identities) != 1 or not identities[0].isdecimal():
        raise ValueError('runtime-mount-identity')
    return identities[0]


def runtime_members(fd, *, limit=MAX_ROWS):
    names = set()
    with os.scandir(fd) as entries:
        for entry in entries:
            names.add(entry.name)
            if len(names) > limit:
                raise ValueError('runtime-membership-limit')
    return names


def runtime_owned_stat(info, kind, *, private=False):
    expected = {'file': stat.S_ISREG, 'directory': stat.S_ISDIR, 'link': stat.S_ISLNK}[kind]
    if (not expected(info.st_mode) or info.st_uid != 0 or info.st_gid != 0 or
            kind != 'link' and info.st_mode & 0o7022 or
            kind == 'file' and info.st_nlink != 1 or
            private and stat.S_IMODE(info.st_mode) != (0o700 if kind == 'directory' else 0o600)):
        raise ValueError('runtime-untrusted-object')


def runtime_open(path, *, directory=False):
    """Open every lexical component beneath /, refusing symlink ancestry.

    Return a CLOEXEC descriptor after rechecking every named/opened identity.
    No ambient link is followed, even for an intermediate source component.
    """
    path = protocol_text(str(path), absolute=True)
    current = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
    held = []
    try:
        runtime_owned_stat(os.fstat(current), 'directory')
        parts = path.split('/')[1:]
        for index, component in enumerate(parts):
            is_directory = index < len(parts) - 1 or directory
            before = os.stat(component, dir_fd=current, follow_symlinks=False)
            runtime_owned_stat(before, 'directory' if is_directory else 'file')
            flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK
            if is_directory:
                flags |= os.O_DIRECTORY
            child = os.open(component, flags, dir_fd=current)
            held.append((current, component, runtime_walk_identity(before)))
            current = child
            if runtime_walk_identity(os.fstat(current)) != runtime_walk_identity(before):
                raise ValueError('runtime-source-changed')
        for parent, component, identity in held:
            if runtime_walk_identity(os.stat(component, dir_fd=parent, follow_symlinks=False)) != identity:
                raise ValueError('runtime-source-changed')
        result, current = current, -1
        return result
    finally:
        if current >= 0:
            os.close(current)
        for parent, _, _ in held:
            os.close(parent)


def runtime_file_label(fd, backend, *, expected=None, write=False):
    if backend not in ('apparmor', 'selinux'):
        raise ValueError('unknown-backend')
    if backend == 'apparmor':
        if expected is not None:
            raise ValueError('runtime-label-changed')
        return None
    if write:
        if not isinstance(expected, str) or not expected:
            raise ValueError('runtime-label-changed')
        os.setxattr(fd, 'security.selinux', expected.encode('ascii') + b'\0')
    value = os.getxattr(fd, 'security.selinux').rstrip(b'\0').decode('ascii')
    # Copies retain the source's ordinary script/data label. The native
    # substitution labels are never granted to new runtime inputs.
    if (not re.fullmatch(r'[A-Za-z0-9_:.,\-]+', value) or
            re.search(r':onpc_kiosk_[a-z_]+_exec_t:', value) or
            expected is not None and value != expected):
        raise ValueError('runtime-label-changed')
    return value


def runtime_policy_label(path, mode):
    """Read the installed file-context policy for one declared source path."""
    library = ctypes.CDLL('libselinux.so.1', use_errno=True)
    library.selabel_open.argtypes = [ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint]
    library.selabel_open.restype = ctypes.c_void_p
    library.selabel_lookup_raw.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p),
                                           ctypes.c_char_p, ctypes.c_int]
    library.selabel_close.argtypes = [ctypes.c_void_p]
    library.freecon.argtypes = [ctypes.c_void_p]
    handle = library.selabel_open(0, None, 0)  # SELABEL_CTX_FILE, default policy.
    if not handle:
        raise OSError(ctypes.get_errno(), 'runtime-label-policy-unavailable')
    context = ctypes.c_char_p()
    try:
        if library.selabel_lookup_raw(handle, ctypes.byref(context), os.fsencode(path), mode) != 0:
            raise OSError(ctypes.get_errno(), 'runtime-label-policy-unavailable')
        return context.value.decode('ascii')
    finally:
        if context:
            library.freecon(context)
        library.selabel_close(handle)


def runtime_specs_valid(specs):
    if not isinstance(specs, dict) or not specs or len(specs) > MAX_ROWS:
        raise ValueError('runtime-membership')
    for path, spec in specs.items():
        protocol_text(path, absolute=True)
        if not path.startswith('/usr/') or not isinstance(spec, dict):
            raise ValueError('runtime-membership')
        kind = spec.get('kind')
        if (kind not in ('directory', 'file', 'link') or spec.get('role') not in RUNTIME_ROLES or
                set(spec) != ({'kind', 'role', 'link'} if kind == 'link' else {'kind', 'role'})):
            raise ValueError('runtime-membership')
        if kind == 'link':
            target = protocol_text(spec['link'])
            if target == '/dev/null' and spec['role'] == 'unit':
                continue
            # Only explicit links to another declared member are allowed.
            # No arbitrary host target is opened or copied.
            if target.startswith('/') or any(part in ('', '.', '..') for part in target.split('/')):
                raise ValueError('runtime-link-escape')
            if str(Path(path).parent / target) not in specs:
                raise ValueError('runtime-link-escape')


def runtime_cache_directory(fd, modules, *, limit=MAX_ROWS):
    """The sole production exclusion: validated CPython bytecode caches."""
    runtime_owned_stat(os.fstat(fd), 'directory')
    names = runtime_members(fd, limit=limit)
    for name in names:
        match = re.fullmatch(r'([A-Za-z_][A-Za-z0-9_]*)\.cpython-[0-9]+(?:\.opt-[0-9]+)?\.pyc', name)
        if match is None or match[1] not in modules:
            raise ValueError('runtime-membership')
        runtime_owned_stat(os.stat(name, dir_fd=fd, follow_symlinks=False), 'file')
    return len(names)


def runtime_read_digest(fd, size, *, target=-1):
    """Bound actual reads/writes even when a concurrent writer grows a source."""
    digest, remaining = hashlib.sha256(), size
    while True:
        data = os.read(fd, min(1024 * 1024, remaining + 1))
        if len(data) > remaining:
            raise ValueError('runtime-source-changed')
        if not data:
            if remaining:
                raise ValueError('runtime-source-changed')
            return digest.hexdigest()
        remaining -= len(data)
        digest.update(data)
        if target >= 0:
            pending = memoryview(data)
            while pending:
                written = os.write(target, pending)
                if written <= 0:
                    raise OSError('runtime-copy-write-failed')
                pending = pending[written:]


def runtime_records_valid(records, backend, *, used_rows=0, used_bytes=0):
    if (backend not in ('apparmor', 'selinux') or not isinstance(records, list) or
            type(used_rows) is not int or type(used_bytes) is not int or
            used_rows < 0 or used_bytes < 0 or used_rows + len(records) > MAX_ROWS):
        raise ValueError('runtime-budget')
    total, paths = used_bytes, []
    for record in records:
        if not isinstance(record, dict):
            raise ValueError('runtime-record-schema')
        kind = record.get('kind')
        fields = {'path', 'kind', 'role'}
        fields |= ({'sha256', 'size', 'mode', 'label'} if kind == 'file' else
                   {'link'} if kind == 'link' else set())
        if set(record) != fields:
            raise ValueError('runtime-record-schema')
        paths.append(record['path'])
        if kind == 'file':
            if (type(record['size']) is not int or record['size'] < 0 or
                    type(record['mode']) is not int or
                    record['mode'] != (0o755 if record['role'] == 'script' else 0o644) or
                    not isinstance(record['sha256'], str) or
                    not re.fullmatch(r'[0-9a-f]{64}', record['sha256']) or
                    backend == 'apparmor' and record['label'] is not None or
                    backend == 'selinux' and (not isinstance(record['label'], str) or
                        not re.fullmatch(r'[A-Za-z0-9_:.,\-]+', record['label']) or
                        re.search(r':onpc_kiosk_[a-z_]+_exec_t:', record['label']))):
                raise ValueError('runtime-record-schema')
            total += record['size']
    if total > MAX_COPY_BYTES or total < 0:
        raise ValueError('runtime-budget')
    if paths != sorted(set(paths)):
        raise ValueError('runtime-membership')
    specs = {record['path']: {key: record[key] for key in ('kind', 'role', 'link')
                             if key in record} for record in records}
    runtime_specs_valid(specs)
    return specs


def measure_runtime_inputs(specs, backend, *, used_rows=0, used_bytes=0):
    """Measure finite named payloads; assertions are transaction-local only."""
    runtime_specs_valid(specs)
    if (type(used_rows) is not int or type(used_bytes) is not int or
            used_rows < 0 or used_bytes < 0 or used_rows + len(specs) > MAX_ROWS or
            used_bytes > MAX_COPY_BYTES):
        raise ValueError('runtime-budget')
    records, assertions, consumed, scanned = [], {}, used_bytes, used_rows + len(specs)
    for path, spec in sorted(specs.items()):
        record = dict(path=path, **spec)
        if spec['kind'] == 'link':
            parent = runtime_open(Path(path).parent, directory=True)
            try:
                before = os.stat(Path(path).name, dir_fd=parent, follow_symlinks=False)
                runtime_owned_stat(before, 'link')
                if os.readlink(Path(path).name, dir_fd=parent) != spec['link']:
                    raise ValueError('runtime-source-changed')
                after = os.stat(Path(path).name, dir_fd=parent, follow_symlinks=False)
                if runtime_identity(before) != runtime_identity(after):
                    raise ValueError('runtime-source-changed')
                assertions[path] = runtime_identity(after)
            finally:
                os.close(parent)
        else:
            fd = runtime_open(path, directory=spec['kind'] == 'directory')
            try:
                before = os.fstat(fd)
                if spec['kind'] == 'directory':
                    wanted = {Path(name).name for name in specs if str(Path(name).parent) == path}
                    modules = {Path(name).stem for name in specs if str(Path(name).parent) == path and
                               specs[name]['kind'] == 'file' and name.endswith('.py')}
                    actual = runtime_members(fd)
                    if '__pycache__' in actual and spec['role'] == 'module' and modules:
                        cache = os.open('__pycache__', os.O_RDONLY | os.O_DIRECTORY |
                                        os.O_NOFOLLOW | os.O_CLOEXEC, dir_fd=fd)
                        try:
                            scanned += 1 + runtime_cache_directory(cache, modules,
                                                                    limit=MAX_ROWS - scanned)
                            if scanned > MAX_ROWS:
                                raise ValueError('runtime-budget')
                        finally:
                            os.close(cache)
                        actual.remove('__pycache__')
                    if actual != wanted:
                        raise ValueError('runtime-membership')
                else:
                    if 'security.capability' in os.listxattr(fd):
                        raise ValueError('runtime-privilege')
                    consumed += before.st_size
                    if consumed > MAX_COPY_BYTES:
                        raise ValueError('runtime-budget')
                    record['sha256'] = runtime_read_digest(fd, before.st_size)
                    expected_label = (runtime_policy_label(path, before.st_mode)
                                      if backend == 'selinux' else None)
                    record.update(size=before.st_size, mode=stat.S_IMODE(before.st_mode),
                                  label=runtime_file_label(fd, backend, expected=expected_label))
                after = os.fstat(fd)
                if runtime_identity(before) != runtime_identity(after):
                    raise ValueError('runtime-source-changed')
                assertions[path] = runtime_identity(after)
            finally:
                os.close(fd)
        records.append(record)
    # A changed required path is refused even when its replacement has the same
    # bytes. A new transaction can establish same-byte compatibility separately.
    check_runtime_assertions(specs, assertions)
    runtime_records_valid(records, backend, used_rows=used_rows, used_bytes=used_bytes)
    runtime_canonical(records)
    return records, assertions


def check_runtime_assertions(specs, assertions):
    if set(specs) != set(assertions):
        raise ValueError('runtime-source-identity')
    for path, spec in specs.items():
        parent = runtime_open(Path(path).parent, directory=True)
        try:
            info = os.stat(Path(path).name, dir_fd=parent, follow_symlinks=False)
            runtime_owned_stat(info, spec['kind'])
            if runtime_identity(info) != tuple(assertions[path]):
                raise ValueError('runtime-source-changed')
        finally:
            os.close(parent)


class RuntimeCopyPublication:
    """Identity-owned scratch and atomic, no-replace supporting-copy publication.

    The native caller must hold its preparation lock and admission lease. This
    object grants no admission/ready authority and performs no directory sweep.
    Keep its ticket with the owner if interruption recovery will be needed.
    """

    def __init__(self, root, backend, expected_specs):
        runtime_specs_valid(expected_specs)
        self.specs = json.loads(json.dumps(expected_specs, sort_keys=True))
        self.root, self.backend = Path(root), backend
        self.parent = runtime_open(root, directory=True)
        self.fd = -1
        self.name = None
        self.owned = {}
        self.published = False
        try:
            runtime_owned_stat(os.fstat(self.parent), 'directory', private=True)
            runtime_file_label(self.parent, backend, expected=(RUNTIME_CONTEXT.decode()
                                                              if backend == 'selinux' else None))
            self.parent_identity = runtime_identity(os.fstat(self.parent))[:2]
            self.mount = runtime_mount_id(self.parent)
            self.name = '.runtime-' + secrets.token_hex(16)
            os.mkdir(self.name, mode=0o700, dir_fd=self.parent)
            self.identity = runtime_identity(os.stat(self.name, dir_fd=self.parent,
                                                     follow_symlinks=False))[:2]
            self.fd = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                              os.O_CLOEXEC, dir_fd=self.parent)
            if runtime_identity(os.fstat(self.fd))[:2] != self.identity:
                raise ValueError('runtime-publication-replaced')
            runtime_owned_stat(os.fstat(self.fd), 'directory', private=True)
            runtime_file_label(self.fd, backend, expected=(RUNTIME_CONTEXT.decode()
                                                          if backend == 'selinux' else None),
                               write=backend == 'selinux')
        except BaseException as error:
            if hasattr(self, 'identity'):
                error.runtime_scratch_ticket = self.ticket()
                try:
                    reclaim_runtime_scratch(self.root, self.ticket())
                except BaseException as cleanup_error:
                    error.add_note('runtime-scratch-cleanup-failed: ' + type(cleanup_error).__name__)
            self.close()
            raise

    def ticket(self):
        return dict(format=RUNTIME_COPY_FORMAT, name=self.name, root=list(self.identity),
                    parent=list(self.parent_identity), members={name: list(identity)
                                                               for name, identity in self.owned.items()})

    def _check_root(self):
        named = runtime_open(self.root, directory=True)
        try:
            parent_identity = runtime_identity(os.fstat(named))[:2]
            parent_mount = runtime_mount_id(named)
        finally:
            os.close(named)
        named = os.open(self.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                        os.O_CLOEXEC, dir_fd=self.parent)
        try:
            scratch_identity = runtime_identity(os.fstat(named))[:2]
            scratch_mount = runtime_mount_id(named)
            runtime_owned_stat(os.fstat(named), 'directory', private=True)
        finally:
            os.close(named)
        if (runtime_identity(os.fstat(self.parent))[:2] != self.parent_identity or
                parent_identity != self.parent_identity or
                parent_mount != self.mount or scratch_mount != self.mount or
                scratch_identity != self.identity or
                runtime_mount_id(self.parent) != self.mount or runtime_mount_id(self.fd) != self.mount or
                runtime_identity(os.fstat(self.fd))[:2] != self.identity or
                runtime_identity(os.stat(self.name, dir_fd=self.parent,
                                         follow_symlinks=False))[:2] != self.identity):
            raise ValueError('runtime-publication-replaced')
        runtime_owned_stat(os.fstat(self.parent), 'directory', private=True)
        runtime_owned_stat(os.fstat(self.fd), 'directory', private=True)

    def _new_file(self, name):
        self._check_root()
        fd = os.open(name, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW |
                     os.O_CLOEXEC, 0o600, dir_fd=self.fd)
        try:
            self.owned[name] = runtime_identity(os.fstat(fd))[:2]
            return fd
        except BaseException as error:
            # The new name remains unknown unless its inode was recorded. Do
            # not invent ownership to remove it, but never leak its descriptor.
            error.runtime_scratch_ticket = self.ticket()
            os.close(fd)
            raise

    def copy(self, records, assertions, *, used_rows=0, used_bytes=0):
        # Only remeasured exact records are accepted. A forged producer record
        # cannot choose a path outside the independently selected finite set.
        specs = runtime_records_valid(records, self.backend, used_rows=used_rows, used_bytes=used_bytes)
        if specs != self.specs:
            raise ValueError('runtime-membership')
        measured, current = measure_runtime_inputs(specs, self.backend, used_rows=used_rows,
                                                   used_bytes=used_bytes)
        if measured != records or current != assertions:
            raise ValueError('runtime-source-changed')
        copies = []
        for index, record in enumerate(records):
            if record['kind'] != 'file':
                continue
            source = runtime_open(record['path'])
            target = -1
            try:
                if runtime_identity(os.fstat(source)) != tuple(assertions[record['path']]):
                    raise ValueError('runtime-source-changed')
                name = str(index)
                target = self._new_file(name)
                if runtime_read_digest(source, record['size'], target=target) != record['sha256']:
                    raise ValueError('runtime-source-changed')
                os.fchmod(target, record['mode'])
                runtime_file_label(target, self.backend, expected=record['label'],
                                   write=self.backend == 'selinux')
                os.fsync(target)
                info = os.fstat(target)
                runtime_owned_stat(info, 'file')
                if (runtime_identity(info)[:2] == runtime_identity(os.fstat(source))[:2] or
                        runtime_identity(os.fstat(source)) != tuple(assertions[record['path']])):
                    raise ValueError('runtime-source-changed')
                os.lseek(target, 0, os.SEEK_SET)
                if runtime_read_digest(target, record['size']) != record['sha256']:
                    raise ValueError('runtime-copy-changed')
                copies.append(dict(index=index, name=name, identity=list(runtime_identity(info))))
            finally:
                os.close(source)
                if target >= 0:
                    os.close(target)
        check_runtime_assertions(specs, assertions)
        manifest = dict(format=RUNTIME_COPY_FORMAT, backend=self.backend, records=records, copies=copies)
        data = runtime_canonical(manifest)
        record_fd = self._new_file('runtime.json')
        try:
            with os.fdopen(os.dup(record_fd), 'wb') as stream:
                stream.write(data)
                stream.flush()
            runtime_file_label(record_fd, self.backend,
                               expected=RUNTIME_CONTEXT.decode() if self.backend == 'selinux' else None,
                               write=self.backend == 'selinux')
            os.fsync(record_fd)
            manifest_identity = list(runtime_identity(os.fstat(record_fd)))
        finally:
            os.close(record_fd)
        os.fsync(self.fd)
        receipt = dict(format=RUNTIME_COPY_FORMAT, backend=self.backend, root=list(self.identity),
                       mount=self.mount,
                       manifest=hashlib.sha256(data).hexdigest(), manifest_identity=manifest_identity,
                       records=records, copies=copies)
        verify_runtime_copies(self.fd, receipt, self.backend, self.specs,
                              used_rows=used_rows, used_bytes=used_bytes)
        return receipt

    def publish(self, name, receipt):
        if not isinstance(name, str) or not re.fullmatch(r'[0-9a-f]{64}', name):
            raise ValueError('runtime-publication-name')
        self._check_root()
        verify_runtime_copies(self.fd, receipt, self.backend, self.specs)
        if sum(bool(re.fullmatch(r'[0-9a-f]{64}', item)) for item in runtime_members(self.parent)) >= 4:
            raise ValueError('generation-limit-reboot-required')
        # renameat2 NOREPLACE is atomic even against an empty foreign directory;
        # ordinary rename() would silently replace that directory.
        library = ctypes.CDLL(None, use_errno=True)
        rename = library.renameat2
        rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        if rename(self.parent, os.fsencode(self.name), self.parent, name.encode('ascii'), 1) != 0:
            raise OSError(ctypes.get_errno(), 'runtime-publication-failed')
        self.name, self.published = name, True
        os.fsync(self.parent)
        self._check_root()
        verify_runtime_copies(self.fd, receipt, self.backend, self.specs)
        return receipt

    def abort(self):
        if self.published:
            raise ValueError('runtime-completed-publication')
        self._check_root()
        reclaim_runtime_scratch(self.root, self.ticket())

    def close(self):
        for attribute in ('fd', 'parent'):
            fd = getattr(self, attribute, -1)
            if fd >= 0:
                os.close(fd)
                setattr(self, attribute, -1)

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        try:
            if not self.published:
                try:
                    self.abort()
                except BaseException as cleanup_error:
                    if error is None:
                        raise
                    error.runtime_scratch_ticket = self.ticket()
                    error.add_note('runtime-scratch-cleanup-failed: ' + type(cleanup_error).__name__)
        finally:
            self.close()
        return False


def verify_runtime_copies(fd, receipt, backend, expected_specs, *, used_rows=0, used_bytes=0,
                          extra_members=()):
    """Validate an independently retained receipt, never adopt a disk manifest.

    InitialPreparation independently verifies any declared native scratch
    members. Supporting-only publication passes no extras and refuses them.
    """
    if (not isinstance(receipt, dict) or set(receipt) != {
            'format', 'backend', 'root', 'mount', 'manifest', 'manifest_identity', 'records', 'copies'} or
            type(receipt['format']) is not int or receipt['format'] != RUNTIME_COPY_FORMAT or
            receipt['backend'] != backend or
            not isinstance(receipt['root'], list) or len(receipt['root']) != 2 or
            any(type(value) is not int or not 0 <= value <= 2**64 - 1 for value in receipt['root']) or
            not isinstance(receipt['mount'], str) or not receipt['mount'].isdecimal() or
            not isinstance(receipt['manifest'], str) or
            not re.fullmatch(r'[0-9a-f]{64}', receipt['manifest']) or
            not isinstance(receipt['manifest_identity'], list) or len(receipt['manifest_identity']) != 8 or
            any(type(value) is not int or not 0 <= value <= 2**64 - 1
                for value in receipt['manifest_identity']) or
            list(runtime_identity(os.fstat(fd))[:2]) != receipt['root'] or
            runtime_mount_id(fd) != receipt['mount']):
        raise ValueError('runtime-copy-identity')
    runtime_owned_stat(os.fstat(fd), 'directory', private=True)
    runtime_file_label(fd, backend,
                       expected=RUNTIME_CONTEXT.decode() if backend == 'selinux' else None)
    records, copies = receipt['records'], receipt['copies']
    specs = runtime_records_valid(records, backend, used_rows=used_rows, used_bytes=used_bytes)
    runtime_specs_valid(expected_specs)
    if specs != expected_specs:
        raise ValueError('runtime-membership')
    if not isinstance(copies, list):
        raise ValueError('runtime-record-schema')
    if len(records) != len(specs) or len(copies) != sum(record['kind'] == 'file' for record in records):
        raise ValueError('runtime-membership')
    expected = {str(index) for index, record in enumerate(records) if record['kind'] == 'file'}
    extras = set(extra_members)
    if (len(extras) != len(extra_members) or extras & (expected | {'runtime.json'}) or
            any(not isinstance(name, str) or not re.fullmatch(r'native-[0-9]+', name)
                for name in extras)):
        raise ValueError('runtime-membership')
    if runtime_members(fd, limit=MAX_ROWS + 1) != expected | {'runtime.json'} | extras:
        raise ValueError('runtime-membership')
    manifest = dict(format=RUNTIME_COPY_FORMAT, backend=backend, records=records, copies=copies)
    data = runtime_canonical(manifest)
    if hashlib.sha256(data).hexdigest() != receipt['manifest']:
        raise ValueError('runtime-copy-identity')
    runtime_owned_stat(os.stat('runtime.json', dir_fd=fd, follow_symlinks=False), 'file', private=True)
    record_fd = os.open('runtime.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                        os.O_NONBLOCK, dir_fd=fd)
    try:
        runtime_owned_stat(os.fstat(record_fd), 'file', private=True)
        if (list(runtime_identity(os.fstat(record_fd))) != receipt['manifest_identity'] or
                runtime_mount_id(record_fd) != receipt['mount']):
            raise ValueError('runtime-copy-identity')
        runtime_file_label(record_fd, backend,
                           expected=RUNTIME_CONTEXT.decode() if backend == 'selinux' else None)
        with os.fdopen(os.dup(record_fd), 'rb') as stream:
            if stream.read(MAX_MANIFEST + 32) != data:
                raise ValueError('runtime-copy-changed')
    finally:
        os.close(record_fd)
    seen = set()
    for copy in copies:
        if (not isinstance(copy, dict) or set(copy) != {'index', 'name', 'identity'} or
                not isinstance(copy['identity'], list) or len(copy['identity']) != 8 or
                any(type(value) is not int or not 0 <= value <= 2**64 - 1 for value in copy['identity']) or
                type(copy['index']) is not int or
                not 0 <= copy['index'] < len(records) or copy['name'] != str(copy['index']) or
                copy['name'] in seen or copy['name'] not in expected):
            raise ValueError('runtime-copy-identity')
        seen.add(copy['name'])
        record = records[copy['index']]
        runtime_owned_stat(os.stat(copy['name'], dir_fd=fd, follow_symlinks=False), 'file')
        source = os.open(copy['name'], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                         os.O_NONBLOCK, dir_fd=fd)
        try:
            before = os.fstat(source)
            runtime_owned_stat(before, 'file')
            if (list(runtime_identity(before)) != copy['identity'] or
                    runtime_mount_id(source) != receipt['mount'] or
                    stat.S_IMODE(before.st_mode) != record['mode'] or before.st_size != record['size'] or
                    'security.capability' in os.listxattr(source)):
                raise ValueError('runtime-copy-identity')
            runtime_file_label(source, backend, expected=record['label'])
            if runtime_read_digest(source, record['size']) != record['sha256']:
                raise ValueError('runtime-copy-changed')
            if runtime_identity(os.fstat(source)) != runtime_identity(before):
                raise ValueError('runtime-copy-identity')
            if runtime_identity(os.stat(copy['name'], dir_fd=fd,
                                        follow_symlinks=False)) != runtime_identity(before):
                raise ValueError('runtime-copy-identity')
        finally:
            os.close(source)
    if seen != expected:
        raise ValueError('runtime-membership')


def reclaim_runtime_scratch(root, ticket):
    """Remove only a named, identity-recorded incomplete flat copy attempt.

    Caller owns the exclusive preparation lock and has reaped its helper. All
    validation precedes deletion; foreign, mounted, hardlinked and unknown state
    remains intact. There is deliberately no prefix sweep or recursive rmtree.
    """
    if (not isinstance(ticket, dict) or set(ticket) != {'format', 'name', 'root', 'parent', 'members'} or
            type(ticket['format']) is not int or ticket['format'] != RUNTIME_COPY_FORMAT or
            any(not isinstance(ticket[key], list) or len(ticket[key]) != 2 or
                any(type(value) is not int or not 0 <= value <= 2**64 - 1 for value in ticket[key])
                for key in ('root', 'parent')) or
            not re.fullmatch(r'\.runtime-[0-9a-f]{32}', ticket['name']) or
            not isinstance(ticket['members'], dict) or len(ticket['members']) > MAX_ROWS + 1):
        raise ValueError('runtime-recovery-ticket')
    for name, identity in ticket['members'].items():
        if (not re.fullmatch(r'(?:(?:native-)?(?:0|[1-9][0-9]*)|runtime\.json)', name) or
                not isinstance(identity, list) or len(identity) != 2 or
                any(type(value) is not int or value < 0 for value in identity)):
            raise ValueError('runtime-recovery-ticket')
    parent = runtime_open(root, directory=True)
    fd = -1
    try:
        runtime_owned_stat(os.fstat(parent), 'directory', private=True)
        if list(runtime_identity(os.fstat(parent))[:2]) != ticket['parent']:
            raise ValueError('runtime-publication-replaced')
        fd = os.open(ticket['name'], os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW |
                     os.O_CLOEXEC, dir_fd=parent)
        runtime_owned_stat(os.fstat(fd), 'directory', private=True)
        if list(runtime_identity(os.fstat(fd))[:2]) != ticket['root']:
            raise ValueError('runtime-publication-replaced')
        # A same-device/inode bind mount still has another kernel mount ID.
        parent_mount = runtime_mount_id(parent)
        if (runtime_mount_id(fd) != parent_mount or
                runtime_members(fd, limit=MAX_ROWS + 1) != set(ticket['members'])):
            raise ValueError('runtime-recovery-membership')
        for name, identity in ticket['members'].items():
            runtime_owned_stat(os.stat(name, dir_fd=fd, follow_symlinks=False), 'file')
            child = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                            os.O_NONBLOCK, dir_fd=fd)
            try:
                runtime_owned_stat(os.fstat(child), 'file')
                if (list(runtime_identity(os.fstat(child))[:2]) != identity or
                        runtime_mount_id(child) != parent_mount):
                    raise ValueError('runtime-publication-replaced')
            finally:
                os.close(child)
        # Recheck every named object immediately before its owned unlink.
        for name, identity in ticket['members'].items():
            info = os.stat(name, dir_fd=fd, follow_symlinks=False)
            runtime_owned_stat(info, 'file')
            if list(runtime_identity(info)[:2]) != identity:
                raise ValueError('runtime-publication-replaced')
            os.unlink(name, dir_fd=fd)
        info = os.stat(ticket['name'], dir_fd=parent, follow_symlinks=False)
        runtime_owned_stat(info, 'directory', private=True)
        if list(runtime_identity(info)[:2]) != ticket['root']:
            raise ValueError('runtime-publication-replaced')
        os.rmdir(ticket['name'], dir_fd=parent)
        os.fsync(parent)
    finally:
        if fd >= 0:
            os.close(fd)
        os.close(parent)


MATERIAL_FORMAT = 1


def material_digest(record):
    """Material has its own versioned domain; source inode assertions are not M."""
    data = json.dumps(record, sort_keys=True, separators=(',', ':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')
    if len(data) > MAX_MANIFEST:
        raise ValueError('material-limit')
    return hashlib.sha256(b'ONPC-KIOSK-MATERIAL\0' + len(data).to_bytes(8, 'big') + data).hexdigest()


def material_file(path, backend, *, privileged=False, symlinks=True):
    """Measure a current required inode, separately from a retained source.

    trusted() owns the bounded lexical/target closure. An exact full assertion
    and a final named-path comparison close replacement during this observation.
    """
    canonical = trusted(path, symlinks=symlinks)
    before_name = canonical.stat()
    fd = os.open(canonical, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if (file_identity(before) != file_identity(before_name) or not stat.S_ISREG(before.st_mode) or
                before.st_uid != 0 or before.st_gid != 0 or before.st_mode & 0o022 or
                before.st_nlink != 1 or not privileged and before.st_mode & 0o6000 or
                'security.capability' in os.listxattr(fd)):
            raise ValueError('material-source-trust')
        if before.st_size > MAX_COPY_BYTES:
            raise ValueError('material-limit')
        digest = runtime_read_digest(fd, before.st_size)
        label = (os.getxattr(fd, 'security.selinux').rstrip(b'\0').decode('ascii')
                 if backend == 'selinux' else None)
        assertion = file_identity(before)
        if (file_identity(os.fstat(fd)) != assertion or
                file_identity(canonical.stat()) != assertion or
                trusted(path, symlinks=symlinks) != canonical):
            raise ValueError('material-source-changed')
        return digest, before.st_size, assertion, label
    finally:
        os.close(fd)


def required_material(config_bytes, policy_bytes, attestation):
    """Measure only required inputs. Never enumerate ambient host siblings.

    This is an unwired preparation operation, not an alternative to prepare().
    006 must supply the attested snapshot and retain native ownership/manager
    proof across this operation, selection, binding and final revalidation.
    """
    pair = [hashlib.sha256(data).hexdigest() for data in (config_bytes, policy_bytes)]
    if attestation != ' '.join(pair) + '\n':
        raise ValueError('policy-snapshot-not-attested')
    config = json.loads(config_bytes)
    backend = config['backend']
    if backend not in ('apparmor', 'selinux'):
        raise ValueError('unknown-backend')
    specs = config.get('runtime_inputs')
    if specs != runtime_input_specs('ubuntu' if backend == 'apparmor' else 'fedora'):
        raise ValueError('runtime-membership')
    runtime_specs_valid(specs)
    enforcing(config)
    native = inventory(config)
    preserved, vendor_assertions = preserved_inventory(config)
    _, required, _ = layout_requirements(config, [*native, *preserved])
    payload_paths = [PAYLOAD / 'config.json', PAYLOAD / (
        'onpc-kiosk.cil' if backend == 'selinux' else 'onpc-kiosk.apparmor')]
    paths = set(required) | set(payload_paths)
    paths.update(Path(record.get('source', record['path'])) for record in native)
    # Explicit mask links describe text, never /dev/null's special-file target.
    paths.update(Path(path).parent if spec['kind'] == 'link' else Path(path)
                 for path, spec in specs.items())
    proofs = required_proofs(paths)
    proof_map = {path: [kind, path, link] for kind, path, link in proofs}
    assertions, copied_bytes, payload = {}, 0, []
    for path, expected in zip(payload_paths, pair):
        digest, size, assertion, source_label = material_file(path, backend, symlinks=False)
        if digest != expected:
            raise ValueError('policy-snapshot-not-attested')
        assertions[str(path)] = assertion
        payload.append(dict(path=str(path), sha256=digest, size=size,
                            mode=stat.S_IMODE(assertion[5]), label=source_label))
    for record in native:
        source = record.get('source', record['path'])
        digest, size, assertion, source_label = material_file(source, backend)
        if digest != record['sha256']:
            raise ValueError('material-source-changed')
        record.update(size=size, source_label=source_label,
                      mode=0o644 if record['role'] in ('blocked', 'library') else 0o755,
                      label=(f'system_u:object_r:onpc_kiosk_{record["role"].replace("-", "_")}_exec_t:s0'
                             if backend == 'selinux' else None))
        assertions[source] = assertion
        copied_bytes += size
    for record in preserved:
        digest, size, assertion, label_value = material_file(record['path'], backend, privileged=True)
        if (digest != record['sha256'] or assertion != vendor_assertions[record['path']] or
                label_value != record['label']):
            raise ValueError('preserved-executable-changed')
        record['size'] = size
        assertions[record['path']] = assertion
    runtime, runtime_assertions = measure_runtime_inputs(
        specs, backend, used_rows=len(proofs) + len(native) + len(preserved), used_bytes=copied_bytes)
    for record in runtime:
        if record['kind'] == 'link':
            proof_map[record['path']] = ['link', record['path'], record['link']]
    proofs = [proof_map[path] for path in sorted(proof_map)]
    # Preserve path/inode identity within a transaction, but do not hash parent
    # timestamps or inode numbers. Sibling changes must not change material.
    for kind, path, _ in proofs:
        info = Path(path).lstat()
        assertions.setdefault(path, runtime_walk_identity(info))
    final_proofs = {path: [kind, path, link] for kind, path, link in required_proofs(paths)}
    for item in runtime:
        if item['kind'] == 'link':
            final_proofs[item['path']] = ['link', item['path'], item['link']]
    if final_proofs != proof_map:
        raise ValueError('material-source-changed')
    record = dict(format=MATERIAL_FORMAT, backend=backend, config=pair[0], policy=pair[1],
                  native=native, preserved=preserved, runtime=runtime, proofs=proofs, payload=payload)
    snapshot = dict(record=record, digest=material_digest(record), config=config, native=native,
                    preserved=preserved, runtime=runtime, proofs=proofs, assertions=assertions,
                    runtime_assertions=runtime_assertions, payload=payload)
    _check_material_assertions(snapshot)
    return snapshot


def _check_material_assertions(snapshot):
    for path, assertion in snapshot['assertions'].items():
        if runtime_walk_identity(Path(path).lstat()) != tuple(assertion):
            raise ValueError('material-source-changed')
    check_runtime_assertions(snapshot['config']['runtime_inputs'], snapshot['runtime_assertions'])


def verify_required_material(snapshot):
    """Repeat host trust/content checks without forgiving same-byte replacement.

    A later *fresh* transaction may accept identical reinstall. A replacement
    after this transaction's capture must refuse, even if M still matches.
    """
    _check_material_assertions(snapshot)
    config = snapshot['config']
    for path, expected in ((PAYLOAD / 'config.json', snapshot['record']['config']),
            (PAYLOAD / ('onpc-kiosk.cil' if config['backend'] == 'selinux' else 'onpc-kiosk.apparmor'),
             snapshot['record']['policy'])):
        digest, _, assertion, _ = material_file(path, config['backend'], symlinks=False)
        if digest != expected or assertion != tuple(snapshot['assertions'][str(path)]):
            raise ValueError('policy-snapshot-not-attested')
    enforcing(config)
    if json.loads((PAYLOAD / 'config.json').read_bytes()) != config:
        raise ValueError('policy-snapshot-not-attested')
    native = inventory(config)
    preserved, identities = preserved_inventory(config)
    expected_native = [{key: value for key, value in item.items()
                        if key not in ('size', 'mode', 'label', 'source_label')} for item in snapshot['native']]
    expected_preserved = [{key: value for key, value in item.items() if key != 'size'}
                          for item in snapshot['preserved']]
    if native != expected_native or preserved != expected_preserved:
        raise ValueError('material-source-changed')
    for item in snapshot['native'] + snapshot['preserved']:
        path = item.get('source', item['path'])
        digest, size, assertion, source_label = material_file(
            path, config['backend'], privileged=item in snapshot['preserved'])
        if (digest != item['sha256'] or size != item['size'] or
                source_label != item.get('source_label', item['label']) or
                assertion != tuple(snapshot['assertions'][path])):
            raise ValueError('material-source-changed')
    runtime, assertions = measure_runtime_inputs(config['runtime_inputs'], config['backend'],
        used_rows=len(snapshot['proofs']) + len(native) + len(preserved),
        used_bytes=sum(item['size'] for item in snapshot['native']))
    if runtime != snapshot['runtime'] or assertions != snapshot['runtime_assertions']:
        raise ValueError('material-source-changed')
    paths = [path for kind, path, _ in snapshot['proofs']
             if path not in config['runtime_inputs'] or config['runtime_inputs'][path]['kind'] != 'link']
    proofs = {path: [kind, path, link] for kind, path, link in required_proofs(paths)}
    for path, spec in config['runtime_inputs'].items():
        if spec['kind'] == 'link':
            proofs[path] = ['link', path, spec['link']]
    if [proofs[path] for path in sorted(proofs)] != snapshot['proofs']:
        raise ValueError('material-source-changed')
    if material_digest(snapshot['record']) != snapshot['digest']:
        raise ValueError('material-source-changed')
    _check_material_assertions(snapshot)


def initial_material_budget(snapshot, layout=()):
    """One budget for proof/layout rows and every independently copied byte."""
    groups = [snapshot[name] for name in ('native', 'preserved', 'runtime', 'payload', 'proofs')]
    if sum(map(len, groups)) + len(layout) + 1 > MAX_ROWS:
        raise ValueError('material-limit')
    copied = snapshot['native'] + snapshot['payload'] + [
        item for item in snapshot['runtime'] if item['kind'] == 'file']
    if any(type(item.get('size')) is not int or item['size'] < 0 for item in copied):
        raise ValueError('material-limit')
    total = sum(item['size'] for item in copied)
    if total > MAX_COPY_BYTES:
        raise ValueError('material-limit')
    # A destination cannot acquire two source classes or privileges.
    files = snapshot['native'] + snapshot['preserved'] + snapshot['payload'] + [
        item for item in snapshot['runtime'] if item['kind'] == 'file']
    if len({item['path'] for item in files}) != len(files):
        raise ValueError('retained-layout')
    return sum(map(len, groups)) + len(layout) + 1, total


def initial_directory_layout(snapshot, *, source_assertions=None):
    """Plan the initial private /usr with complete required-material coverage.

    This still scans ambient immediate entries, and is never used for a later
    retained invocation. Every ancestor of a runtime/payload copy is a tree,
    so no shallow host directory can cover one of those independent copies.
    Native realization must independently capture sources and record actual
    late omissions; this intended layout is not a realization receipt.
    """
    verify_required_material(snapshot)
    initial_material_budget(snapshot)
    files = snapshot['native'] + snapshot['preserved'] + snapshot['payload'] + [
        item for item in snapshot['runtime'] if item['kind'] == 'file']
    layout = directory_layout(snapshot['config'], files, material_proofs=snapshot['proofs'],
                              source_assertions=source_assertions)
    # Validated bytecode caches are intentionally absent from the finite product
    # payload. Binding their host directory would reintroduce mutable code.
    cache_paths = {str(Path(path) / '__pycache__') for path, spec in
                   snapshot['config']['runtime_inputs'].items()
                   if spec == {'kind': 'directory', 'role': 'module'}}
    layout = sorted((node for node in layout if node['path'] not in cache_paths),
                    key=lambda node: node['path'])
    if source_assertions is not None:
        for path in cache_paths:
            source_assertions.pop(path, None)
    _, _, concrete = layout_proof_requirements(snapshot['proofs'])
    validate_required_layout(layout, concrete, files)
    nodes = {node['path']: node for node in layout}
    for item in files:
        if any(nodes.get(str(parent), {}).get('kind') != 'tree'
               for parent in Path(item['path']).parents
               if parent not in (Path('/'), Path('/usr'))):
            raise ValueError('retained-layout')
    initial_material_budget(snapshot, layout)
    verify_required_material(snapshot)
    return layout


def initial_supporting_inputs(snapshot):
    """Runtime scripts/data and attested config/policy use ordinary copy roles."""
    records = [dict(item) for item in snapshot['runtime']]
    assertions = dict(snapshot['runtime_assertions'])
    for item in snapshot['payload']:
        # Policy/config files grant no native execution role. The production
        # package installs both at 0644; incompatible safe modes still refuse.
        records.append(dict(item, kind='file', role='asset'))
        assertions[item['path']] = snapshot['assertions'][item['path']]
    records.sort(key=lambda item: item['path'])
    used_rows = (len(snapshot['native']) + len(snapshot['preserved']) +
                 len(snapshot['proofs']) + 1)
    used_bytes = sum(item['size'] for item in snapshot['native'])
    specs = runtime_records_valid(records, snapshot['record']['backend'],
                                  used_rows=used_rows, used_bytes=used_bytes)
    return records, assertions, specs


class InitialPreparation:
    """Unwired initial plan and owned native/supporting copies, without admission.

    The native caller owns its lock, lease, source acquisition and deadline.
    This context owns only RuntimeCopyPublication's identity-recorded scratch
    and CLOEXEC descriptors. It removes scratch on exit unless the exact ticket
    and directory have been transferred to native; no ready generation, V or
    mount is published here. Native composition must acquire
    and independently verify these copies before a realization can be claimed.
    """

    def __init__(self, root, snapshot):
        self.publication = None
        # Freeze the producer's intent independently of later caller mutation.
        self.snapshot = copy.deepcopy(snapshot)
        self._layout_assertions = {}
        self.layout = initial_directory_layout(self.snapshot,
                                               source_assertions=self._layout_assertions)
        self.records, self.assertions, self.specs = initial_supporting_inputs(self.snapshot)
        self.used_rows = (initial_material_budget(self.snapshot, self.layout)[0] -
                          len(self.records))
        self.used_bytes = sum(item['size'] for item in self.snapshot['native'])
        backend = self.snapshot['record']['backend']
        publication = RuntimeCopyPublication(root, backend, self.specs)
        self.publication = publication
        try:
            self.receipt = publication.copy(self.records, self.assertions,
                used_rows=self.used_rows, used_bytes=self.used_bytes)
            self.native_copies = self._copy_native()
            self.sources = self._sources()
            self._intent = copy.deepcopy((self.layout, self.sources, self.native_copies,
                                          self.snapshot['native']))
            self.verify()
        except BaseException as error:
            publication.__exit__(type(error), error, error.__traceback__)
            self.publication = None
            raise

    def _native_label(self, fd, record, *, write=False):
        backend = self.snapshot['record']['backend']
        expected = (f'system_u:object_r:onpc_kiosk_{record["role"].replace("-", "_")}_exec_t:s0'
                    if backend == 'selinux' else None)
        if record['label'] != expected:
            raise ValueError('executable-label-changed')
        if backend == 'selinux':
            if write:
                os.setxattr(fd, 'security.selinux', expected.encode('ascii') + b'\0')
            if os.getxattr(fd, 'security.selinux').rstrip(b'\0').decode('ascii') != expected:
                raise ValueError('executable-label-changed')

    def _copy_native(self):
        copies = []
        for index, record in enumerate(self.snapshot['native']):
            origin = record.get('source', record['path'])
            assertion = tuple(self.snapshot['assertions'][origin])
            source = runtime_open(origin)
            target = -1
            try:
                if runtime_identity(os.fstat(source)) != assertion:
                    raise ValueError('material-source-changed')
                name = 'native-' + str(index)
                target = self.publication._new_file(name)
                if runtime_read_digest(source, record['size'], target=target) != record['sha256']:
                    raise ValueError('material-source-changed')
                os.fchmod(target, record['mode'])
                self._native_label(target, record, write=True)
                os.fsync(target)
                info = os.fstat(target)
                runtime_owned_stat(info, 'file')
                if (runtime_identity(info)[:2] == assertion[:2] or
                        runtime_identity(os.fstat(source)) != assertion):
                    raise ValueError('material-source-changed')
                copies.append(dict(index=index, name=name, identity=list(runtime_identity(info))))
            finally:
                os.close(source)
                if target >= 0:
                    os.close(target)
        os.fsync(self.publication.fd)
        return copies

    def _verify_native(self):
        if len(self.native_copies) != len(self.snapshot['native']):
            raise ValueError('runtime-copy-identity')
        for index, (member, record) in enumerate(zip(self.native_copies, self.snapshot['native'])):
            if (set(member) != {'index', 'name', 'identity'} or
                    type(member['index']) is not int or member['index'] != index or
                    member['name'] != 'native-' + str(index) or
                    self.publication.owned.get(member['name']) != tuple(member['identity'][:2])):
                raise ValueError('runtime-copy-identity')
            source = os.open(member['name'], os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC |
                             os.O_NONBLOCK, dir_fd=self.publication.fd)
            try:
                before = os.fstat(source)
                runtime_owned_stat(before, 'file')
                origin = record.get('source', record['path'])
                if (list(runtime_identity(before)) != member['identity'] or
                        runtime_identity(before)[:2] == tuple(self.snapshot['assertions'][origin][:2]) or
                        runtime_mount_id(source) != self.publication.mount or
                        stat.S_IMODE(before.st_mode) != record['mode'] or
                        record['mode'] != (0o644 if record['role'] in ('blocked', 'library') else 0o755) or
                        before.st_size != record['size'] or 'security.capability' in os.listxattr(source)):
                    raise ValueError('runtime-copy-identity')
                self._native_label(source, record)
                if runtime_read_digest(source, record['size']) != record['sha256']:
                    raise ValueError('runtime-copy-changed')
                if (runtime_identity(os.fstat(source)) != runtime_identity(before) or
                        runtime_identity(os.stat(member['name'], dir_fd=self.publication.fd,
                                                 follow_symlinks=False)) != runtime_identity(before)):
                    raise ValueError('runtime-copy-identity')
            finally:
                os.close(source)

    def _sources(self):
        runtime = {item['path']: index for index, item in enumerate(self.records)}
        copies = {item['index']: item for item in self.receipt['copies']}
        native = {item['path']: index for index, item in enumerate(self.snapshot['native'])}
        vendor = {item['path']: index for index, item in enumerate(self.snapshot['preserved'])}
        payload = {item['path'] for item in self.snapshot['payload']}
        required = {path for _, path, _ in self.snapshot['proofs']}
        sources = {}
        for source_index, node in enumerate([dict(path='/usr', kind='tree'), *self.layout]):
            path, kind = node['path'], node['kind']
            # source_index is the stable layout slot used by V/I. Class-local
            # index below identifies a native/runtime/vendor input or copy;
            # these are different namespaces and must never be interchanged.
            source = dict(kind=kind, required=path in required, source_index=source_index,
                          source_class='ambient' if kind == 'empty-directory' else 'skeleton')
            if kind == 'link':
                source['link'] = node['link']
            if path in native:
                index = native[path]
                record = self.snapshot['native'][index]
                origin = record.get('source', path)
                source.update(source_class='native', index=index, path=origin,
                              assertion=list(self.snapshot['assertions'][origin]),
                              record=dict(record), name=self.native_copies[index]['name'],
                              copy_identity=list(self.native_copies[index]['identity']))
            elif path in runtime and kind == 'file':
                index = runtime[path]
                source.update(source_class='payload' if path in payload else 'runtime',
                              index=index, name=copies[index]['name'],
                              assertion=list(self.assertions[path]),
                              copy_identity=list(copies[index]['identity']),
                              record=dict(self.records[index]))
            elif path in vendor:
                source.update(source_class='vendor', index=vendor[path], path=path,
                              assertion=list(self.snapshot['assertions'][path]),
                              record=dict(self.snapshot['preserved'][vendor[path]]))
            elif kind in ('file', 'directory', 'link'):
                # Inventory captured this exact original source once. Native
                # alone observes later trust/availability and either binds that
                # inode or records omission/masking in actual V. No later host
                # name is reopened here, including after identical replacement.
                source.update(source_class='alias' if kind == 'link' and path in required
                              else 'ambient', path=path, index=source_index,
                              assertion=list(self._layout_assertions[path]))
            sources[path] = source
        return sources

    def plan(self):
        self.verify()
        # No digest of this intended plan is represented as V or I.
        data = json.dumps(dict(format=1, material=self.snapshot['digest'],
            backend=self.snapshot['record']['backend'], layout=self.layout,
            sources=self.sources, runtime=self.receipt, proofs=self.snapshot['proofs'],
            native=dict(records=self.snapshot['native'], copies=self.native_copies)), sort_keys=True,
            separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')
        if len(data) > MAX_MANIFEST:
            raise ValueError('material-limit')
        return json.loads(data)

    def verify(self):
        """Recheck required material/copies and static intent, not ambient trust.

        Late ambient acquisition, refusal and actual omission/masking belong to
        native realization; frozen host provenance grants no binding authority.
        """
        if self.publication is None:
            raise ValueError('runtime-publication-replaced')
        self.publication._check_root()
        verify_runtime_copies(self.publication.fd, self.receipt,
            self.snapshot['record']['backend'], self.specs,
            used_rows=self.used_rows, used_bytes=self.used_bytes,
            extra_members=[member['name'] for member in self.native_copies])
        if (self.records != self.receipt['records'] or
                (self.layout, self.sources, self.native_copies, self.snapshot['native']) != self._intent):
            raise ValueError('material-source-changed')
        self._verify_native()
        initial_material_budget(self.snapshot, self.layout)
        verify_required_material(self.snapshot)

    def ticket(self):
        return self.publication.ticket()

    def detach(self):
        """Transfer the exact incomplete scratch to the native channel owner.

        Call only after sending the plan, cleanup ticket and copy-directory
        descriptor successfully. Native must reap this helper and independently
        verify the named objects before using or publishing them. This operation
        grants no completed realization or ready authority.
        """
        self.verify()
        publication, self.publication = self.publication, None
        ticket = publication.ticket()
        publication.close()
        return ticket

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        publication, self.publication = self.publication, None
        if publication is not None:
            return publication.__exit__(kind, error, traceback)
        return False


def retained_source_assertion(fd, identity, node, required, item, backend, preserved):
    """Observe one source FD; callers narrow only eligible ambient source errors."""
    before = os.fstat(fd)
    if file_identity(before)[:2] != tuple(identity):
        raise ValueError('retained-source-identity')
    kind = node['kind']
    valid_kind = (stat.S_ISLNK(before.st_mode) if kind == 'link' else
                  stat.S_ISREG(before.st_mode) if kind == 'file' else stat.S_ISDIR(before.st_mode))
    safe = (valid_kind and before.st_uid == 0 and
            (kind == 'link' or not before.st_mode & 0o022))
    if kind == 'link' and safe:
        safe = os.readlink('', dir_fd=fd) == node['link']
    if not safe:
        if required:
            raise ValueError('retained-required-source')
        return None
    if item is not None:
        if (before.st_gid != 0 or before.st_nlink not in ((0, 1) if preserved else (1,)) or
                stat.S_IMODE(before.st_mode) != item['mode'] or before.st_size != item['size'] or
                'security.capability' in os.listxattr(fd)):
            raise ValueError('retained-required-source')
        value = (os.getxattr(fd, 'security.selinux').rstrip(b'\0').decode('ascii')
                 if backend == 'selinux' else None)
        if value != item['label']:
            raise ValueError('retained-required-source')
        os.lseek(fd, 0, os.SEEK_SET)
        if runtime_read_digest(fd, item['size']) != item['sha256']:
            raise ValueError('retained-required-source')
    if file_identity(os.fstat(fd)) != file_identity(before):
        raise ValueError('retained-source-changed')
    return file_identity(before)


class RetainedSourceProjection:
    """Bounded local opens beneath the single native-owned recursive clone.

    Native must first verify the receipt, clone and this finite inode projection.
    This adapter grants no acquisition authority. At most one leaf is borrowed
    at a time; callers must consume it before looking up another entry. Every
    parent and final node is opened without following links. A descriptor-backed
    reopen of an already checked regular inode permits hashing an O_PATH clone
    source without ever reopening its host name.
    """
    def __init__(self, root_fd, entries):
        self.root = self.leaf = -1
        if (type(root_fd) is not int or root_fd < 0 or not isinstance(entries, dict) or
                not entries or len(entries) > MAX_ROWS or '/usr' not in entries):
            raise ValueError('retained-source-identity')
        self.entries = {}
        for path, entry in entries.items():
            protocol_text(path, absolute=True)
            if (path != '/usr' and not path.startswith('/usr/') or
                    not isinstance(entry, dict) or set(entry) != {'kind', 'identity'} or
                    entry['kind'] not in ('tree', 'directory', 'file', 'link') or
                    not isinstance(entry['identity'], (list, tuple)) or len(entry['identity']) != 2 or
                    any(type(value) is not int or not 0 <= value <= 2**64 - 1
                        for value in entry['identity'])):
                raise ValueError('retained-source-identity')
            self.entries[path] = dict(kind=entry['kind'], identity=tuple(entry['identity']))
        if self.entries['/usr']['kind'] != 'tree':
            raise ValueError('retained-source-identity')
        for path in self.entries:
            if any(self.entries.get(str(parent), {}).get('kind') != 'tree'
                   for parent in Path(path).parents if parent not in (Path('/'),)):
                raise ValueError('retained-source-identity')
        self.root = os.dup(root_fd)
        try:
            os.set_inheritable(self.root, False)
            info = os.fstat(self.root)
            if (not stat.S_ISDIR(info.st_mode) or
                    file_identity(info)[:2] != self.entries['/usr']['identity']):
                raise ValueError('retained-source-identity')
        except BaseException:
            self.close()
            raise

    def __len__(self):
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self, path):
        entry = self.entries[path]
        if self.leaf >= 0:
            os.close(self.leaf)
            self.leaf = -1
        if self.root < 0:
            raise ValueError('retained-source-identity')
        current = os.dup(self.root)
        try:
            walked = '/usr'
            for part in path.split('/')[2:]:
                child = os.open(part, os.O_PATH | os.O_NOFOLLOW | os.O_CLOEXEC,
                                dir_fd=current)
                os.close(current)
                current = child
                walked += '/' + part
                observed, expected = os.fstat(current), self.entries[walked]
                if (file_identity(observed)[:2] != expected['identity'] or
                        walked != path and not stat.S_ISDIR(observed.st_mode)):
                    raise ValueError('retained-source-identity')
            info = os.fstat(current)
            kind = entry['kind']
            if (file_identity(info)[:2] != entry['identity'] or
                    (stat.S_IFMT(info.st_mode) != (
                        stat.S_IFLNK if kind == 'link' else stat.S_IFREG if kind == 'file'
                        else stat.S_IFDIR))):
                raise ValueError('retained-source-identity')
            if kind == 'file':
                readable = os.open('/proc/self/fd/' + str(current),
                                   os.O_RDONLY | os.O_NONBLOCK | os.O_CLOEXEC)
                if file_identity(os.fstat(readable)) != file_identity(info):
                    os.close(readable)
                    raise ValueError('retained-source-changed')
                os.close(current)
                current = readable
            self.leaf, current = current, -1
            return dict(fd=self.leaf, identity=entry['identity'])
        finally:
            if current >= 0:
                os.close(current)

    def close(self):
        if self.leaf >= 0:
            os.close(self.leaf)
            self.leaf = -1
        if self.root >= 0:
            os.close(self.root)
            self.root = -1

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()


def select_retained_material(current, retained_record, layout, pins, *, source_slots=None):
    """Select a fresh layout from a native-verified receipt/clone projection.

    pins maps canonical /usr names to caller-owned descriptors plus original
    (device,inode) provenance. This function neither opens a host ambient path
    nor acquires/attests a clone, parses a ready receipt, publishes or attaches.
    Only 006's native owner can supply that authority. Descriptors stay with the
    caller; returned indices/assertions are bound again by native before use.
    source_slots is the native-verified V path-to-slot map, including original
    masks and absences. Never number sources from the surviving descriptor set.
    The default is useful for initial, contiguous plans only; production receipt
    callers must pass the original slots, which may contain gaps.
    """
    verify_required_material(current)
    if (retained_record != current['record'] or
            material_digest(retained_record) != current['digest']):
        raise ValueError('manager-material-stale')
    if (not isinstance(layout, list) or len(layout) > MAX_ROWS or
            not isinstance(pins, (dict, RetainedSourceProjection))):
        raise ValueError('retained-layout')
    nodes = {}
    for entry in layout:
        if not isinstance(entry, dict) or entry.get('kind') not in (
                'tree', 'directory', 'empty-directory', 'file', 'link', 'absent'):
            raise ValueError('retained-layout')
        path, kind = protocol_text(entry.get('path'), absolute=True), entry['kind']
        if (not path.startswith('/usr/') or path in nodes or
                set(entry) != ({'path', 'kind', 'link'} if kind == 'link' else {'path', 'kind'})):
            raise ValueError('retained-layout')
        if kind == 'link':
            protocol_text(entry['link'])
        nodes[path] = entry
    for path in nodes:
        if any(nodes.get(str(parent), {}).get('kind') != 'tree'
               for parent in Path(path).parents if parent not in (Path('/usr'), Path('/'))):
            raise ValueError('retained-layout')
    proofs = {Path(path): (kind, link) for kind, path, link in current['proofs']}
    concrete = {path: proof for path, proof in proofs.items()
                if path != Path('/usr') and Path('/usr') in path.parents and
                not any(proofs.get(parent, (None,))[0] == 'link' for parent in path.parents)}
    validate_required_layout(layout, concrete, [*current['native'], *current['preserved']])
    required = {'/usr'} | {str(path) for path in concrete}
    paths = sorted({'/usr', *nodes})
    if source_slots is None:
        source_slots = dict(zip(paths, range(len(paths))))
    if (not isinstance(source_slots, dict) or set(source_slots) != set(paths) or
            any(type(source_slots[path]) is not int or
                not 0 <= source_slots[path] < 2**63 for path in paths) or
            any(source_slots[left] >= source_slots[right]
                for left, right in zip(paths, paths[1:]))):
        raise ValueError('retained-source-identity')
    # Freeze the selected domain before any descriptor access or omission.
    source_slots = dict(source_slots)
    if any(nodes.get(path, {}).get('kind') in ('absent', 'empty-directory') for path in required):
        raise ValueError('retained-required-source')
    files = current['native'] + current['preserved'] + current['runtime'] + current.get('payload', [])
    expected = {item['path']: item for item in files if item.get('kind', 'file') == 'file'}
    # Runtime/native overlap would make source class and privilege ambiguous.
    if len(expected) != sum(item.get('kind', 'file') == 'file' for item in files):
        raise ValueError('retained-layout')
    if not set(expected) <= required:
        raise ValueError('retained-layout')
    if (len(nodes) + len(current['native']) + len(current['preserved']) +
            len(current['runtime']) + len(proofs) > MAX_ROWS):
        raise ValueError('material-limit')
    if set(pins) != {'/usr'} | {path for path, node in nodes.items()
                              if node['kind'] not in ('empty-directory', 'absent')}:
        raise ValueError('retained-source-identity')
    result, sources = [], {}
    vendor = {item['path'] for item in current['preserved']}
    for path in sorted(pins):
        index = source_slots[path]
        node = nodes.get(path, {'path': '/usr', 'kind': 'tree'})
        try:
            pin = pins[path]
        except OSError as error:
            if path in required or error.errno not in (errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE):
                raise
            if node['kind'] == 'directory':
                result.append(dict(path=path, kind='empty-directory'))
            continue
        if (not isinstance(pin, dict) or set(pin) != {'fd', 'identity'} or
                type(pin['fd']) is not int or pin['fd'] < 0 or
                not isinstance(pin['identity'], (tuple, list)) or len(pin['identity']) != 2 or
                any(type(value) is not int or value < 0 for value in pin['identity'])):
            raise ValueError('retained-source-identity')
        fd = pin['fd']
        try:
            assertion = retained_source_assertion(fd, pin['identity'], node, path in required,
                expected.get(path), current['record']['backend'], path in vendor)
        except OSError as error:
            if path in required or error.errno not in (errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE):
                raise
            assertion = None
        if assertion is None:
            if node['kind'] == 'directory':
                result.append(dict(path=path, kind='empty-directory'))
            continue
        sources[path] = dict(index=index, assertion=assertion)
        if path != '/usr':
            result.append(dict(node))
    result += [dict(node) for node in layout if node['kind'] == 'empty-directory']
    result.sort(key=lambda item: item['path'])
    validate_required_layout(result, concrete, [*current['native'], *current['preserved']])
    verify_required_material(current)
    for path, source in list(sources.items()):
        try:
            assertion = file_identity(os.fstat(pins[path]['fd']))
        except OSError as error:
            if path in required or error.errno not in (errno.EACCES, errno.EPERM, errno.EIO, errno.ESTALE):
                raise
            # This last observation may only narrow the fresh invocation. It
            # cannot revive a previously omitted source or change source V.
            del sources[path]
            result = [node for node in result if node['path'] != path]
            if nodes[path]['kind'] == 'directory':
                result.append(dict(path=path, kind='empty-directory'))
            continue
        if assertion != source['assertion']:
            raise ValueError('retained-source-changed')
    result.sort(key=lambda item: item['path'])
    validate_required_layout(result, concrete, [*current['native'], *current['preserved']])
    return dict(material=current['digest'], layout=result, sources=sources,
                source_slots=source_slots)


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
    # Check the actual post-inventory layout before manager matching or writes,
    # even when a measured substitution source remains available elsewhere.
    _, _, concrete = layout_requirements(config, [*records, *preserved])
    validate_required_layout(layout, concrete, [*records, *preserved])
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
    invocation = verify_invocation_root(config['backend'])
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
    if trusted(generation / 'generation').read_text() != digest + '\n':
        raise ValueError('generation-changed')
    verify_tree(generation / 'tree', layout)
    for index, record in enumerate(records):
        target = trusted(generation / str(index))
        if hashlib.sha256(target.read_bytes()).hexdigest() != record['sha256']:
            raise ValueError('copy-changed')
        verify_label(target, record['role'], config['backend'])
    stage = 'bindings'
    bindings = binding_protocol(config, records, preserved, identities, layout, generation, role)
    make_tree(invocation / 'tree', layout)
    for path in (invocation / 'tree', *(invocation / 'tree').rglob('*')):
        runtime_label(path, config['backend'])
    verify_tree(invocation / 'tree', layout)
    for path in (invocation / 'tree', *(invocation / 'tree').rglob('*')):
        runtime_label(path, config['backend'], verify=True)
    fd, name = tempfile.mkstemp(prefix='.bindings-', dir=invocation)
    pending = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(bindings)
            stream.flush()
            os.fsync(stream.fileno())
        runtime_label(pending, config['backend'])
        pending.replace(invocation / 'bindings')
        runtime_label(invocation / 'bindings', config['backend'], verify=True)
    finally:
        pending.unlink(missing_ok=True)


def native_preparation_service(deadline_ns):
    """Load only checked installed support bytes in the isolated interpreter.

    Do not add a directory to Python's import search or consume bytecode caches.
    The native caller's original deadline also bounds this bootstrap through
    its pidfd owner. Each support file keeps its named full identity across read.
    """
    import types
    import time

    def before():
        now = time.monotonic_ns()
        if not now < deadline_ns <= now + 60_000_000_000:
            raise TimeoutError('preparation-deadline')

    before()
    sys.modules['kiosk_confinement'] = sys.modules[__name__]
    for name in ('kiosk_preparation_input', 'kiosk_view_receipt', 'kiosk_preparation_service'):
        before()
        path = trusted(NATIVE_SUPPORT / (name + '.py'))
        fd = runtime_open(path)
        try:
            info = os.fstat(fd)
            runtime_owned_stat(info, 'file')
            if info.st_nlink != 1 or not 0 < info.st_size <= MAX_MANIFEST:
                raise ValueError('untrusted-path')
            parts, offset = [], 0
            while offset < info.st_size:
                before()
                data = os.pread(fd, min(65536, info.st_size - offset), offset)
                if not data:
                    raise ValueError('source-changed')
                parts.append(data)
                offset += len(data)
            named = runtime_open(path)
            try:
                unchanged = file_identity(os.fstat(named)) == file_identity(info)
            finally:
                os.close(named)
            if not unchanged or file_identity(os.fstat(fd)) != file_identity(info):
                raise ValueError('source-changed')
        finally:
            os.close(fd)
        module = types.ModuleType(name)
        module.__file__, module.__package__ = str(path), ''
        sys.modules[name] = module
        exec(compile(b''.join(parts), str(path), 'exec'), module.__dict__)
    before()
    return sys.modules['kiosk_preparation_service']


def prepare_native_channel(role, channel_text, deadline_text):
    """The fixed native child entry; descriptors and deadline confer no admission."""
    import socket
    import fcntl
    import time

    if (os.geteuid() != 0 or role not in ('manager', 'gate') or channel_text != '3' or
            not re.fullmatch(r'[1-9][0-9]{0,19}', deadline_text) or
            not 0 < int(deadline_text) < 2**64):
        raise ValueError('invalid-arguments')
    deadline_ns = int(deadline_text)
    now = time.monotonic_ns()
    if not now < deadline_ns <= now + 60_000_000_000:
        raise TimeoutError('preparation-deadline')
    os.umask(0o077)
    seen = set()
    for fd, path in NATIVE_LOCKS:
        info, named = os.fstat(fd), path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or
                stat.S_IMODE(info.st_mode) != 0o600 or info.st_nlink != 1 or
                file_identity(info) != file_identity(named) or
                (info.st_dev, info.st_ino) in seen or
                fcntl.fcntl(fd, fcntl.F_GETFL) & os.O_ACCMODE != os.O_RDWR):
            raise ValueError('unowned-preparation')
        seen.add((info.st_dev, info.st_ino))
        os.set_inheritable(fd, False)
    with socket.socket(fileno=3) as channel:
        os.set_inheritable(channel.fileno(), False)
        if (channel.family != socket.AF_UNIX or channel.type != socket.SOCK_SEQPACKET or
                channel.getsockname() or channel.getpeername()):
            raise ValueError('unowned-preparation')
        service = native_preparation_service(deadline_ns)
        service.serve(channel, role=role, deadline_ns=deadline_ns)


def main():
    native = len(sys.argv) == 5 and sys.argv[1] == '--native-channel'
    role = sys.argv[2] if native else sys.argv[1] if len(sys.argv) == 2 else 'other'
    try:
        if native:
            prepare_native_channel(role, sys.argv[3], sys.argv[4])
        elif len(sys.argv) == 2:
            prepare(role)
        else:
            raise ValueError('invalid-arguments')
    except Exception as error:
        report_preparation_failure(error, role)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
