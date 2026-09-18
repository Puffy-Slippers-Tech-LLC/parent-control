"""Read the shared fixture credential without executing the checkout's .envrc."""

import ctypes
import hmac
import os
from pathlib import Path
import re
import shlex
import stat
import sys
import threading

ROOT = Path(__file__).resolve().parents[2]
VARIABLE = 'TEST_ACCOUNT_PASSWORD'
MESSAGE = 'Set a nonempty literal TEST_ACCOUNT_PASSWORD in .envrc before preparing or testing the VM.'
_crypt_lock = threading.Lock()


def validate(value):
    if (not isinstance(value, str) or not value.strip() or len(value) > 256
            or any(not 32 <= ord(char) <= 126 for char in value)
            or ':' in value or value in {'set_test_account_passsword', 'REPLACE_WITH_TEST_PASSWORD'}):
        raise ValueError(MESSAGE)
    return value


def read_password(root=ROOT):
    """Only a single literal assignment is accepted; never consult environment."""
    try:
        path = Path(root) / '.envrc'
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, encoding='utf-8') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_uid != Path(root).stat().st_uid
                    or info.st_mode & 0o077 or info.st_size > 65536):
                raise ValueError(MESSAGE)
            values = []
            for line in stream:
                if not re.match(r'^\s*(?:export\s+)?' + VARIABLE + r'\s*=', line):
                    continue
                rhs = line.split('=', 1)[1].strip()
                # Only one literal shell word (plus an optional comment).
                if not re.fullmatch(r"(?:'[^']*'|\"[^\"$`\\]*\"|[A-Za-z0-9_./@%+!,=-]+)\s*(?:#.*)?", rhs):
                    raise ValueError(MESSAGE)
                words = shlex.split(rhs, comments=True)
                if len(words) != 1:
                    raise ValueError(MESSAGE)
                values.append(words[0])
        if len(values) != 1:
            raise ValueError(MESSAGE)
        return validate(values[0])
    except (OSError, UnicodeError, ValueError):
        raise ValueError(MESSAGE + ' Use a caller-owned regular file with permissions 0600.') from None


def matches(password, encoded):
    """libcrypt verifies the guest's native SHA-512/yescrypt password hash."""
    if not encoded or encoded.startswith(('!', '*')):
        return False
    with _crypt_lock:
        library = ctypes.CDLL('libcrypt.so.1')
        library.crypt.argtypes = (ctypes.c_char_p, ctypes.c_char_p)
        library.crypt.restype = ctypes.c_char_p
        actual = library.crypt(password.encode('ascii'), encoded.encode('ascii'))
        return actual is not None and hmac.compare_digest(actual, encoded.encode('ascii'))


if __name__ == '__main__':
    try:
        read_password()
    except ValueError as error:
        print(str(error), file=sys.stderr)
        raise SystemExit(1)
