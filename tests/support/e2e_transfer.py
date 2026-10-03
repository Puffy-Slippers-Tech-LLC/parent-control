"""Private real-file guestfs double for FIX04 transfer/cleanup checks."""
import hashlib
from pathlib import Path


class GuestFiles:
    def __init__(self, root):
        self.root = root
        self.closed = False
        self.uploads = 0
        self.corrupt = False

    def path(self, name): return self.root / name.lstrip('/')
    def set_backend(self, *_): pass
    def set_network(self, *_): pass
    def add_drive_opts(self, *_, **__): pass
    def launch(self): pass
    def inspect_os(self): return ['/dev/test']
    def inspect_get_mountpoints(self, *_): return {'/': '/dev/test'}
    def mount(self, *_): pass
    def sync(self): pass
    def close(self): self.closed = True
    def realpath(self, name): return name
    def exists(self, name): return self.path(name).exists()
    def is_symlink(self, name): return self.path(name).is_symlink()
    def mkdir(self, name): self.path(name).mkdir()
    def chown(self, *_): pass
    def chmod(self, mode, name): self.path(name).chmod(mode)

    def lstatns(self, name):
        info = self.path(name).lstat()
        return {key: getattr(info, key) for key in (
            'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink', 'st_size')}

    def upload(self, source, name):
        self.uploads += 1
        self.path(name).write_bytes(Path(source).read_bytes() + (b'corrupt' if self.corrupt else b''))

    def checksum(self, algorithm, name):
        assert algorithm == 'sha256'
        return hashlib.sha256(self.path(name).read_bytes()).hexdigest()

    def find(self, name):
        prefix = '' if name.endswith('/') else '/'
        return [prefix + p.relative_to(self.path(name)).as_posix()
                for p in self.path(name).rglob('*')]
