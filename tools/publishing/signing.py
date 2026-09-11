#!/usr/bin/python3 -IB
"""Git/debsign adapter for publish.py; keep secrets off argv and out of builds."""
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
VARIABLE = 'APT_PACKAGE_PRIVATE_KEY_PASSPHRASE'


def read_passphrase(root=ROOT):
    """Read a literal shell assignment, without sourcing/executing .envrc."""
    path = root / '.envrc'
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(descriptor, encoding='utf-8') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o002
                or (info.st_mode & 0o020 and info.st_gid != os.getgid())
                or info.st_size > 65536):
            raise ValueError('unsafe signing configuration')
        values = []
        for line in stream:
            if not re.match(r'^\s*(?:export\s+)?' + VARIABLE + r'\s*=', line):
                continue
            # Shell operators/expansion are never evaluated. Single-quoted
            # literal passwords may contain dollar signs and backticks.
            rhs = line.split('=', 1)[1].strip()
            if not rhs.startswith("'") and any(char in rhs for char in ('$', '`')):
                raise ValueError('signing assignment must be literal')
            words = shlex.split(rhs, comments=True, posix=True)
            if len(words) != 1:
                raise ValueError('invalid signing assignment')
            values.append(words[0])
    if (len(values) != 1 or not values[0].strip()
            or any(char in values[0] for char in ('\n', '\r', '\x00'))
            or values[0].lower() in ('changeme', 'placeholder', 'your-passphrase', 'replace-me')):
        raise ValueError('missing or placeholder signing value')
    return values[0].encode('utf-8')


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    try:
        secret = read_passphrase()
        # An anonymous pipe, inherited only by GnuPG. No passphrase file,
        # environment variable, shell, or pinentry agent is involved.
        reader, writer = os.pipe()
        try:
            # Keep the write below PIPE_BUF so it cannot block before GPG starts.
            if len(secret) > 4095:
                raise ValueError('signing value too long')
            os.write(writer, secret + b'\n')
            os.close(writer)
            writer = None
            env = {key: os.environ[key] for key in ('HOME', 'USER', 'LOGNAME') if key in os.environ}
            env.update(PATH='/usr/bin:/bin', LANG='C.UTF-8')
            result = subprocess.run(
                ['/usr/bin/gpg', '--batch', '--no-tty', '--pinentry-mode', 'loopback',
                 '--passphrase-fd', str(reader), *args],
                env=env, pass_fds=(reader,), stderr=subprocess.PIPE, check=False)
            if result.returncode:
                raise ValueError('batch signing failed')
            # Git requires this machine-readable signing status on stderr.
            # Other GPG diagnostics can contain identities; do not relay them.
            for line in result.stderr.splitlines():
                if line.startswith(b'[GNUPG:] SIG_CREATED '):
                    sys.stderr.buffer.write(line + b'\n')
            return 0
        finally:
            os.close(reader)
            if writer is not None:
                os.close(writer)
    except (OSError, ValueError):
        # Do not print exception text: shlex, OS errors and GPG diagnostics may
        # contain configuration bytes, private identities or paths.
        print('\033[31mSigning failed: check the configured key and literal passphrase in .envrc.\033[0m',
              file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
