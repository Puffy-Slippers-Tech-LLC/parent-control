"""Deterministic, offline GTK fixture shared by native, Flatpak, Snap and games.

No product imports, policy probes or private observation channel. The displayed
draft and move count are the complete public activity contract. Instance keys
are declared by the scenario, so two windows never depend on titles or order.
"""

import argparse
import json
import sys

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, Gtk

from gtk_automation import add_identified_window_controls, set_automation_id


KINDS = ('native', 'flatpak', 'snap', 'game')
INSTANCES = ('primary', 'secondary', 'hard', 'soft')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--instance', choices=INSTANCES, default='primary')
    parser.add_argument('--fullscreen', action='store_true', help='Open the fixed game level fullscreen')
    parser.add_argument('--work-document', help='Exact child work-document receipt')
    options = parser.parse_args(argv)
    document = None
    if options.work_document is not None:
        if options.kind != 'native' or options.instance != 'primary' or len(options.work_document) > 4096:
            parser.error('Work documents belong to the primary native fixture')
        from work_document import Document
        receipt = json.loads(options.work_document)
        document = Document(receipt['user'], receipt)
    if options.fullscreen and options.kind != 'game':
        parser.error('Fullscreen belongs to the game fixture')
    if options.kind not in ('native', 'flatpak') and options.instance in ('hard', 'soft'):
        parser.error('Hard and Soft instances belong to the native/Flatpak fixtures')
    if Gtk.get_major_version() != 4 or Gtk.get_minor_version() < 22:
        parser.error('GTK 4.22 or newer is required to publish public automation IDs')
    scope = f'onpc-fixture-{options.kind}-{options.instance}'
    app = Gtk.Application(application_id=f'com.puffyslippers.ONPCFixture.{options.kind}.{options.instance}',
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(application):
        window = set_automation_id(Gtk.ApplicationWindow(application=application,
            title='ONPC Test Application', default_width=480, default_height=320), scope)
        header = Gtk.HeaderBar()
        add_identified_window_controls(header, scope + '-window-controls')
        window.set_titlebar(header)
        content = set_automation_id(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12),
                           scope + '-content')
        window.set_child(content)
        content.append(set_automation_id(Gtk.Label(label='Ready'), scope + '-status'))
        if options.kind == 'game':
            # The game has one fixed starting level. Publish the actual window
            # mode, rather than inferring it from launch success or geometry.
            mode = set_automation_id(Gtk.Label(), scope + '-mode')
            def read_mode(*_args):
                mode.set_label(('Fullscreen' if window.is_fullscreen() else 'Windowed') + '; level: 1')
            window.connect('notify::fullscreened', read_mode)
            read_mode()
            content.append(mode)
        # GtkText is an internal delegate with accessibility role NONE. Publish
        # the GtkEntry itself; Edit draft focuses it through normal GTK input.
        draft = set_automation_id(Gtk.Entry(), scope + '-draft')
        draft.set_max_length(256)
        draft.set_text(document.read()[0] if document else 'ONPC fixture draft')
        content.append(draft)
        edit = set_automation_id(Gtk.Button(label='Edit draft'), scope + '-edit')
        edit.connect('clicked', lambda _button: draft.grab_focus())
        content.append(edit)
        submitted = set_automation_id(Gtk.Label(label='No submitted draft'), scope + '-submitted')
        submit = set_automation_id(Gtk.Button(label='Submit draft'), scope + '-submit')
        submit.connect('clicked', lambda _button: submitted.set_label(draft.get_text()))
        content.append(submit)
        content.append(submitted)
        if document:
            saved = set_automation_id(Gtk.Label(label='Document opened'), scope + '-saved')
            save = set_automation_id(Gtk.Button(label='Save document'), scope + '-save')
            def save_document(_button):
                save.set_sensitive(False)
                try:
                    document.save(draft.get_text())
                except (ValueError, OSError):
                    saved.set_label('Document save refused')
                else:
                    saved.set_label('Document saved')
            save.connect('clicked', save_document)
            content.append(save)
            content.append(saved)
        # A finite turn-based game: move a token around a four-cell track.
        # Its score and token are public state that can survive session visits.
        moves = 0
        score = set_automation_id(Gtk.Label(label='Moves: 0; token: 0'), scope + '-score')
        move = set_automation_id(Gtk.Button(label='Move token'), scope + '-move')

        def advance(_button):
            nonlocal moves
            moves += 1
            score.set_label(f'Moves: {moves}; token: {moves % 4}')

        move.connect('clicked', advance)
        content.append(move)
        content.append(score)
        close = set_automation_id(Gtk.Button(label='Close'), scope + '-close')
        close.connect('clicked', lambda _button: window.close())
        content.append(close)
        if options.fullscreen:
            window.fullscreen()
        window.present()

    app.connect('activate', activate)
    try:
        return app.run([sys.argv[0]])
    finally:
        if document:
            document.close()


if __name__ == '__main__':
    raise SystemExit(main())
