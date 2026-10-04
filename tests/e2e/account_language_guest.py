"""Supported account-language API mechanics; no file writes or session renewal."""
import grp
import json
import os
import pwd
import sys
import xml.etree.ElementTree as ET

import session_control as sessions

LOCALE = 'zh_CN.UTF-8'
ROLE = 'standard'
DEST = 'org.freedesktop.Accounts'
ROOT = '/org/freedesktop/Accounts'
USER = DEST + '.User'


class LanguageError(RuntimeError):
    pass


def require(value, code):
    if not value:
        raise LanguageError('account-language:' + code)


class AccountsAPI:
    """Fresh synchronous D-Bus reads with finite deadlines and typed replies."""
    def __init__(self):
        from gi.repository import Gio, GLib
        self.Gio, self.GLib = Gio, GLib
        self.bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)

    def call(self, path, interface, method, signature, values, reply):
        try:
            value = self.bus.call_sync(DEST, path, interface, method,
                self.GLib.Variant(signature, values) if signature else None,
                self.GLib.VariantType.new(reply), self.Gio.DBusCallFlags.NONE, 5000, None)
            return value.unpack()
        except Exception:
            raise LanguageError('account-language:api-' +
                ('submission-uncertain' if method == 'SetLanguage' else 'read-failed')) from None

    def resolve(self, account):
        path, = self.call(ROOT, DEST, 'FindUserByName', '(s)', (account.pw_name,), '(o)')
        require(path == ROOT + '/User' + str(account.pw_uid), 'account-path')
        props, = self.call(path, 'org.freedesktop.DBus.Properties', 'GetAll',
                           '(s)', (USER,), '(a{sv})')
        require(type(props.get('Uid')) is int and props['Uid'] == account.pw_uid
                and props.get('UserName') == account.pw_name
                and type(props.get('Language')) is str and len(props['Language']) <= 128,
                'account-identity')
        return path, props['Language']

    def supported(self, path):
        xml, = self.call(path, 'org.freedesktop.DBus.Introspectable', 'Introspect',
                         None, (), '(s)')
        require(type(xml) is str and len(xml) <= 65536, 'api-schema')
        node = ET.fromstring(xml)
        interfaces = node.findall("interface[@name='" + USER + "']")
        require(len(interfaces) == 1, 'api-unsupported')
        methods = interfaces[0].findall("method[@name='SetLanguage']")
        properties = interfaces[0].findall("property[@name='Language']")
        require(len(methods) == len(properties) == 1
                and [(arg.get('type'), arg.get('direction', 'in'))
                     for arg in methods[0].findall('arg')] == [('s', 'in')]
                and properties[0].get('type') == 's'
                and properties[0].get('access') in ('read', 'readwrite'), 'api-unsupported')

    def set_language(self, path, language):
        require(self.call(path, USER, 'SetLanguage', '(s)', (language,), '()') == (),
                'submission-reply')


def accounts():
    # ListCachedUsers is not exhaustive. Read NSS, including system/unrelated
    # accounts; never create an absent station user on the product-free baseline.
    result = sorted(pwd.getpwall(), key=lambda item: item.pw_uid)
    require(0 < len(result) <= 128 and len({item.pw_uid for item in result}) == len(result)
            and len({item.pw_name for item in result}) == len(result), 'account-bound')
    return result


def authority():
    require(os.geteuid() == 0, 'root-transport')
    parent = pwd.getpwnam(sessions.ACCOUNTS['parent'])
    require(parent.pw_uid >= 1000 and grp.getgrnam('sudo').gr_gid
            in os.getgrouplist(parent.pw_name, parent.pw_gid), 'administrator')
    return parent, sessions.source_session(sessions.sessions(), parent.pw_uid)


def set_language(api, role, language):
    require(role == ROLE, 'target-binding')
    require(language == LOCALE, 'locale-binding')
    parent, source = authority()
    target = pwd.getpwnam(sessions.ACCOUNTS[role])
    require(target.pw_uid >= 1000 and target.pw_uid != parent.pw_uid, 'fixture-identity')
    path, previous = api.resolve(target)
    api.supported(path)
    installed = sessions.call(['/usr/bin/locale', '-a']).splitlines()
    require(any(item.lower().replace('-', '') == 'zh_cn.utf8' for item in installed),
            'locale-not-installed')
    require(api.resolve(target) == (path, previous)
            and pwd.getpwnam(target.pw_name) == target
            and sessions.source_session(sessions.sessions(), parent.pw_uid) == source,
            'entry-changed')
    # One mutation; no fallback, polling setter or retry after any error.
    api.set_language(path, language)
    return {'accepted': True}


