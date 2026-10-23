"""Finite guest fixture mechanics, shared by guarded SSH and private doubles.

No lifecycle, input dispatcher, rollback, retry or process supervisor lives here.
The enclosing VM owner restores its snapshot after any uncertain operation.
"""
from contextlib import ExitStack, contextmanager
import grp
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import pwd
import re
import stat
import subprocess
import time
from types import SimpleNamespace

try:
    import guest_files
    import native_assets
    import baseline_assets
    import native_trust
    import fixture_manifest
except ImportError:
    from tests.e2e import guest_files
    from tests.fixtures import native_assets, baseline_assets, native_trust
    from tools import fixture_manifest

LIMIT = 8 * 1024 * 1024
TRUST = '/etc/fapolicyd/trust.d/onpc-fixture-runtime.trust'
HEX = re.compile(r'[0-9a-f]{64}')


def require(value, reason='refused'):
    if not value:
        raise ValueError('fixture-guest:' + reason)


def sha(data):
    return hashlib.sha256(data).hexdigest()


class Files:
    """Pinned ordinary files; private roots and UID maps are host-test seams."""
    def __init__(self, root='/', *, uid_map=None, gid_map=None):
        self.root = Path(root)
        self.uid_map = uid_map or (lambda uid: uid)
        self.gid_map = gid_map or (lambda gid: gid)

    @contextmanager
    def directory(self, path, *, uid=0, gid=0, create=False):
        path = PurePosixPath(path)
        require(path.is_absolute() and '..' not in path.parts, 'path')
        with ExitStack() as stack:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            stack.callback(os.close, fd)
            chain = []
            def safe(info):
                require(stat.S_ISDIR(info.st_mode) and info.st_uid in
                        (self.uid_map(0), self.uid_map(uid)) and not info.st_mode & 0o022,
                        'directory-metadata')
            root_info = os.fstat(fd)
            safe(root_info)
            for part in path.parts[1:]:
                try:
                    info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                except FileNotFoundError:
                    require(create, 'missing-directory')
                    os.mkdir(part, 0o755, dir_fd=fd)
                    child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                    try:
                        os.fchown(child, self.uid_map(uid), self.gid_map(gid))
                        os.fchmod(child, 0o755)
                    finally:
                        os.close(child)
                    info = os.stat(part, dir_fd=fd, follow_symlinks=False)
                safe(info)
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
                stack.callback(os.close, child)
                require(os.fstat(child) == info, 'directory-replaced')
                chain.append((fd, part, child, info))
                fd = child
            def guard():
                signature = lambda s: (s.st_dev, s.st_ino, s.st_uid, s.st_gid, s.st_mode)
                require(signature(self.root.lstat()) == signature(root_info), 'root-replaced')
                for parent, name, pinned, expected in chain:
                    require(signature(os.fstat(pinned)) == signature(expected) ==
                            signature(os.stat(name, dir_fd=parent, follow_symlinks=False)),
                            'directory-replaced')
            guard()
            yield fd
            guard()

    def preflight(self, path, *, uid=0):
        """Read existing ancestors without creating a missing one."""
        path = PurePosixPath(path)
        require(path.is_absolute() and '..' not in path.parts and str(path) != '/', 'path')
        for parent in reversed(path.parents):
            try:
                with self.directory(str(parent), uid=uid):
                    pass
            except FileNotFoundError:
                break
            except ValueError as error:
                if str(error) == 'fixture-guest:missing-directory':
                    break
                raise

    def info(self, path, *, uid=0):
        target = PurePosixPath(path)
        try:
            with self.directory(str(target.parent), uid=uid) as parent:
                return os.stat(target.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except ValueError as error:
            if str(error) == 'fixture-guest:missing-directory':
                return None
            raise

    def exists(self, path, *, uid=0):
        return self.info(path, uid=uid) is not None

    def read(self, path, *, uid=0, gid=0, mode=0o644, limit=LIMIT):
        return self.read_identity(path, uid=uid, gid=gid, mode=mode, limit=limit)[0]

    def read_identity(self, path, *, uid=0, gid=0, mode=0o644, limit=LIMIT):
        target = PurePosixPath(path)
        with self.directory(str(target.parent), uid=uid) as parent:
            data, info = guest_files.read_regular(parent, target.name,
                owner=self.uid_map(uid), mode=mode, limit=limit)
            require(info.st_gid == self.gid_map(gid), 'file-group')
            return data, [info.st_dev, info.st_ino]

    def write(self, path, data, *, uid=0, gid=0, mode=0o644):
        target = PurePosixPath(path)
        with self.directory(str(target.parent), uid=uid, gid=gid, create=True) as parent:
            guest_files.write_exclusive(parent, target.name, data,
                owner=self.uid_map(uid), group=self.gid_map(gid), mode=mode)
            os.fsync(parent)

    def replace(self, path, data, *, expected, uid=0, gid=0, mode=0o644):
        """Overwrite only a pinned, independently verified ordinary owned file.

        An interrupted write is terminal and belongs to snapshot restoration.
        No unlink, fallback creation or per-file rollback is permitted.
        """
        target = PurePosixPath(path)
        with self.directory(str(target.parent), uid=uid) as parent:
            old, before = guest_files.read_regular(parent, target.name,
                owner=self.uid_map(uid), mode=mode, limit=LIMIT)
            require(old == expected and before.st_gid == self.gid_map(gid), 'replacement-old-file')
            fd = os.open(target.name, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                require(guest_files.identity(os.fstat(fd)) == guest_files.identity(before),
                        'replacement-file-changed')
                view = memoryview(data)
                while view:
                    count = os.write(fd, view)
                    require(count > 0, 'replacement-write')
                    view = view[count:]
                os.ftruncate(fd, len(data))
                os.fsync(fd)
                require(guest_files.identity(os.fstat(fd)) == guest_files.identity(
                    os.stat(target.name, dir_fd=parent, follow_symlinks=False)),
                    'replacement-file-changed')
            finally:
                os.close(fd)
            os.fsync(parent)

    def names(self, path):
        with self.directory(path) as parent:
            names = os.listdir(parent)
            require(len(names) <= 256, 'directory-size')
            return names

    def mkdir(self, path, *, uid=0, gid=0, mode=0o700):
        target = PurePosixPath(path)
        with self.directory(str(target.parent)) as parent:
            os.mkdir(target.name, mode, dir_fd=parent)
            with self.directory(path, uid=uid) as child:
                os.fchown(child, self.uid_map(uid), self.gid_map(gid))
                os.fchmod(child, mode)

    def chown(self, path, *, uid, gid, mode):
        target = PurePosixPath(path)
        with self.directory(str(target.parent)) as parent:
            fd = os.open(target.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            try:
                info = os.fstat(fd)
                require(stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                        and info.st_uid == self.uid_map(0), 'native-file-metadata')
                os.fchown(fd, self.uid_map(uid), self.gid_map(gid))
                os.fchmod(fd, mode)
            finally:
                os.close(fd)

    def remove(self, path, *, uid=0, gid=0, mode=0o600, directory=False, expected):
        target = PurePosixPath(path)
        with self.directory(str(target.parent), uid=uid) as parent:
            info = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            require([info.st_dev, info.st_ino] == expected, 'cleanup-replaced')
            require(info.st_uid == self.uid_map(uid) and info.st_gid == self.gid_map(gid)
                    and stat.S_IMODE(info.st_mode) == mode, 'cleanup-metadata')
            require(stat.S_ISDIR(info.st_mode) if directory else
                    stat.S_ISREG(info.st_mode) and info.st_nlink == 1, 'cleanup-type')
            (os.rmdir if directory else os.unlink)(target.name, dir_fd=parent)

    def alias(self, path, destination):
        target = PurePosixPath(path)
        with self.directory(str(target.parent)) as parent:
            info = os.stat(target.name, dir_fd=parent, follow_symlinks=False)
            require(stat.S_ISLNK(info.st_mode) and info.st_uid == self.uid_map(0)
                    and info.st_gid == self.gid_map(0), 'native-tool-alias')
            value = os.readlink(target.name, dir_fd=parent)
            require(value in (destination, PurePosixPath(destination).name), 'native-tool-alias')


def command(argv):
    result = subprocess.run(argv, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, check=True, timeout=60,
                            env={**os.environ, 'LC_ALL': 'C', 'LANG': 'C'})
    require(len(result.stdout) <= 32 * 1024 * 1024 and len(result.stderr) <= LIMIT,
            'native-output-size')
    return result.stdout


class Native:
    """Exact native APIs and labels; target qualification still gates dispatch.

    Backend configuration is environment-owned and is only verified. All other
    trust fragments, vendor records and installed product rules are preserved.
    """
    def __init__(self, files, command, target, *, service_gid=None):
        self.files, self.command, self.target = files, command, target
        self.gid = service_gid if service_gid is not None else grp.getgrnam('fapolicyd').gr_gid
        self.cli = native_trust.native_tool_paths(target['os'])['cli']

    def _trusted(self, request):
        return {m['destination']: {'size': m['length'], 'sha256': m['sha256']}
                for m in request['members'].values() if m['native_action'] == 'trust'}

    def _rules(self, request):
        if self.target['os'] != 'fedora':
            return {}
        runtime = {source: path for source, (path, _) in
                   native_assets.source_destinations('@other@').items()
                   if source in native_assets.runtime_sources()}
        by_path = {m['destination']: m for m in request['members'].values()}
        if not any(m['native_action'] in ('native-open', 'native-execute')
                   for m in request['members'].values()):
            return {}
        require(set(runtime.values()) <= set(by_path), 'native-runtime-closure')
        expected = {source: by_path[path]['sha256'] for source, path in runtime.items()}
        return native_assets.native_policy_files(expected, tuple(
            request['accounts'][role]['uid'] for role in ('child', 'other')))

    def _backend(self):
        f = self.files
        self._tools()
        require(not f.exists(native_trust.BACKEND_PENDING), 'native-backend-pending')
        record_raw = f.read(native_trust.BACKEND_RECORD, mode=0o600, limit=300000)
        record = native_trust.validate_backend_record(json.loads(record_raw))
        metadata = record['metadata']
        data = f.read(native_trust.BACKEND_CONFIG, uid=metadata['uid'], gid=metadata['gid'],
                      mode=metadata['mode'], limit=65536)
        require(record['complete'] and record['os_id'] == self.target['os']
                and bytes.fromhex(record['after_hex']) == data
                and native_trust.file_backend_config(data, self.target['os']) == data,
                'native-backend')
        self.command([self.cli, '--check-config'])
        self._started()

    def _service(self, *, allow_activating=False):
        raw = self.command(['/usr/bin/systemctl', 'show', 'fapolicyd.service',
            '--property=MainPID', '--property=InvocationID', '--property=ActiveState']).decode()
        rows = [line.split('=', 1) for line in raw.splitlines()]
        require(len(rows) == 3 and all(len(row) == 2 for row in rows), 'native-service')
        fields = dict(rows)
        require(set(fields) == {'MainPID', 'InvocationID', 'ActiveState'}
                and fields['ActiveState'] in (('active', 'activating') if allow_activating else ('active',))
                and fields['MainPID'].isdigit() and (int(fields['MainPID']) > 0
                    or allow_activating and fields['ActiveState'] == 'activating' and fields['MainPID'] == '0')
                and re.fullmatch(r'[0-9a-f]{32}', fields['InvocationID']), 'native-service')
        return fields

    def _journal(self, identity, *, after=None):
        argv = ['/usr/bin/journalctl', '--boot', '--unit=fapolicyd.service',
                '--output=json', '--no-pager', '--all', '--lines=1000']
        if after is not None:
            argv += ['--after-cursor', after]
        argv += ['_PID=' + identity['MainPID'],
                 '_SYSTEMD_INVOCATION_ID=' + identity['InvocationID']]
        rows = [json.loads(line) for line in self.command(argv).decode().splitlines()]
        require(len(rows) <= 1000, 'native-journal-size')
        for row in rows:
            require(type(row) is dict and row.get('_PID') == identity['MainPID']
                    and row.get('_SYSTEMD_INVOCATION_ID') == identity['InvocationID']
                    and type(row.get('MESSAGE')) is str
                    and type(row.get('__CURSOR')) is str and 0 < len(row['__CURSOR']) <= 4096,
                    'native-journal-identity')
        return rows

    def _event(self, message, identity, *, after=None):
        deadline = time.monotonic() + 180
        while True:
            require(self._service() == identity, 'native-service-changed')
            rows = self._journal(identity, after=after)
            require(self._service() == identity, 'native-service-changed')
            if any(row['MESSAGE'] == message or row['MESSAGE'].endswith(': ' + message)
                   for row in rows):
                return rows[-1]['__CURSOR']
            require(time.monotonic() < deadline, 'native-event-timeout:' + message)
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))

    def _started(self):
        # Package startup can still be hashing its database in start-post.
        # Observe that one invocation becoming active without restarting it or
        # adopting a replacement process; _event retains strict active checks.
        deadline = time.monotonic() + 180
        identity = self._service(allow_activating=True)
        pinned = {key: identity[key] for key in ('MainPID', 'InvocationID')
                  if key != 'MainPID' or identity[key] != '0'}
        while identity['ActiveState'] == 'activating':
            require(time.monotonic() < deadline, 'native-service-timeout')
            time.sleep(min(0.2, max(0, deadline - time.monotonic())))
            require(time.monotonic() < deadline, 'native-service-timeout')
            observed = self._service(allow_activating=True)
            require(time.monotonic() < deadline, 'native-service-timeout')
            require(all(observed[key] == value for key, value in pinned.items()),
                    'native-service-changed')
            if observed['MainPID'] != '0':
                pinned['MainPID'] = observed['MainPID']
            identity = observed
        # Type=forking becomes active before the packaged daemon loads trust.
        # Its current invocation's startup event follows initialization; querying
        # LMDB sooner can race the daemon replacing that database.
        cursor = self._event('Starting to listen for events', identity)
        return identity, cursor

    def ready(self):
        self._backend()

    def _tools(self):
        """Authenticate native tools with their package's complete checksum rows.

        This is the same package API/metadata gate as baseline preparation;
        never execute a CLI merely because its pathname is canonical.
        """
        tools = native_trust.native_tool_paths(self.target['os'])
        data = {path: self.files.read(path, mode=0o755, limit=16 * LIMIT)
                for path in tools.values()}
        if self.target['os'] == 'fedora':
            self.files.alias('/usr/sbin', '/usr/bin')
        for path in tools.values():
            argv = (['rpm', '-qf', '--queryformat', '%{NAME}', path] if
                    self.target['os'] == 'fedora' else ['dpkg-query', '-S', path])
            expected = 'fapolicyd' if self.target['os'] == 'fedora' else 'fapolicyd: ' + path
            require(self.command(argv).decode().strip() == expected, 'native-tool-owner')
        if self.target['os'] == 'fedora':
            identity = self.command(['rpm', '-q', '--queryformat',
                '%{NAME} %{EPOCHNUM}:%{VERSION}-%{RELEASE}\n', 'fapolicyd']).decode()
            raw = self.command(['rpm', '-q', '--queryformat',
                '%{FILEDIGESTALGO}\n[%{FILENAMES}\t%{FILEDIGESTS}\n]', 'fapolicyd']).decode()
            require(len(raw) <= 2 * LIMIT and raw.splitlines() and raw.splitlines()[0] == '8',
                    'native-tool-checksums')
            rows = [line.split('\t') for line in raw.splitlines()[1:]]
            require(all(len(row) == 2 for row in rows), 'native-tool-checksums')
            checksums = {path: [row[1] for row in rows if row[0] == path] for path in data}
            algorithm, width = 'sha256', 64
        else:
            identity = self.command(['dpkg-query', '-W', '-f=${Package} ${Version}\n',
                                     'fapolicyd']).decode()
            raw = self.command(['dpkg-query', '--control-show', 'fapolicyd', 'md5sums']).decode()
            require(0 < len(raw) <= 2 * LIMIT, 'native-tool-checksums')
            rows = [line.split() for line in raw.splitlines()]
            require(all(len(row) == 2 for row in rows), 'native-tool-checksums')
            checksums = {path: [row[0] for row in rows if row[1] == path.lstrip('/')] for path in data}
            algorithm, width = 'md5', 32
        fields = identity.split()
        require(len(fields) == 2 and fields[0] == 'fapolicyd' and
                re.fullmatch(r'[A-Za-z0-9.+:~_-]{1,240}', fields[1]), 'native-package')
        for path, expected in checksums.items():
            require(len(expected) == 1 and re.fullmatch('[0-9a-f]{' + str(width) + '}', expected[0])
                    and hashlib.new(algorithm, data[path]).hexdigest() == expected[0], 'native-tool-bytes')

    def _foreign_trust(self, request, trusted):
        """CLI add deduplicates all fragments, so audit every source first."""
        f = self.files
        selected = {m['destination'] for m in request['members'].values()}
        paths = ['/etc/fapolicyd/trust.d/' + name for name in f.names('/etc/fapolicyd/trust.d')]
        if f.exists('/etc/fapolicyd/fapolicyd.trust'):
            paths.append('/etc/fapolicyd/fapolicyd.trust')
        for path in paths:
            info = f.info(path)
            require(info is not None and stat.S_ISREG(info.st_mode) and info.st_nlink == 1
                    and info.st_uid == f.uid_map(0)
                    and stat.S_IMODE(info.st_mode) in (0o600, 0o644), 'trust-metadata')
            # Foreign vendor fragments keep their observed readonly group;
            # only our owned fragment has an exact native service GID.
            gid = self.gid if path == TRUST else info.st_gid
            if path == TRUST:
                require(info.st_gid == f.gid_map(self.gid) and stat.S_IMODE(info.st_mode) == 0o600,
                        'owned-trust-metadata')
            data = f.read(path, gid=gid, mode=stat.S_IMODE(info.st_mode), limit=2 * LIMIT)
            if path == TRUST:
                require(request.get('repeat') is True and native_trust.trust_entries(data) == trusted,
                        'foreign-owned-trust')
                continue
            for line in data.decode('ascii').splitlines():
                if not line.strip() or line.startswith('#'):
                    continue
                parts = line.rsplit(None, 2)
                require(len(parts) == 3 and parts[1].isdigit() and HEX.fullmatch(parts[2]),
                        'foreign-trust-format')
                require(parts[0] not in selected, 'foreign-fixture-trust')

    def _stock(self, rules):
        if self.target['os'] != 'fedora':
            return
        f = self.files
        manifest = self.command(['rpm', '-q', '--queryformat',
                                 native_assets.NATIVE_RULE_MANIFEST, 'fapolicyd']).decode()
        stock = native_assets.native_stock_rules(manifest, lambda path, mode, group:
            f.read(path, gid=0 if group == 'root' else self.gid, mode=mode, limit=2 * LIMIT))
        for path, (data, mode) in stock.items():
            require(f.read(path, gid=self.gid, mode=mode, limit=2 * LIMIT) == data, 'stock-rule-changed')
        integrations = {
            '00-oh-no-parent-control-canary.rules': 'installed-fapolicyd-canary',
            '02-oh-no-parent-control-original-allow.rules': 'installed-fapolicyd-original-policy',
            '99-oh-no-parent-control-allow.rules': 'installed-fapolicyd-fallback'}
        layers = {'01-oh-no-parent-control-deny.rules', '89-oh-no-parent-control.rules'}
        names = set(f.names('/etc/fapolicyd/rules.d'))
        permitted = {PurePosixPath(p).name for p in (*stock, *rules)} | set(integrations) | layers
        require(names <= permitted and not f.exists('/etc/fapolicyd/fapolicyd.rules'),
                'foreign-native-policy')
        for name in names & (set(integrations) | layers):
            path = '/etc/fapolicyd/rules.d/' + name
            metadata = f.info(path)
            require(metadata is not None and stat.S_ISREG(metadata.st_mode)
                    and metadata.st_nlink == 1 and metadata.st_uid == f.uid_map(0)
                    and stat.S_IMODE(metadata.st_mode) == 0o644, 'product-native-metadata')
            # Broker replacements use root's current GID; the reboot-time
            # native tmpfiles rule may subsequently change it to fapolicyd.
            # Both are readonly provenance, never a group to copy/adopt.
            data = f.read(path, mode=0o644, gid=metadata.st_gid)
            if name in integrations:
                saved = f.info('/var/lib/oh-no-parent-control/' + integrations[name])
                require(saved is not None and stat.S_ISREG(saved.st_mode) and saved.st_nlink == 1
                        and saved.st_uid == f.uid_map(0) and stat.S_IMODE(saved.st_mode) == 0o600,
                        'product-native-provenance')
                require(data == f.read('/var/lib/oh-no-parent-control/' + integrations[name],
                    mode=0o600, gid=saved.st_gid), 'product-native-policy')
            else:
                require(data.startswith(b'# Generated by Oh No! Parent Control. Do not edit.\n'),
                        'product-native-layer')

    def preflight(self, request):
        self._backend()
        trusted, rules = self._trusted(request), self._rules(request)
        self._foreign_trust(request, trusted)
        self._stock(rules)
        for path, data in rules.items():
            self.files.preflight(path)
            if self.files.exists(path):
                require(request.get('repeat') is True
                        and self.files.read(path, gid=self.gid, mode=0o644) == data,
                        'native-policy-collision')
        require(not self.files.exists(native_trust.TRUST_PENDING), 'native-trust-pending')
        # Also reject fixture identities already present in another native
        # source (including package DB trust), not just trust.d text aliases.
        self.verify_database(request, installed=request.get('repeat') is True)

    def activate(self, request):
        trusted, rules = self._trusted(request), self._rules(request)
        f = self.files
        identity, cursor = self._started()
        if self.target['os'] == 'fedora':
            for member in request['members'].values():
                self.command(['/usr/sbin/restorecon', '-F', '--', member['destination']])
        previous = request.get('replaces')
        if trusted:
            if previous is None:
                f.write(TRUST, b'# Exact attempt-owned fixture trust.\n', mode=0o600)
            for path in sorted(trusted):
                self.command([self.cli, '--file', 'add' if previous is None else 'update',
                              path, '--trust-file', PurePosixPath(TRUST).name])
            # The native CLI may rewrite its owned fragment with root's GID.
            # Canonicalize only this exact CLI output before independent readback.
            f.chown(TRUST, uid=0, gid=self.gid, mode=0o600)
            require(native_trust.trust_entries(f.read(TRUST, mode=0o600,
                    gid=self.gid)) == trusted,
                    'generated-native-trust')
            if self.target['os'] == 'fedora':
                self.command(['/usr/sbin/restorecon', '-F', '--', TRUST])
            self.command([self.cli, '--update'])
            # The sole update is asynchronous. Observe its daemon's completion
            # after the pre-update cursor before opening LMDB, without resending
            # the mutation or retrying a failed database command.
            self._event('Updated', identity, after=cursor)
            self.verify_database(request)
        for path, data in rules.items():
            if previous is None:
                f.write(path, data, gid=self.gid, mode=0o644)
            else:
                f.replace(path, data, expected=self._rules(previous)[path], gid=self.gid, mode=0o644)
            self.command(['/usr/sbin/restorecon', '-F', '--', path])
        if rules:
            self.command(['/usr/sbin/fagenrules', '--load'])
        self.labels(request)

    def labels(self, request, *, verify=False):
        if self.target['os'] != 'fedora':
            return
        paths = [m['destination'] for m in request['members'].values()]
        paths += list(self._rules(request))
        if self._trusted(request):
            paths.append(TRUST)
        for path in sorted(paths):
            self.command(['/usr/sbin/matchpathcon', '-V', path] if verify else
                         ['/usr/sbin/restorecon', '-F', '--', path])

    def verify_database(self, request, *, installed=True):
        trusted = self._trusted(request) if installed else {}
        selected = {m['destination'] for m in request['members'].values()}
        rows = {path: [] for path in selected}
        for line in self.command([self.cli, '--dump-db']).decode().splitlines():
            fields = native_trust.database_row(line)
            if fields is not None and fields[1] in rows:
                rows[fields[1]].append(fields)
        for path in sorted(selected):
            expected = ([['filedb', path, str(trusted[path]['size']), trusted[path]['sha256']]]
                        if path in trusted else [])
            key = next(key for key, member in request['members'].items()
                       if member['destination'] == path)
            require(rows[path] == expected, 'native-database:' + json.dumps({
                'member': key, 'expected': [[row[0], row[2], row[3]] for row in expected],
                'observed': [[row[0], row[2], row[3]] for row in rows[path]]}, sort_keys=True))

    def verify(self, request):
        self._backend()
        trusted, rules = self._trusted(request), self._rules(request)
        self._foreign_trust({**request, 'repeat': True}, trusted)
        require(bool(trusted) == self.files.exists(TRUST), 'native-trust-presence')
        if trusted:
            require(native_trust.trust_entries(self.files.read(TRUST, mode=0o600,
                                                             gid=self.gid)) == trusted, 'native-trust')
        for path, data in rules.items():
            require(self.files.read(path, gid=self.gid, mode=0o644) == data, 'native-policy')
        self._stock(rules)
        self.verify_database(request)
        if rules:
            output = self.command(['/usr/sbin/fagenrules', '--check']).decode().splitlines()
            require('/usr/sbin/fagenrules: No change' in output, 'native-rules-not-active')
        self.labels(request, verify=True)


def accounts():
    names = {'child': 'onpc-child-riley', 'other': 'onpc-child-jordan', 'parent': 'onpc-parent-jamie'}
    result = {'system': {'uid': 0, 'gid': 0, 'home': '/root'}}
    # Fixed roles are the baseline's accepted public accounts, never host IDs.
    for role, name in names.items():
        account = pwd.getpwnam(name)
        result[role] = {'uid': account.pw_uid, 'gid': account.pw_gid, 'home': account.pw_dir}
    group = 'wheel' if Path('/etc/fedora-release').exists() else 'sudo'
    admin = grp.getgrnam(group).gr_gid
    require(admin in os.getgrouplist(names['parent'], result['parent']['gid']) and
            all(admin not in os.getgrouplist(names[role], result[role]['gid'])
                for role in ('child', 'other')), 'account-roles')
    return result


def target():
    # /etc/os-release is a vendor compatibility link; use the canonical source.
    values = {}
    for line in Path('/usr/lib/os-release').read_text().splitlines():
        if '=' in line:
            key, value = line.split('=', 1)
            values[key] = value.strip('"')
    result = {'os': values.get('ID'), 'release': values.get('VERSION_ID'),
              'architecture': os.uname().machine}
    require((result['os'], result['release'], result['architecture']) in
            (('ubuntu', '26.04', 'x86_64'), ('fedora', '44', 'x86_64')), 'target')
    return result


def runtime_witness(request):
    """Use the established identity-recorded fixture launch/termination helpers."""
    try:
        from fixture_process import launch_native, terminate
    except ImportError:
        from tests.fixtures.build_test_applications import launch_native, terminate
    members = request['members']
    preferred = ['/opt/onpc-test-fixtures-trusted-hard/native-fixture',
                 native_assets.executable_path('A')]
    executables = {m['destination']: m for m in members.values() if m['mode'] == 0o755}
    if not executables:
        require(not members or all(m['mode'] == 0o644 for m in members.values()), 'witness-closure')
        return
    path = next((p for p in preferred if p in executables), sorted(executables)[0])
    process = launch_native(Path(path), request['accounts']['child']['uid'])
    # launch_native owns the Popen receipt, bounded marker read and one-shot
    # failure cleanup. Never signal a process inferred from a path or PID scan.
    terminate(process)
    require(process.returncode == 0, 'witness-exit')


class Guest:
    def __init__(self, files, native, accounts, witness, *, target, guard=None):
        self.files, self.native = files, native
        self.accounts, self.witness, self.target = accounts, witness, target
        self.guard = guard

    def _validate(self, request):
        require(type(request) is dict and set(request) - {'replaces'} ==
                {'binding', 'target', 'members', 'absences', 'accounts', 'staging', 'repeat',
                 'stage_identity', 'stage_files'}, 'request')
        binding = request['binding']
        require(type(binding) is dict and set(binding) == {'vm_uuid', 'run', 'boot_sha256',
                'attempt_id', 'manifest_sha256', 'content_identity', 'subsets', 'generation'}, 'binding')
        require(type(binding['generation']) is int and binding['generation'] >= 0, 'generation')
        for field in ('boot_sha256', 'manifest_sha256', 'content_identity'):
            require(type(binding[field]) is str and HEX.fullmatch(binding[field]), 'binding-digest')
        require(type(binding['attempt_id']) is str and
                re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,127}', binding['attempt_id']), 'attempt')
        canonical = (json.dumps(binding, sort_keys=True, separators=(',', ':'),
                                ensure_ascii=True, allow_nan=False) + '\n').encode('ascii')
        require(request['staging'] == '/run/onpc-fixture-' + sha(canonical)
                and type(request['repeat']) is bool and request['target'] == self.target, 'staging')
        require(request['accounts'] == self.accounts, 'accounts')
        def identity(value):
            return type(value) is list and len(value) == 2 and all(
                type(number) is int and number > 0 for number in value)
        require(request['stage_identity'] is None or identity(request['stage_identity']),
                'stage-identity')
        require(request['stage_files'] is None or type(request['stage_files']) is dict and
                all(identity(value) for value in request['stage_files'].values()), 'stage-identities')
        declared = fixture_manifest.select(binding['subsets'])
        require(type(request['members']) is dict and set(request['members']) == set(declared),
                'members')
        for key, member in request['members'].items():
            declaration = declared[key]
            original, mode, role = (declaration[name] for name in ('destination', 'mode', 'owner'))
            path = original
            for name, account in self.accounts.items():
                path = path.replace('@' + name + '@', account['home'])
            require(member['destination'] == path and member['owner'] == role and member['mode'] == mode
                    and member['uid'] == self.accounts[role]['uid']
                    and member['gid'] == self.accounts[role]['gid']
                    and type(member['length']) is int and 0 < member['length'] <= LIMIT
                    and type(member['sha256']) is str and HEX.fullmatch(member['sha256']), 'member')
            require(set(member) == {'destination', 'mode', 'owner', 'subsets', 'native_action',
                                    'length', 'sha256', 'uid', 'gid'}
                    and member['subsets'] == declaration['subsets']
                    and member['native_action'] == declaration['native_action'], 'native-action')
        absences = [item['destination'] for item in fixture_manifest.ABSENCES
                    if set(binding['subsets']).intersection(item['subsets'])]
        require(request['absences'] == absences, 'absences')
        if 'replaces' in request:
            previous = request['replaces']
            require(type(previous) is dict and 'replaces' not in previous
                    and previous['repeat'] is True and request['repeat'] is False, 'replacement')
            self._validate(previous)
            require(all(binding[key] == previous['binding'][key] for key in
                ('vm_uuid', 'run', 'boot_sha256', 'attempt_id', 'subsets')) and
                binding['generation'] == previous['binding']['generation'] + 1 and
                set(request['members']) == set(previous['members']),
                'replacement-binding')

    def _stage(self, request, *, files=False):
        info = self.files.info(request['staging'])
        require(info is not None and stat.S_ISDIR(info.st_mode)
                and info.st_uid == self.files.uid_map(0) and info.st_gid == self.files.gid_map(0)
                and stat.S_IMODE(info.st_mode) == 0o700
                and [info.st_dev, info.st_ino] == request['stage_identity'], 'staging-replaced')
        if files:
            require(type(request['stage_files']) is dict and
                    set(request['stage_files']) == set(request['members']), 'stage-identities')
            for key in request['members']:
                _, identity = self.files.read_identity(request['staging'] + '/' + key, mode=0o600)
                require(identity == request['stage_files'][key], 'staged-file-replaced')

    def call(self, action, request, payloads=None):
        if self.guard is not None:
            self.guard(request['binding'])
        if action == 'inspect':
            self.native.ready()
            return {'accounts': self.accounts, 'target': self.target}
        self._validate(request)
        f, members, stage = self.files, request['members'], request['staging']
        if action in ('stage', 'place', 'activate', 'clean'):
            self._stage(request, files=action in ('place', 'activate', 'clean'))
        if action == 'preflight':
            previous = request.get('replaces')
            for m in members.values():
                path, uid = m['destination'], m['uid']
                f.preflight(path, uid=uid)
                if f.exists(path, uid=uid):
                    require(request['repeat'] or previous is not None, 'unknown-destination')
                    expected = next(old for old in previous['members'].values()
                        if old['destination'] == path) if previous is not None else m
                    self._bytes(expected, path)
                else:
                    require(not request['repeat'] and previous is None, 'missing-destination')
            for path in request['absences']:
                f.preflight(path)
                require(not f.exists(path), 'required-absence')
            self.native.preflight(previous if previous is not None else request)
            require(not f.exists(stage), 'staging-collision')
        elif action == 'reserve':
            require(not request['repeat'], 'repeat-write')
            f.mkdir(stage)
            info = f.info(stage)
            return {'ok': True, 'identity': [info.st_dev, info.st_ino]}
        elif action == 'stage':
            require(not request['repeat'] and type(payloads) is dict and set(payloads) == set(members),
                    'payload-membership')
            for key, m in members.items():
                data = payloads[key]
                require(type(data) is bytes and len(data) == m['length'] and sha(data) == m['sha256'],
                        'payload-bytes')
            for key, data in payloads.items():
                f.write(stage + '/' + key, data, mode=0o600)
            identities = {}
            for key, data in payloads.items():
                observed, identity = f.read_identity(stage + '/' + key, mode=0o600)
                require(observed == data, 'staging-write')
                identities[key] = identity
            return {'ok': True, 'identities': identities}
        elif action == 'place':
            require(not request['repeat'], 'repeat-write')
            # Recheck the complete destination/native set after transfer and
            # before the first placement, then create only new declared files.
            previous = request.get('replaces')
            old_bytes = {}
            for key, m in members.items():
                f.preflight(m['destination'], uid=m['uid'])
                if previous is None:
                    require(not f.exists(m['destination'], uid=m['uid']), 'placement-collision')
                else:
                    old_bytes[key] = self._bytes(previous['members'][key], m['destination'])
            for path in request['absences']:
                require(not f.exists(path), 'required-absence')
            self.native.preflight(previous if previous is not None else request)
            staged = {}
            for key, m in members.items():
                data, identity = f.read_identity(stage + '/' + key, mode=0o600)
                require(identity == request['stage_files'][key] and
                        len(data) == m['length'] and sha(data) == m['sha256'], 'stage-modified')
                staged[key] = data
            for key, m in members.items():
                if previous is None:
                    f.write(m['destination'], staged[key], uid=m['uid'], gid=m['gid'], mode=m['mode'])
                else:
                    f.replace(m['destination'], staged[key], expected=old_bytes[key],
                              uid=m['uid'], gid=m['gid'], mode=m['mode'])
        elif action == 'activate':
            require(not request['repeat'], 'repeat-write')
            for member in members.values():
                self._bytes(member, member['destination'])
            self.native.preflight(request.get('replaces', request))
            self.native.activate(request)
        elif action == 'readback':
            observed = {}
            for key, m in members.items():
                data = self._bytes(m, m['destination'])
                observed[key] = {**{name: m[name] for name in ('mode', 'uid', 'gid')},
                                 'sha256': sha(data), 'length': len(data)}
            for path in request['absences']:
                require(not f.exists(path), 'required-absence')
            self.native.verify(request)
            return {'files': observed, 'native': True, 'labels': True}
        elif action == 'witness':
            self.witness(request)
            return {'ready': True}
        elif action == 'clean':
            require(set(f.names(stage)) == set(members), 'staging-inventory')
            for key, m in members.items():
                data = f.read(stage + '/' + key, mode=0o600)
                require(len(data) == m['length'] and sha(data) == m['sha256'], 'cleanup-stage-modified')
            for key in members:
                f.remove(stage + '/' + key, expected=request['stage_files'][key])
            f.remove(stage, directory=True, mode=0o700, expected=request['stage_identity'])
        else:
            require(False, 'action')
        return {'ok': True}

    def _bytes(self, member, path):
        data = self.files.read(path, uid=member['uid'], gid=member['gid'], mode=member['mode'])
        require(len(data) == member['length'] and sha(data) == member['sha256'], 'member-readback')
        return data


def default_guest():
    require(os.geteuid() == 0, 'root-required')
    f, t = Files(), target()
    def guard(binding):
        marker = json.loads(f.read('/etc/onpc-system-test.json', mode=0o600))
        require(marker['run'] == binding['run'] and marker['domain_uuid'] == binding['vm_uuid']
                and Path('/sys/class/dmi/id/product_uuid').read_text().strip().lower() == binding['vm_uuid']
                and sha(Path('/proc/sys/kernel/random/boot_id').read_bytes()) == binding['boot_sha256'],
                'stale-guest')
    return Guest(f, Native(f, command, t), accounts(), runtime_witness, target=t, guard=guard)
