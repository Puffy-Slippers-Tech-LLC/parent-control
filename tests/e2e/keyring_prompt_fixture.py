"""Prepare one real login-keyring challenge in the active fixture session.

This is environment setup, not a customer observation. It never supplies or
reads a keyring password. The subsequent AT-SPI operation must find the prompt.
"""

import json
import os
import pwd
import re
import selectors
import stat
import subprocess
import sys


ACCOUNTS = {'parent': 'onpc-parent-jamie', 'standard': 'onpc-child-jordan'}
CHALLENGE = r'''
from gi.repository import Gio, GLib
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

SERVICE = 'org.freedesktop.secrets'
ROOT = '/org/freedesktop/secrets'
INTERFACE = 'org.freedesktop.Secret.Service'
stage = 'session-bus'
signal.alarm(180)
bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)

def call(path, interface, method, signature, values):
    global stage
    stage = method
    return bus.call_sync(SERVICE, path, interface, method,
                         GLib.Variant(signature, values), None,
                         Gio.DBusCallFlags.NONE, 15000, None).unpack()

# Shell normally owns SystemPrompter. Activate the installed gcr provider's
# distinct service; gcr requests replacement of that replaceable bus name.
# This prepares the real provider, without substituting a fixture dialog or
# relaxing the AT-SPI owner check used by the subsequent customer action.
stage = 'gcr-provider'
def bus_call(method, signature, values):
    return bus.call_sync('org.freedesktop.DBus', '/org/freedesktop/DBus',
                         'org.freedesktop.DBus', method,
                         GLib.Variant(signature, values), None,
                         Gio.DBusCallFlags.NONE, 15000, None).unpack()

bus_call('StartServiceByName', '(su)', ('org.gnome.keyring.PrivatePrompter', 0))
provider, = bus_call('GetNameOwner', '(s)', ('org.gnome.keyring.PrivatePrompter',))
deadline = time.monotonic() + 5
while True:
    owner, = bus_call('GetNameOwner', '(s)', ('org.gnome.keyring.SystemPrompter',))
    if owner == provider:
        break
    if time.monotonic() >= deadline:
        raise SystemExit('keyring-fixture:wrong-prompter')
    time.sleep(.1)

# Record the actual provider's locale, not this observation client's locale.
pid, = bus_call('GetConnectionUnixProcessID', '(s)', (provider,))
environment = dict(item.split(b'=', 1) for item in
                   Path('/proc/' + str(pid) + '/environ').read_bytes().split(b'\0')
                   if b'=' in item)
locale = (environment.get(b'LC_ALL') or environment.get(b'LC_MESSAGES')
          or environment.get(b'LANG') or b'C').decode('ascii')
packages = {}
for package in ('gcr', 'gnome-shell'):
    packages[package] = subprocess.check_output(
        ['/usr/bin/dpkg-query', '--show', '--showformat=${Version}', package],
        text=True, timeout=5).strip()
sources = Gio.Settings.new('org.gnome.desktop.input-sources').get_value('sources').unpack()
metadata = {'packages': packages, 'provider_locale': locale,
            'keyboard_sources': [list(source) for source in sources]}

collection, = call(ROOT, INTERFACE, 'ReadAlias', '(s)', ('default',))
if collection == '/':
    raise SystemExit('keyring-fixture:missing-login-collection')
label, = call(collection, 'org.freedesktop.DBus.Properties', 'Get',
              '(ss)', ('org.freedesktop.Secret.Collection', 'Label'))
if label.casefold() != 'login':
    raise SystemExit('keyring-fixture:wrong-collection')
locked, prompt = call(ROOT, INTERFACE, 'Lock', '(ao)', ([collection],))
if locked != [collection] or prompt != '/':
    raise SystemExit('keyring-fixture:lock')
unlocked, prompt = call(ROOT, INTERFACE, 'Unlock', '(ao)', ([collection],))
if unlocked or prompt == '/':
    raise SystemExit('keyring-fixture:missing-challenge')
loop = GLib.MainLoop()
bus.signal_subscribe(None, 'org.freedesktop.Secret.Prompt', 'Completed',
                     prompt, None, Gio.DBusSignalFlags.NONE,
                     lambda *_: loop.quit())
call(prompt, 'org.freedesktop.Secret.Prompt', 'Prompt', '(s)', ('',))
sys.stdout.write(json.dumps(metadata, sort_keys=True) + '\n')
sys.stdout.flush()
GLib.timeout_add_seconds(180, lambda: loop.quit() or False)
loop.run()
'''
# Only fixed stages cross the guest boundary; exception messages may contain
# service data. Keep the preparation code executable in isolation for tests.
CHALLENGE = ("stage = 'startup'\ntry:\n" +
             ''.join('    ' + line + '\n' for line in CHALLENGE.splitlines()) +
             "except BaseException:\n"
             "    print('keyring-fixture:failed:' + stage, flush=True)\n")


