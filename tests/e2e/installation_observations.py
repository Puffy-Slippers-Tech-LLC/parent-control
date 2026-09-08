"""Fixed read-only installation probes; customer input owns package changes.

These establish package state, not authenticated input, notice visibility,
payload integrity or readiness. The journey must compare the returned package
digest to VerifiedInputs and separately retain those remaining assertions.
"""

COMMON = '''import hashlib,json,pathlib,stat,subprocess
package = 'oh-no-parent-control'
def call(*args):
    result = subprocess.run(args, capture_output=True, text=True, check=True, timeout=15)
    assert len(result.stdout) <= 4194304
    return result.stdout
def regular(path):
    p = pathlib.Path(path)
    s = p.lstat()
    assert p.resolve() == p and stat.S_ISREG(s.st_mode)
    assert s.st_uid == s.st_gid == 0 and s.st_nlink == 1
    assert not stat.S_IMODE(s.st_mode) & 0o022
    return p
def reboot_packages():
    p = pathlib.Path('/run/reboot-required.pkgs')
    # lexists semantics: dangling symlinks must fail, not look absent.
    try:
        p.lstat()
    except FileNotFoundError:
        return []
    raw = regular(str(p)).read_text()
    assert len(raw) <= 65536
    return raw.splitlines()
'''

# Query the complete package database successfully instead of interpreting a
# failed single-package query (which could be a database error) as absence.
# Residual package/config state also disqualifies the clean baseline.
ABSENT = COMMON + '''rows = call('/usr/bin/dpkg-query', '-W', '-f=${Package}\\t${db:Status-Status}\\n').splitlines()
assert rows
for row in rows:
    fields = row.split('\\t')
    assert len(fields) == 2 and all(fields)
    assert fields[0] != package
for name in ('/usr/lib/oh-no-parent-control', '/etc/oh-no-parent-control',
             '/var/lib/oh-no-parent-control', '/usr/bin/oh-no-parent-control',
             '/usr/bin/oh-no-parent-control-parent',
             '/usr/libexec/oh-no-parent-control-broker'):
    try:
        pathlib.Path(name).lstat()
    except FileNotFoundError:
        continue
    raise AssertionError('product-payload-present')
assert package not in reboot_packages()
print('package-absent')
'''

INSTALLED = COMMON + '''asset = regular('/var/lib/onpc-e2e-assets/package.deb')
expected = [call('/usr/bin/dpkg-deb', '-f', str(asset), field).strip()
            for field in ('Package', 'Version', 'Architecture')]
assert expected[0] == package and all(expected)
assert all('\\n' not in value and '\\t' not in value for value in expected)
actual = call('/usr/bin/dpkg-query', '-W',
              '-f=${Package}\\t${Version}\\t${Architecture}\\t${Status}\\n', package)
assert actual == '\\t'.join([*expected, 'install ok installed']) + '\\n'
regular('/run/reboot-required')
assert package in reboot_packages()
h = hashlib.sha256()
with asset.open('rb') as stream:
    for block in iter(lambda: stream.read(1048576), b''): h.update(block)
print(json.dumps({'package_sha256': h.hexdigest(), 'installed_identity_verified': True,
                  'product_reboot_required': True}, sort_keys=True))
'''

# Follow the stock getty's foreground group, never a host-wide process search.
# This is a separate boundary from login(1): a visible prompt alone does not
# prove who will consume a password. No command or process identity is supplied
# by the worker. sudo may be the distribution's alternatives-managed binary.
SUDO_PASSWORD = '''import os,pathlib,pwd,stat,subprocess,termios
uid = pwd.getpwnam('onpc-parent-jamie').pw_uid
assert uid > 0
leader = int(subprocess.run(['systemctl','show','serial-getty@ttyS0.service',
                            '--property=MainPID','--value'], capture_output=True,
                           text=True, check=True, timeout=10).stdout.strip())
assert leader > 1
device = os.makedev(4,64)
def process(pid):
    p = pathlib.Path('/proc') / str(pid)
    fields = (p/'stat').read_text().rpartition(') ')[2].split()
    assert len(fields) >= 20
    return p, fields
root, root_fields = process(leader)
assert int(root_fields[3]) == leader and int(root_fields[4]) == device
pid = int(root_fields[5])
assert pid > 1 and pid != leader
proc, fields = process(pid)
assert [int(v) for v in fields[2:6]] == [pid,leader,device,pid]
parent, parent_fields = process(int(fields[1]))
assert int(parent_fields[3]) == leader and int(parent_fields[4]) == device
assert int(parent_fields[5]) == pid
expected_args = [b'/usr/bin/sudo',b'-k',b'-p',b'ONPC-INSTALL-PASSWORD: ',b'--',
                 b'/usr/bin/apt-get',b'install',b'-y',
                 b'/var/lib/onpc-e2e-assets/package.deb',b'']
def snapshot():
    assert (proc/'cmdline').read_bytes().split(b'\\0') == expected_args
    executable = pathlib.Path('/usr/bin/sudo').resolve(strict=True)
    info = executable.stat()
    assert stat.S_ISREG(info.st_mode) and info.st_uid == info.st_gid == 0
    assert not stat.S_IMODE(info.st_mode) & 0o022
    assert (proc/'exe').resolve(strict=True) == executable
    assert (parent/'exe').resolve(strict=True) == pathlib.Path('/usr/bin/bash')
    def ids(p):
        rows = dict(line.split(':',1) for line in (p/'status').read_text().splitlines())
        return [int(v) for v in rows['Uid'].split()]
    assert ids(proc) == [uid,0,0,0] and ids(parent) == [uid]*4
    assert (proc/'fd/0').stat().st_rdev == device
    current = [process(value)[1] for value in (leader,pid,int(fields[1]))]
    for before, after in zip((root_fields,fields,parent_fields), current):
        assert before[1:6] == after[1:6] and before[19] == after[19]
snapshot()
fd = os.open('/dev/ttyS0', os.O_RDONLY | os.O_NONBLOCK | os.O_NOCTTY | os.O_NOFOLLOW)
try:
    info = os.fstat(fd)
    assert stat.S_ISCHR(info.st_mode) and info.st_rdev == device
    assert not termios.tcgetattr(fd)[3] & (termios.ECHO | termios.ECHONL)
    snapshot()
finally:
    os.close(fd)
print('install-password-safe')
'''
