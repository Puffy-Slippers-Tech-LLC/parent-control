"""Noninteractive system and app updates within the installed guest release."""

import os
import pwd
import shutil
import subprocess
import time


def update_packages(os_id):
    environment = {**os.environ, 'DEBIAN_FRONTEND': 'noninteractive', 'NEEDRESTART_MODE': 'a'}
    if os_id == 'ubuntu':
        commands = (
            ['apt-get', '-o', 'APT::Update::Error-Mode=any', 'update'],
            ['apt-get', '-o', 'DPkg::Lock::Timeout=300',
             '-o', 'Dpkg::Options::=--force-confdef', '-o', 'Dpkg::Options::=--force-confold',
             '-o', 'APT::Get::AutomaticRemove::Kernels=true',
             '-y', 'dist-upgrade'],
            ['apt-get', 'check'],
        )
    elif os_id == 'fedora':
        commands = (['dnf5', '--refresh', '-y', 'upgrade'], ['dnf5', 'check'])
    else:
        raise ValueError('baseline:unsupported-os')
    for command in commands:
        print(f'baseline: updating {os_id}: {command[-1]}', flush=True)
        # APT does not classify every gateway error as retryable.
        attempts = 3 if command[-1] == 'update' else 1
        for attempt in range(1, attempts + 1):
            try:
                subprocess.run(command, check=True, timeout=3600, env=environment,
                               stdin=subprocess.DEVNULL)
            except subprocess.CalledProcessError as error:
                if error.returncode != 100 or attempt == attempts:
                    raise
                print('baseline: [update:apt-index-retry] retrying Ubuntu index refresh', flush=True)
                time.sleep(5)
            else:
                break


def update_guest(os_id, *, username='edgar'):
    update_packages(os_id)
    if shutil.which('snap'):
        print('baseline: [update:snap] refreshing installed Snaps', flush=True)
        subprocess.run(['snap', 'wait', 'system', 'seed.loaded'], check=True, timeout=600)
        subprocess.run(['snap', 'refresh'], check=True, timeout=1800)
    if shutil.which('flatpak'):
        print('baseline: [update:flatpak-system] updating system Flatpaks', flush=True)
        update = ['update', '--noninteractive', '-y']
        subprocess.run(['flatpak', '--system', *update], check=True, timeout=1800)
        try:
            pwd.getpwnam(username)
        except KeyError:
            # Older or manually installed baselines may have a different administrator.
            return
        print('baseline: [update:flatpak-user] updating provisioning account Flatpaks', flush=True)
        subprocess.run(['runuser', '-u', username, '--', 'dbus-run-session', '--',
                        'flatpak', '--user', *update], check=True, timeout=1800)
