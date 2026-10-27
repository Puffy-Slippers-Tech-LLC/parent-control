"""One app-only locale fault inside the existing installed approval history."""
import json
import os
from pathlib import Path
import pwd
import secrets
import sys

UNIT = 'oh-no-parent-control-app.service'


def require(value, code):
    if not value:
        raise RuntimeError(code)


def guest_operation(action, token, receipt):
    sys.path.insert(0, '/var/tmp/onpc-system-input')
    import system_guest as guest
    from system_kiosk_confinement import (ACCOUNT, SERVICES, user_command,
                                         user_unit, wait_kiosk_inactive)
    marker = guest.guard()
    guest.enable_diagnostics()
    require(len(token) == 32 and all(value in '0123456789abcdef' for value in token),
            'basic-locale:token')
    account = pwd.getpwnam(ACCOUNT)
    require(account.pw_uid > 0 and account.pw_shell == '/usr/sbin/nologin',
            'basic-locale:account')
    directory = Path('/etc/systemd/user') / (UNIT + '.d')
    dropin = directory / ('90-onpc-basic-locale-' + token + '.conf')
    # Inline startup avoids a separate temporary executable and its trust setup.
    # The installed entry point and genuine vendor agent remain unchanged.
    code = (
        "import os,runpy,sys;"
        f"assert os.getuid()=={account.pw_uid};"
        "sys.path[:0]=['/usr/lib/oh-no-parent-control',"
        "'/usr/lib/oh-no-parent-control/kiosk'];"
        "from oh_no_parent_control_kiosk import agent_locale;"
        "agent_locale.installed_locales=lambda:('C','C.utf8','POSIX');"
        "sys.argv=['/usr/bin/oh-no-parent-control'];"
        "runpy.run_path(sys.argv[0],run_name='__main__')"
    )
    body = ('[Service]\nExecStart=\nExecStart=/usr/bin/python3 -I -c '
            + json.dumps(code) + '\n').encode('ascii')
    boot = Path('/proc/sys/kernel/random/boot_id').read_text()
    if action == 'install':
        wait_kiosk_inactive(account)
        created = not directory.exists()
        if created:
            directory.mkdir(mode=0o755)
        info = directory.lstat()
        require(directory.is_dir() and not directory.is_symlink()
                and info.st_uid == 0 and not info.st_mode & 0o022
                and not list(directory.iterdir()), 'basic-locale:foreign-dropins')
        inventory = guest.run(['/usr/bin/locale', '-a'])
        # Exclusive creation preserves pre-existing configuration. The outer
        # runner restores its owned VM if installation fails before this reply.
        with dropin.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o644)
            stream.write(body)
            stream.flush()
            os.fsync(stream.fileno())
            written = os.fstat(stream.fileno())
        return {'run': marker['run'], 'boot': boot, 'uid': account.pw_uid,
                'directory': [info.st_dev, info.st_ino], 'created': created,
                'file': [written.st_dev, written.st_ino], 'inventory': inventory}

    require(receipt['run'] == marker['run'] and receipt['boot'] == boot
            and receipt['uid'] == account.pw_uid, 'basic-locale:attempt-changed')
    info, entry = directory.lstat(), dropin.lstat()
    require(not directory.is_symlink() and [info.st_dev, info.st_ino] == receipt['directory']
            and dropin.is_file() and not dropin.is_symlink() and entry.st_uid == 0
            and entry.st_nlink == 1 and not entry.st_mode & 0o022
            and [entry.st_dev, entry.st_ino] == receipt['file']
            and dropin.read_bytes() == body, 'basic-locale:owned-override-changed')
    if action == 'observe':
        app, agent = user_unit(account, UNIT), user_unit(account, SERVICES['polkit'])
        require(app['ActiveState'] == agent['ActiveState'] == 'active',
                'basic-locale:inactive-services')
        require((Path('/proc') / app['MainPID'] / 'cmdline').read_bytes().split(b'\0') ==
                [b'/usr/bin/python3', b'-I', b'-c', code.encode('ascii'), b''],
                'basic-locale:app-launcher')
        process = Path('/proc') / agent['MainPID']
        require(os.readlink(process / 'exe') == '/usr/libexec/polkit-mate-authentication-agent-1',
                'basic-locale:vendor-agent')
        environment = dict(item.split(b'=', 1) for item in
                           (process / 'environ').read_bytes().split(b'\0') if b'=' in item)
        require({key: environment.get(key) for key in (b'LANG', b'LANGUAGE', b'LC_ALL')} ==
                {b'LANG': b'C.utf8', b'LANGUAGE': b'C', b'LC_ALL': b'C.utf8'},
                'basic-locale:fallback-not-applied')
        return {'successful_basic_discovery': True, 'native_agent_basic_environment': True}

    require(action == 'restore', 'basic-locale:operation')
    dropin.unlink()
    if receipt['created']:
        directory.rmdir()
    if guest.run(['systemctl', 'show', '--value', '--property=ActiveState',
                  f'user@{account.pw_uid}.service']) == 'active':
        user_command(account, ['/usr/bin/systemctl', '--user', 'daemon-reload'])
    require(guest.run(['/usr/bin/locale', '-a']) == receipt['inventory'],
            'basic-locale:system-inventory-changed')
    return {'restored': True, 'system_locale_unchanged': True}


class BasicLocaleFault:
    def __init__(self, journey, lease):
        self.journey, self.lease = journey, lease
        self.token, self.receipt, self.restored = secrets.token_hex(16), None, False
        self.source = Path(__file__).read_bytes()

    def call(self, action):
        import watch_activity
        self.lease.guard()
        intention = {'install': 'Preparing basic language settings for the request app',
                     'observe': 'Checking native approval with basic language settings',
                     'restore': 'Restoring normal request language settings'}[action]
        with watch_activity.operation(intention):
            raw = self.journey.transport.call([
                'env', 'ONPC_EXPECTED_RUN=' + self.lease.state['run'],
                '/usr/bin/python3', '-I', '-', action, self.token,
                json.dumps(self.receipt)], input=self.source, timeout=120)
        self.lease.guard()
        require(type(raw) is bytes and 0 < len(raw) <= 65536, 'basic-locale:response-bound')
        return json.loads(raw)

    def install(self):
        self.receipt = self.call('install')
        return {'installed': True, 'discovery_failure': False}

    def restore(self):
        if self.receipt is not None and not self.restored:
            value = self.call('restore')
            require(value.get('restored') is True, 'basic-locale:restoration')
            self.restored = True
            return value


if __name__ == '__main__':
    require(len(sys.argv) == 4 and sys.argv[1] in ('install', 'observe', 'restore'),
            'basic-locale:arguments')
    print(json.dumps(guest_operation(sys.argv[1], sys.argv[2], json.loads(sys.argv[3])),
                     sort_keys=True))
