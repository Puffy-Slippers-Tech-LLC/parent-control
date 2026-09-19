"""Deterministic, offline GTK fixture shared by native, Flatpak, Snap and games.

No product imports, policy probes or private observation channel. The displayed
draft and move count are the complete public activity contract. Instance keys
are declared by the scenario, so two windows never depend on titles or order.
"""

import argparse
import sys

import gi

gi.require_version('Gtk', '4.0')
from gi.repository import Gio, Gtk


KINDS = ('native', 'flatpak', 'snap', 'game')
INSTANCES = ('primary', 'secondary')


def identify(widget, identity):
    builder = Gtk.Builder()
    builder.expose_object(identity, widget)
    return widget


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kind', choices=KINDS, required=True)
    parser.add_argument('--instance', choices=INSTANCES, default='primary')
    options = parser.parse_args(argv)
    if Gtk.get_major_version() != 4 or Gtk.get_minor_version() < 22:
        parser.error('GTK 4.22 or newer is required to publish public automation IDs')
    scope = f'onpc-fixture-{options.kind}-{options.instance}'
    app = Gtk.Application(application_id='com.puffyslippers.ONPCFixture',
                          flags=Gio.ApplicationFlags.NON_UNIQUE)

    def activate(application):
        window = identify(Gtk.ApplicationWindow(application=application,
            title='ONPC Test Application', default_width=480, default_height=320), scope)
        content = identify(Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12),
                           scope + '-content')
        window.set_child(content)
        content.append(identify(Gtk.Label(label='Ready'), scope + '-status'))
        # GtkText is an internal delegate with accessibility role NONE. Publish
        # the GtkEntry itself; Edit draft focuses it through normal GTK input.
        draft = identify(Gtk.Entry(), scope + '-draft')
        draft.set_max_length(256)
        draft.set_text('ONPC fixture draft')
        content.append(draft)
        edit = identify(Gtk.Button(label='Edit draft'), scope + '-edit')
        edit.connect('clicked', lambda _button: draft.grab_focus())
        content.append(edit)
        submitted = identify(Gtk.Label(label='No submitted draft'), scope + '-submitted')
        submit = identify(Gtk.Button(label='Submit draft'), scope + '-submit')
        submit.connect('clicked', lambda _button: submitted.set_label(draft.get_text()))
        content.append(submit)
        content.append(submitted)
        # A finite turn-based game: move a token around a four-cell track.
        # Its score and token are public state that can survive session visits.
        moves = 0
        score = identify(Gtk.Label(label='Moves: 0; token: 0'), scope + '-score')
        move = identify(Gtk.Button(label='Move token'), scope + '-move')

        def advance(_button):
            nonlocal moves
            moves += 1
            score.set_label(f'Moves: {moves}; token: {moves % 4}')

        move.connect('clicked', advance)
        content.append(move)
        content.append(score)
        close = identify(Gtk.Button(label='Close'), scope + '-close')
        close.connect('clicked', lambda _button: window.close())
        content.append(close)
        window.present()

    app.connect('activate', activate)
    return app.run([sys.argv[0]])


if __name__ == '__main__':
    raise SystemExit(main())
