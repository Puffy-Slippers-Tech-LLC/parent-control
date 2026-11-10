"""Installed snapshot recipe, separate from changeable tests and diagnostics.

Changes here invalidate installed snapshots. Test/helper changes do not.
"""

import os
import json
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


def prepare_upgrade(transport, command, guard, directory, usernames, operation, payload):
    """The genuine prior/current activation recipe, shared with snapshot capture."""
    def accounts():
        return [transport.call(['getent', 'passwd', *usernames]),
                *[transport.call(['id', '-G', name]) for name in usernames]]

    before = accounts()
    with operation('Installing the genuine prior release and observing its activation'):
        transport.call(command('install-previous'), timeout=2400)
        guard()
        transport.reboot()
        guard()
    with operation('Updating the request station and observing its required activation'):
        transport.call(command('upgrade'), timeout=2400)
        guard()
        transport.reboot()
        guard()
        transport.call(command('verify-setup'), timeout=660)
    if accounts() != before:
        raise RuntimeError('kiosk-update:ordinary-accounts-changed')
    transport.copy(True, payload + '/results/',
                   str(directory / 'update-results') + '/')
    result = json.loads((directory / 'update-results/update-activation.json').read_bytes())
    if not (result['old_package_reboot_observed'] is True
            and result['update_requested_reboot'] is True
            and result['same_version_reinstall'] is False):
        raise RuntimeError('kiosk-update:activation-incomplete')
    guard()
    return {**result, 'candidate_reboot_verified': True, 'ordinary_accounts_preserved': True}
