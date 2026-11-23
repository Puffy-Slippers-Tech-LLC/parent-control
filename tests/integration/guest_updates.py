"""Noninteractive updates within the installed guest release."""

import os
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


def update_apps(username):
    if shutil.which('snap'):
        subprocess.run(['snap', 'wait', 'system', 'seed.loaded'], check=True, timeout=600)
        subprocess.run(['snap', 'refresh'], check=True, timeout=1800)
    if shutil.which('flatpak'):
        user = ['runuser', '-u', username, '--', 'dbus-run-session', '--']
        for prefix, scope in (([], '--system'), (user, '--user')):
            subprocess.run([*prefix, 'flatpak', scope, 'update', '--noninteractive', '-y'],
                           check=True, timeout=1800)