def provider_metadata(response):
    """Allow only bounded, nonsecret provider tuple fields into run evidence."""
    try:
        if len(response) > 4096:
            raise ValueError()
        value = json.loads(response)
        if (not isinstance(value, dict)
                or set(value) != {'packages', 'provider_locale', 'keyboard_sources'}
                or not isinstance(value['packages'], dict)
                or set(value['packages']) != {'gcr', 'gnome-shell'}
                or not isinstance(value['keyboard_sources'], list)
                or not 0 < len(value['keyboard_sources']) <= 8):
            raise ValueError()
        words = [*value['packages'].values(), value['provider_locale']]
        for source in value['keyboard_sources']:
            if not isinstance(source, list) or len(source) != 2 or source[0] not in ('xkb', 'ibus'):
                raise ValueError()
            words.extend(source)
        if not all(isinstance(word, str) and re.fullmatch(r'[A-Za-z0-9_.+:@()/-]{1,128}', word)
                   for word in words):
            raise ValueError()
        return value
    except (ValueError, TypeError, KeyError):
        raise ValueError('keyring-fixture:provider-metadata') from None


def stop_child(child):
    """Reap only this invocation's directly spawned challenge process."""
    if child.poll() is None:
        child.terminate()
    try:
        child.wait(timeout=5)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def main():
    if os.geteuid() != 0 or len(sys.argv) != 2 or sys.argv[1] not in ACCOUNTS:
        raise SystemExit('keyring-fixture:arguments')
    account = pwd.getpwnam(ACCOUNTS[sys.argv[1]])
    runtime = '/run/user/' + str(account.pw_uid)
    bus = runtime + '/bus'
    for path, kind in ((runtime, stat.S_ISDIR), (bus, stat.S_ISSOCK)):
        info = os.stat(path, follow_symlinks=False)
        if info.st_uid != account.pw_uid or not kind(info.st_mode):
            raise SystemExit('keyring-fixture:session-owner')
    command = ['/usr/bin/python3', '-I', '-c', CHALLENGE]
    child = subprocess.Popen(command, stdin=subprocess.DEVNULL,
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                             start_new_session=True, close_fds=True,
                             user=account.pw_uid, group=account.pw_gid, extra_groups=[],
                             env={'XDG_RUNTIME_DIR': runtime,
                                  'DBUS_SESSION_BUS_ADDRESS': 'unix:path=' + bus,
                                  'HOME': account.pw_dir, 'USER': account.pw_name,
                                  'LANG': 'C.UTF-8'})
    try:
        with child.stdout, selectors.DefaultSelector() as selector:
            selector.register(child.stdout, selectors.EVENT_READ)
            if not selector.select(30):
                raise SystemExit('keyring-fixture:preparation-timeout')
            response = os.read(child.stdout.fileno(), 4096)
            if response.startswith(b'keyring-fixture:failed:'):
                allowed = {b'keyring-fixture:failed:' + stage.encode() + b'\n'
                           for stage in ('startup', 'session-bus', 'gcr-provider', 'ReadAlias',
                                         'Get', 'Lock', 'Unlock', 'Prompt')}
                raise SystemExit(response.decode().strip() if response in allowed
                                 else 'keyring-fixture:challenge-preparation')
            metadata = provider_metadata(response)
    except BaseException:
        stop_child(child)
        raise
    sys.stdout.buffer.write(json.dumps(metadata, sort_keys=True).encode() + b'\n')
    sys.stdout.buffer.flush()


if __name__ == '__main__':
    main()
