"""Persistent console settings: baseline writes, test attempts only verify."""
import re
import stat

LOGIN_TIMEOUT = 600
GETTY_TARGET = '/usr/lib/systemd/system/serial-getty@.service'
GETTY_LINK = '/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service'


def require(value, code):
    if not value:
        raise ValueError('baseline:console-' + code + '; run tools/prepare-vm')


def login_window(g, *, prepare=False):
    path = '/etc/login.defs'
    require(g.realpath(path) == path, 'login-path')
    before = g.lstatns(path)
    fields = ('st_dev', 'st_ino', 'st_mode', 'st_uid', 'st_gid', 'st_nlink')
    identity = lambda info: tuple(info[key] for key in fields)
    require(stat.S_ISREG(before['st_mode']) and before['st_uid'] == before['st_gid'] == 0
            and before['st_nlink'] == 1 and not before['st_mode'] & 0o7022, 'login-file')
    require(0 < g.filesize(path) <= 65536, 'login-size')
    original = g.read_file(path)
    require(len(original) <= 65536 and b'\x00' not in original, 'login-content')
    lines = original.splitlines(keepends=True)
    selected = [i for i, line in enumerate(lines)
                if line.split() and line.split()[0] == b'LOGIN_TIMEOUT']
    require(len(selected) <= 1, 'login-setting')
    if selected:
        index = selected[0]
        match = re.fullmatch(rb'([ \t]*LOGIN_TIMEOUT[ \t]+)(60|600)([ \t]*(?:#[^\r\n]*)?)(\r?\n)?', lines[index])
        require(match is not None, 'login-setting')
        lines[index] = match[1] + b'600' + match[3] + (match[4] or b'')
    else:
        # Some supported guests leave the shadow default implicit. Only
        # baseline preparation may add the declared console prerequisite.
        require(prepare, 'login-stale')
        if not original.endswith(b'\n'):
            lines.append(b'\n')
        lines.append(b'LOGIN_TIMEOUT\t600\n')
    desired = b''.join(lines)
    require(len(desired) <= 65536, 'login-size')
    require(identity(g.lstatns(path)) == identity(before), 'login-file-changed')
    if desired != original:
        require(prepare, 'login-stale')
        g.write(path, desired)
    require(identity(g.lstatns(path)) == identity(before) and g.read_file(path) == desired, 'login-readback')
    return {'login_timeout_seconds': LOGIN_TIMEOUT, 'configuration': 'login.defs',
            'readback_verified': True}


def getty(g, *, prepare=False):
    require(g.is_file(GETTY_TARGET) and g.realpath(GETTY_TARGET) == GETTY_TARGET, 'getty-prerequisite')
    directory = GETTY_LINK.rsplit('/', 1)[0]
    require(g.is_dir(directory) and g.realpath(directory) == directory, 'getty-directory')
    if not g.is_symlink(GETTY_LINK):
        require(prepare and not g.exists(GETTY_LINK), 'getty-missing-or-conflict')
        g.ln_s(GETTY_TARGET, GETTY_LINK)
    require(g.realpath(GETTY_LINK) == GETTY_TARGET, 'getty-conflict')


def reconcile(g):
    login_window(g, prepare=True)
    getty(g, prepare=True)


def verify(g):
    login_window(g)
    getty(g)
