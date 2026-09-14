"""Discard passing render images only after every fixture has shut down."""

import os
from pathlib import Path
import re
import shutil
import stat
import tempfile


class RenderArtifacts:
    def __init__(self, prefix, *, parent='/var/tmp', shader_cache=False):
        from tools.test_retention import allocate
        self.path = Path(allocate(tempfile.mkdtemp, prefix=prefix, dir=parent))
        self.shader_cache = shader_cache
        info = self.path.stat()
        self.identity = info.st_dev, info.st_ino

    def finish(self, passed):
        if not passed:
            print(f'UI artifacts retained: {self.path}', flush=True)
            return
        # Pin the allocated directory and refuse replacements. Never scan other
        # attempts, follow symlinks, or delete logs and input event streams.
        fd = os.open(self.path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(fd)
            if (info.st_dev, info.st_ino) != self.identity:
                raise ValueError('UI artifact directory was replaced')
            if self.shader_cache:
                self._clear_shaders(fd)
            removed = 0
            for name in os.listdir(fd):
                if not re.fullmatch(r'[A-Za-z0-9_.-]+\.png|layout(?:-\d+)?\.json', name):
                    continue
                info = os.stat(name, dir_fd=fd, follow_symlinks=False)
                if not (stat.S_ISREG(info.st_mode) and info.st_uid == os.geteuid()
                        and info.st_nlink == 1):
                    continue
                os.unlink(name, dir_fd=fd)
                removed += 1
            print(f'UI passing render cleanup: files={removed}; directory={self.path}', flush=True)
        finally:
            os.close(fd)
        # Event streams and any unexpected files keep their original directory.
        if not any(self.path.iterdir()):
            self.path.rmdir()

    @staticmethod
    def _clear_shaders(root_fd):
        try:
            cache = os.open('cache', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                            dir_fd=root_fd)
        except FileNotFoundError:
            return
        try:
            # These contain regenerable driver data, never application logs.
            # rmtree's fd-based implementation refuses directory symlinks.
            for name in ('mesa_shader_cache', 'mesa_shader_cache_db',
                         'mesa_shader_cache_sf', 'nvidia'):
                try:
                    info = os.stat(name, dir_fd=cache, follow_symlinks=False)
                except FileNotFoundError:
                    continue
                if stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid():
                    shutil.rmtree(name, dir_fd=cache)
        finally:
            os.close(cache)
