"""Installed snapshot recipe, separate from changeable tests and diagnostics.

Changes here invalidate installed snapshots. Test/helper changes do not.
"""

import os


def install(run, guard, package):
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    run(['apt-get', 'update'], timeout=600)
    guard()
    run(['apt-get', '-o', 'DPkg::Lock::Timeout=120', 'install', '--no-install-recommends',
         '-y', str(package)], timeout=1800)


def prepare(transport, command, guard, *, reboot=True):
    transport.call(command, timeout=1200)
    guard()
    if reboot:
        transport.reboot()
        guard()
