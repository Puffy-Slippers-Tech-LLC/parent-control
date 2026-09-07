"""Check fixed development-helper authorization without requesting authentication."""
import os
from pathlib import Path
import stat
import subprocess


PROGRAMS = {'/usr/local/libexec/onpc-' + name: 'com.puffyslippers.onpc.development.' + name
            for name in ('test-runner', 'diagnostics', 'test-artifacts', 'export-screenshot')}


def check(program):
    if program not in PROGRAMS or os.geteuid() == 0:
        raise ValueError('expected an installed development helper and unprivileged caller')
    path = Path(program)
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
        raise ValueError('development helper installation is unsafe; run ./setup.sh --test-tools-only')
    # This process is alive throughout the check; no host-wide process discovery.
    fields = Path('/proc/self/stat').read_text().rsplit(')', 1)[1].split()
    subject = f'{os.getpid()},{int(fields[19])},{os.getuid()}'
    try:
        # Ordinary users cannot pass arbitrary action details to CheckAuthorization.
        # Dedicated exec.path actions allow this detail-free, noninteractive check.
        result = subprocess.run(['/usr/bin/pkcheck', '--action-id', PROGRAMS[program],
                                 '--process', subject],
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=15, check=False)
    except subprocess.TimeoutExpired as error:
        raise ValueError('noninteractive authorization check timed out') from error
    if result.returncode:
        raise ValueError(f'noninteractive authorization unavailable (status={result.returncode}); refresh ./setup.sh --test-tools-only from an active local administrator session')


def launch(program, argv):
    check(program)
    command = ['/usr/bin/pkexec', program, *argv]
    os.execve(command[0], command, {'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
