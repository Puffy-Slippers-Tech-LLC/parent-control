"""Resolve the invoking repository before privileged checkout code is loaded.

The installer embeds this standard-library-only code in the root-owned helpers.
Polkit authorizes the caller; repository markers do not confer authorization.
"""
import os
from pathlib import Path
import grp
import pwd
import stat


def checkout_root():
    root = Path.cwd()
    uid = int(os.environ.get('PKEXEC_UID', str(os.getuid())))
    try:
        allowed_users = {pwd.getpwuid(uid).pw_name, 'root'}
    except KeyError as error:
        raise ValueError('test-runner:unknown-repository-caller') from error
    groups = {}

    def safe(info):
        if info.st_uid not in (0, uid) or info.st_mode & 0o002:
            return False
        if info.st_mode & 0o020:
            if info.st_gid not in groups:
                # Ubuntu's private user groups commonly own mode-775 checkouts.
                # A writable group must not admit any unrelated account, through
                # either primary or supplementary membership.
                members = set(grp.getgrgid(info.st_gid).gr_mem)
                members.update(user.pw_name for user in pwd.getpwall()
                               if user.pw_gid == info.st_gid)
                groups[info.st_gid] = members <= allowed_users
            return groups[info.st_gid]
        return True
    markers = ('setup.sh', 'Makefile', 'tools/onpc-test-runner',
               'tools/install_test_runner.py', 'config/com.puffyslippers.onpc.development.policy')
    try:
        for relative in ('', *markers):
            path = root / relative
            for part in (path, *path.parents):
                if part.is_symlink():
                    raise ValueError('test-runner:unsafe-repository-path')
                info = part.stat()
                if not safe(info):
                    raise ValueError('test-runner:unsafe-repository-path')
                if part == root:
                    break
            info = path.stat()
            if not (stat.S_ISREG(info.st_mode) if relative else stat.S_ISDIR(info.st_mode)):
                raise ValueError('test-runner:unsafe-repository-path')
    except (OSError, KeyError) as error:
        raise ValueError('test-runner:invoke-from-repository-root-with-keep-cwd') from error
    return root