def system_locale():
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    locale = bus.call_sync('org.freedesktop.locale1', '/org/freedesktop/locale1',
        'org.freedesktop.DBus.Properties', 'Get',
        GLib.Variant('(ss)', ('org.freedesktop.locale1', 'Locale')),
        GLib.VariantType.new('(v)'), Gio.DBusCallFlags.NONE, 5000, None).unpack()[0]
    require(type(locale) in (list, tuple) and len(locale) <= 32
            and all(type(item) is str and len(item) <= 256 for item in locale), 'system-locale')
    return list(locale)


def snapshot(api, *, product_free=True):
    require(os.geteuid() == 0, 'root-transport')
    users = accounts()
    values = {str(item.pw_uid): {'name': item.pw_name, 'language': api.resolve(item)[1]}
              for item in users}
    require(accounts() == users, 'accounts-changed')
    # These are engineering preservation witnesses, not product acceptance.
    absent = not any(os.path.lexists(path) for path in (
        '/var/lib/oh-no-parent-control', '/etc/oh-no-parent-control',
        '/usr/bin/oh-no-parent-control-parent', '/usr/lib/oh-no-parent-control'))
    package = sessions.call(['/usr/bin/dpkg-query', '-W', '-f=${binary:Package}\n'])
    installed = any(item.split(':')[0] == 'oh-no-parent-control' for item in package.splitlines())
    if product_free:
        require(absent, 'product-state-present')
        require(not any(item.split(':')[0] in ('oh-no-parent-control', 'oh-no-parent-control-dbgsym')
                        for item in package.splitlines()), 'product-package-present')
    else:
        require(installed and not absent, 'installed-product-required')
    # Each guarded SSH command has a new remote session. Preserve the local
    # graphical identities; remote transport lifetimes are owned by its guard.
    graphical = {key: item for key, item in sessions.sessions().items()
                 if sessions.local_graphical(item)}
    return {'accounts': values, 'sessions': graphical,
            'system_locale': system_locale(), 'observer_locale': {
                key: value for key, value in os.environ.items()
                if key in ('LANG', 'LANGUAGE') or key.startswith('LC_')},
            'product_free': product_free,
            'target_uid': str(pwd.getpwnam(sessions.ACCOUNTS[ROLE]).pw_uid)}


def execute(action, role, language, api=None):
    require(action in ('read', 'read-installed', 'set', 'refuse', 'reject-inputs'), 'action')
    api = AccountsAPI() if api is None else api
    if action in ('read', 'read-installed'):
        return snapshot(api, product_free=action == 'read')
    if action == 'set':
        return set_language(api, role, language)
    if action == 'refuse':
        current = sessions.sessions()
        active = [item for item in current.values() if sessions.local_graphical(item)
                  and item['Active'] == 'yes']
        require(len(active) == 1 and active[0]['Class'] == 'greeter', 'expected-greeter')
        try:
            set_language(api, role, language)
        except sessions.SessionError as error:
            require(str(error) == 'session:source-owner', 'unexpected-refusal')
            return {'wrong_entry_refused': True}
        require(False, 'wrong-entry-accepted')
    authority()
    for target, locale, error in (('parent', LOCALE, 'target-binding'),
                                 (ROLE, 'zz_ZZ.UTF-8', 'locale-binding')):
        try:
            set_language(api, target, locale)
        except LanguageError as failure:
            require(str(failure) == 'account-language:' + error, 'unexpected-refusal')
        else:
            require(False, 'invalid-input-accepted')
    return {'wrong_account_refused': True, 'undeclared_locale_refused': True}


if __name__ == '__main__':
    try:
        require(len(sys.argv) == 4, 'arguments')
        print(json.dumps(execute(*sys.argv[1:]), sort_keys=True))
    except (LanguageError, sessions.SessionError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
    except Exception:
        print('account-language:operation-failed', file=sys.stderr)
        sys.exit(1)
