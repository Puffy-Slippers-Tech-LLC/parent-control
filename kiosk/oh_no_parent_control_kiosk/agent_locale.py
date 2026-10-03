"""Set the dedicated kiosk agent's locale through its systemd user service."""

import locale
from pathlib import Path
import re
import subprocess

from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui.languages import selected_language, supported_language

UNIT = 'oh-no-parent-control-polkit-agent.service'
NAME = 'org.freedesktop.systemd1'
PATH = '/org/freedesktop/systemd1'
INTERFACE = NAME + '.Manager'


def installed_locales():
    result = subprocess.run(['/usr/bin/locale', '-a'], check=True, capture_output=True,
                            text=True, timeout=5)
    return tuple(result.stdout.splitlines())


def agent_environment(language, desktop_language, available_locales):
    language = selected_language(language, ())
    available = [value for value in available_locales
                 if re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}', value)
                 and '.utf8' in value.lower().replace('-', '')
                 and not value.lower().startswith('c.')]
    matching = [value for value in available if supported_language(value) == language]
    if not available:
        raise RuntimeError('kiosk authentication requires an installed UTF-8 message locale')
    preferred = matching or available
    fallback = next((value for value in preferred if value.lower().startswith('en_us.')),
                    preferred[0])
    message_locale = next((value for value in preferred
                          if value.lower().replace('-', '') == desktop_language.lower().replace('-', '')),
                         fallback)
    native = {'zh-Hans': 'zh_CN', 'zh-Hant': 'zh_TW',
              'sr-Latn': 'sr_RS@latin'}.get(language, language.replace('-', '_'))
    if (re.fullmatch(r'[A-Za-z0-9_.@-]{1,80}', desktop_language)
            and supported_language(desktop_language) == language):
        registration_locale = desktop_language
    else:
        normalized = locale.normalize(native)
        base, _, modifier = normalized.partition('@')
        registration_locale = base.split('.')[0] + '.UTF-8'
        if modifier:
            registration_locale += '@' + modifier
    # libpolkit-agent registers using LANG. GTK/gettext use LANGUAGE for the
    # agent's own translations. GNU gettext ignores LANGUAGE in C locales;
    # use an installed non-C UTF-8 locale even if the chosen one is absent.
    return (f'LANG={registration_locale}\nLANGUAGE={native}\n'
            f'LC_ALL={message_locale}\n')


class KioskAgentLocale:
    def __init__(self):
        self._applied = None
        self._connection = None
        self._subscription = self._deadline = 0
        self._done = None
        self._job = None
        self._results = {}
        self._revision = 0
        self._locales = None

    def prepare(self, language, desktop_language, done):
        """Complete the agent restart before dispatching an approval request."""
        if self._done is not None:
            done(RuntimeError('kiosk authentication agent restart is already pending'))
            return
        try:
            if self._locales is None:
                self._locales = installed_locales()
            environment = agent_environment(language, desktop_language, self._locales)
        except Exception as error:
            done(error)
            return
        if environment == self._applied:
            done(None)
            return
        # A failed or timed-out restart can still replace the running agent.
        # Never reuse the preceding locale after attempting a different one.
        self._applied = None
        self._done = done
        self._revision += 1
        revision = self._revision
        self._job = None
        self._results = {}
        try:
            directory = Path(GLib.get_user_runtime_dir()) / 'oh-no-parent-control'
            directory.mkdir(mode=0o700, exist_ok=True)
            Gio.File.new_for_path(str(directory / 'polkit-agent.env')).replace_contents(
                environment.encode('ascii'), None, False, Gio.FileCreateFlags.PRIVATE, None)
            self._connection = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            self._subscription = self._connection.signal_subscribe(
                NAME, INTERFACE, 'JobRemoved', PATH, None, Gio.DBusSignalFlags.NONE,
                lambda *args: self._job_removed(*args) if revision == self._revision else None)
            self._deadline = GLib.timeout_add_seconds(30, self._timed_out)

            def restarted(connection, result):
                if self._done is None or revision != self._revision:
                    return
                try:
                    self._job, = connection.call_finish(result).unpack()
                except Exception as error:
                    self._finish(error)
                    return
                if self._job in self._results:
                    self._completed(self._results[self._job])

            self._pending_environment = environment
            self._connection.call(
                NAME, PATH, INTERFACE, 'RestartUnit', GLib.Variant('(ss)', (UNIT, 'replace')),
                GLib.VariantType.new('(o)'), Gio.DBusCallFlags.NONE, 30_000, None, restarted)
        except Exception as error:
            self._finish(error)

    def _job_removed(self, _connection, _sender, _path, _interface, _signal, parameters):
        _identifier, job, unit, result = parameters.unpack()
        if unit != UNIT or self._done is None:
            return
        if job == self._job:
            self._completed(result)
        elif self._job is None:
            self._results[job] = result

    def _completed(self, result):
        if result == 'done':
            self._applied = self._pending_environment
            self._finish(None)
        else:
            self._finish(RuntimeError('kiosk authentication agent restart failed'))

    def _timed_out(self):
        self._deadline = 0
        self._finish(TimeoutError('kiosk authentication agent restart timed out'))
        return GLib.SOURCE_REMOVE

    def _finish(self, error):
        done, self._done = self._done, None
        self.close()
        if done is not None:
            done(error)

    def close(self):
        self._done = None
        self._revision += 1
        if self._subscription:
            self._connection.signal_unsubscribe(self._subscription)
            self._subscription = 0
        if self._deadline:
            GLib.source_remove(self._deadline)
            self._deadline = 0
