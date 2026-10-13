"""Installed snapshot recipe, separate from changeable tests and diagnostics.

Changes here invalidate installed snapshots. Test/helper changes do not.
"""

import os
from pathlib import Path


def install(run, guard, package):
    # Use the checkout's frozen public installation entry point for current
    # and previous packages. It owns dependency resolution and reinstalls.
    makefile = Path(__file__).resolve().parent / 'install-source/Makefile'
    os.environ['DEBIAN_FRONTEND'] = 'noninteractive'
    guard()
    run(['make', '--no-print-directory', '-C', str(makefile.parent), 'install',
         'INSTALL_PACKAGE=' + str(package.resolve()),
         'APT=apt-get -o DPkg::Lock::Timeout=120 --no-install-recommends -y',
         'DNF=dnf -y'], timeout=2400)


def prepare(transport, command, guard, *, reboot=True):
    transport.call(command, timeout=1200)
    guard()
    if reboot:
        transport.reboot()
        guard()
