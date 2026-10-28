"""One attempt-owned missing optional scenery file in the installed kiosk."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import pwd
import secrets
import stat
import sys


ARTWORK = Path('/usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/'
               'kiosk-background-scenery-clear.png')
MAX_ARTWORK = 32 * 1024 * 1024


def require(value, code):
    if not value:
        raise RuntimeError('optional-artwork:' + code)


def metadata(info):
    # Rename changes ctime; all content and access metadata must survive.
    return [info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode,
            info.st_nlink, info.st_size, info.st_mtime_ns]


def guest_operation(action, token, receipt):
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from system_kiosk_confinement import ACCOUNT, census, wait_kiosk_inactive
    marker = guest.guard()
    guest.enable_diagnostics()
    require(action in ('install', 'observe', 'restore'), 'action')
    require(len(token) == 32 and all(c in '0123456789abcdef' for c in token), 'token')
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin', 'account')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    hidden = '.onpc-u08-' + token + '-' + ARTWORK.name
    directory = os.open('/', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        # Pin every ancestor, including on merged-/usr installations. /usr/lib
        # is the package-owned literal path; no symlink component is adopted.
        for part in ARTWORK.parent.parts[1:]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=directory)
            os.close(directory)
            directory = child
            info = os.fstat(directory)
            require(info.st_uid == 0 and not info.st_mode & 0o022, 'unsafe-parent')
        parent = os.fstat(directory)
        parent_identity = [parent.st_dev, parent.st_ino, parent.st_uid,
                           parent.st_gid, parent.st_mode]

        def absent(name):
            try:
                os.stat(name, dir_fd=directory, follow_symlinks=False)
            except FileNotFoundError:
                return True
            return False

        def identity(name):
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                 dir_fd=directory)
            try:
                before = os.fstat(descriptor)
                require(stat.S_ISREG(before.st_mode) and before.st_uid == 0
                        and not before.st_mode & 0o022 and before.st_nlink == 1
                        and before.st_dev == parent.st_dev
                        and 0 < before.st_size <= MAX_ARTWORK, 'unsafe-artwork')
                digest = hashlib.sha256()
                remaining = before.st_size
                while remaining:
                    data = os.read(descriptor, min(remaining, 65536))
                    require(bool(data), 'short-artwork')
                    digest.update(data)
                    remaining -= len(data)
                require(not os.read(descriptor, 1)
                        and metadata(os.fstat(descriptor)) == metadata(before)
                        and metadata(os.stat(name, dir_fd=directory,
                                             follow_symlinks=False)) == metadata(before),
                        'artwork-changed')
                return {'metadata': metadata(before), 'sha256': digest.hexdigest()}
            finally:
                os.close(descriptor)

        def rename(source, destination):
            # Linux's no-replace primitive is atomic, unlike exists()+rename().
            libc = ctypes.CDLL(None, use_errno=True)
            renameat2 = libc.renameat2
            renameat2.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                                  ctypes.c_char_p, ctypes.c_uint)
            renameat2.restype = ctypes.c_int
            if renameat2(directory, os.fsencode(source), directory,
                         os.fsencode(destination), 1) != 0:  # RENAME_NOREPLACE
                error = ctypes.get_errno()
                raise OSError(error, os.strerror(error))
            os.fsync(directory)

        def attempt():
            guest.guard()
            require(pwd.getpwnam(ACCOUNT).pw_uid == account.pw_uid
                    and receipt['run'] == marker['run'] and receipt['boot'] == boot
                    and receipt['uid'] == account.pw_uid
                    and receipt['parent'] == parent_identity, 'attempt-changed')

        if action == 'install':
            require(receipt is None, 'already-installed')
            wait_kiosk_inactive(account)
            original = identity(ARTWORK.name)
            require(absent(hidden), 'foreign-hidden-artwork')
            guest.guard()
            rename(ARTWORK.name, hidden)
            require(absent(ARTWORK.name) and identity(hidden) == original, 'install-changed')
            return {'run': marker['run'], 'boot': boot, 'uid': account.pw_uid,
                    'parent': parent_identity, 'original': original}

        attempt()
        if action == 'restore':
            wait_kiosk_inactive(account)
            attempt()
            require(absent(ARTWORK.name) and identity(hidden) == receipt['original'],
                    'hidden-artwork-changed')
            rename(hidden, ARTWORK.name)
            require(absent(hidden) and identity(ARTWORK.name) == receipt['original'],
                    'restored-artwork-changed')
            return {'restored': True, 'same_artwork': True}

        # The caller must first independently observe the usable public form.
        require(absent(ARTWORK.name) and identity(hidden) == receipt['original'],
                'hidden-artwork-changed')
        session = census()
        attempt()
        require(absent(ARTWORK.name) and identity(hidden) == receipt['original'],
                'observation-artwork-changed')
        return {'optional_artwork_missing': True, 'original_artwork_preserved': True,
                'session': session}
    finally:
        os.close(directory)


class OptionalArtworkFault:
    def __init__(self, journey, lease):
        self.journey, self.lease = journey, lease
        self.token, self.receipt, self.restored = secrets.token_hex(16), None, False
        self.source = Path(__file__).read_bytes()

    def call(self, action):
        import watch_activity
        self.lease.guard()
        with watch_activity.operation({
                'install': 'Making one optional kiosk scenery file unavailable',
                'observe': 'Checking the active kiosk with optional scenery unavailable',
                'restore': 'Restoring the exact optional kiosk scenery file'}[action]):
            raw = self.journey.transport.call([
                'env', 'ONPC_EXPECTED_RUN=' + self.lease.state['run'],
                '/usr/bin/python3', '-I', '-', action, self.token, json.dumps(self.receipt)],
                input=self.source, timeout=120)
        self.lease.guard()
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'response-bound')
        value = json.loads(raw)
        require(type(value) is dict, 'response-type')
        return value

    def install(self):
        require(self.receipt is None and not self.restored, 'already-installed')
        self.receipt = self.call('install')
        return {'installed': True, 'optional_artwork_missing': True}

    def restore(self):
        if self.receipt is not None and not self.restored:
            value = self.call('restore')
            require(value.get('restored') is True, 'restoration')
            self.restored = True
            return value


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] in ('install', 'observe', 'restore'),
            'arguments')
    print(json.dumps(guest_operation(sys.argv[1], sys.argv[2], json.loads(sys.argv[3])),
                     sort_keys=True))
