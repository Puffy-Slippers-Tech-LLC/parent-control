"""Private guest entry point staged only by the host baseline controller."""

import os
from pathlib import Path
import stat
import sys

import prepare_vm


def main():
    root = Path('/var/lib/onpc-baseline-preparation')
    if os.geteuid() != 0 or prepare_vm.CHECKOUT != root / 'checkout':
        return 1
    fd = os.open(root / 'password', os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding='ascii') as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o600):
            return 1
        password = stream.read(257)
    (root / 'password').unlink()
    os.chdir(prepare_vm.CHECKOUT)
    result = prepare_vm.main(password)
    password = ''
    if result == 0:
        (root / 'success').write_text('success\n')
    return result


if __name__ == '__main__':
    sys.exit(main())
