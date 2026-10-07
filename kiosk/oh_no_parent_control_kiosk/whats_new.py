"""Account-bound, asynchronous release-note presentation for both request modes."""

import json

from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.diagnostic_events import get_logger, error_code
from .whats_new_dialog import WhatsNewDialog


LOG = get_logger('kiosk')


class WhatsNewPresenter:
    def __init__(self, window):
        self.window = window
        self.target_uid = None
        self.revision = 0
        self.record = None
        self.dialog = None
        self.menu_item = None
        self.attempted = set()
        self.wait_id = 0
        self.closed = False

    def select_child(self, target_uid):
        self.revision += 1
        self.target_uid = target_uid
        self.record = None
        self._cancel_wait()
        if self.dialog is not None:
            # Account replacement is teardown, never acknowledgement.
            self.dialog.destroy()
            self.dialog = None
        self.menu_item.set_visible(False)
        self._call(False)

    def _call(self, acknowledge):
        revision = self.revision
        window = self.window
        if window._preview and not window._interactive_preview:
            from broker.oh_no_parent_control.whats_new import read_metadata, validate_metadata, product_version
            from common.oh_no_parent_control_ui.about import app_version, branding_asset_path
            try:
                version = product_version(app_version())
                records = [dict(record, record_id=version + ':Child', auto_show=False)
                           for record in validate_metadata(read_metadata(
                               branding_asset_path('whats-new-child.toml')))
                           if record['ProductVersion'] == version]
                self._loaded({'product_version': version, 'records': records})
            except Exception as error:
                self._failed(error)
            return
        method = ('Acknowledge' if acknowledge else 'Get') + (
            'OwnWhatsNew' if window._child_overlay else 'ChildWhatsNew')
        values = () if window._child_overlay else (self.target_uid,)
        signature = '' if window._child_overlay else 'u'
        if acknowledge:
            values += (self.record['ProductVersion'],)
            signature += 's'

        def finished(connection, result):
            if self.closed or revision != self.revision:
                return
            try:
                encoded, = connection.call_finish(result).unpack()
                value = json.loads(encoded)
                self._loaded(value)
            except Exception as error:
                self._failed(error)

        try:
            window._bus_call(method, GLib.Variant(f'({signature})', values), '(s)', finished)
        except Exception as error:
            self._failed(error)

    def _loaded(self, value):
        version = value['product_version']
        record = next((record for record in value['records']
                       if record['ProductVersion'] == version
                       and record['record_id'] == version + ':Child'), None)
        self.record = record
        self.menu_item.set_visible(record is not None)
        self.try_auto()

    def _failed(self, error):
        # Release information is optional: never replace setup, a request,
        # or its result with an error screen. The broker retains eligibility.
        LOG.warning('kiosk.030', error_type=error_code(error))

    def _cancel_wait(self):
        if self.wait_id:
            GLib.source_remove(self.wait_id)
            self.wait_id = 0

    def _ready(self):
        window = self.window
        return (not self.closed and window._language_ready
                and not window._language_loading and window._language_dialog is None
                and not window._state.in_flight and not getattr(window, '_reboot_required', False))

    def _modal_blocked(self):
        if self.window.get_dialogs().get_n_items():
            return True
        windows = Gtk.Window.get_toplevels()
        for index in range(windows.get_n_items()):
            window = windows.get_item(index)
            if not window.get_visible() or not window.get_modal():
                continue
            owner = window.get_transient_for()
            visited = set()
            while owner is not None and owner not in visited:
                if owner is self.window:
                    return True
                visited.add(owner)
                owner = owner.get_transient_for()
        return False

    def try_auto(self):
        self._cancel_wait()
        if (self.closed or self.record is None or not self.record['auto_show']
                or self.target_uid in self.attempted):
            return GLib.SOURCE_REMOVE
        if (self._ready() and self.window._stack.get_visible_child_name() == 'request'
                and not self._modal_blocked()):
            self.show()
        else:
            def retry():
                self.wait_id = 0
                return self.try_auto()
            self.wait_id = GLib.timeout_add(250, retry)
        return GLib.SOURCE_REMOVE

    def show(self):
        if not self.record or not self._ready():
            return
        if self.dialog is not None:
            self.dialog.present()
            return
        if self._modal_blocked():
            return
        revision = self.revision
        record = self.record

        def closed(displayed):
            if self.closed or revision != self.revision:
                return
            self.dialog = None
            if displayed:
                self._call(True)

        try:
            self.dialog = WhatsNewDialog(self.window, record, closed,
                                         links_enabled=self.window._child_overlay)
            self.dialog.present()
        except Exception as error:
            if self.dialog is not None:
                self.dialog.destroy()
                self.dialog = None
            self._failed(error)
        self.attempted.add(self.target_uid)

    def close(self):
        self.closed = True
        self._cancel_wait()
        if self.dialog is not None:
            self.dialog.destroy()
            self.dialog = None
