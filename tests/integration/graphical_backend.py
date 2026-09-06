#!/usr/bin/python3
"""Read-only os-autoinst tooling preflight; never opens or controls a VM."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import time

from owned_commands import Commands


ROOT = Path(__file__).resolve().parents[2]
PACKAGES = ('os-autoinst', 'libfeature-compat-try-perl')
BACKEND = Path('/usr/lib/os-autoinst/backend/generalhw.pm')
ENTRYPOINT = Path('/usr/bin/isotovideo')


class PreflightError(RuntimeError):
    """Fixed diagnostic category; child output and environment are not exported."""


def package_pins(path=ROOT / 'tests/test-tools-ubuntu-26.04.txt'):
    pins = {}
    for line in path.read_text().splitlines():
        name, separator, version = line.partition('=')
        if name in PACKAGES and separator:
            if name in pins or not re.fullmatch(r'[0-9A-Za-z.+:~\-]+', version):
                raise PreflightError('tools:invalid-package-pin')
            pins[name] = version
    if set(pins) != set(PACKAGES):
        raise PreflightError('tools:missing-package-pin')
    return pins


def probe(commands, arguments, category):
    try:
        return commands.run(arguments, timeout=30)
    except Exception as error:
        raise PreflightError(category) from error


def check(commands=None, *, pins=None):
    """Require the reviewed package, working CLI and loadable generalhw backend.

    A version-only check misses backend-specific Perl dependencies. Perl's
    compile check loads this backend's dependencies without constructing it or
    running its lifecycle methods. Keep this result separate from live smoke.
    """
    commands = commands if commands is not None else Commands()
    pins = package_pins() if pins is None else pins
    started = time.monotonic()
    for name in PACKAGES:
        raw = probe(commands, ['/usr/bin/dpkg-query', '-W',
                              '-f=${Status}\n${Version}\n', name],
                    'tools:package-unavailable:' + name)
        if raw != f'install ok installed\n{pins[name]}\n'.encode():
            raise PreflightError('tools:package-mismatch:' + name)
    version = probe(commands, [str(ENTRYPOINT), '--version'], 'tools:entrypoint-failed')
    # The Ubuntu build reports version "unknown"; package metadata above owns
    # version identity. Export only the numeric public test API version.
    api = re.search(rb'\[interface v([0-9]+)\]', version)
    if api is None or api.group(1) != b'48':
        raise PreflightError('tools:unexpected-test-api')
    probe(commands, ['/usr/bin/perl', '-I/usr/lib/os-autoinst', '-c', str(BACKEND)],
          'tools:generalhw-load-failed')
    return {
        'schema_version': 1, 'scope': 'tooling-only', 'outcome': 'passed',
        'backend': 'generalhw', 'test_api': 48, 'packages': pins,
        'files_sha256': {str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                         for path in (ENTRYPOINT, BACKEND)},
        'duration_seconds': round(time.monotonic() - started, 3),
        'graphical_smoke': 'not-run', 'vm_access': False,
    }


def main(argv=None):
    argparse.ArgumentParser(description=__doc__).parse_args(argv)
    try:
        result = check()
    except (Exception, KeyboardInterrupt) as error:
        category = str(error) if isinstance(error, PreflightError) else 'tools:preflight-failed'
        print(json.dumps({'scope': 'tooling-only', 'outcome': 'failed',
                          'category': category, 'graphical_smoke': 'not-run',
                          'vm_access': False}, sort_keys=True))
        return 1
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
