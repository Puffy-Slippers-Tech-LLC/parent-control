"""Public language actions and optional rendered review aids for host previews."""

import os
import tempfile
import time
from pathlib import Path


def switch_language(ui, wait, surface, language):
    ui.activate('parent-menu-button' if surface == 'parent' else 'kiosk-menu-button')
    ui.activate('parent-menu-preferences' if surface == 'parent'
                else 'kiosk-menu-item-preferences')
    wait(lambda: ui.showing('language-dialog'), 'language chooser opens')
    ui.activate('language-choice-' + language.lower())
    ui.activate('language-continue')
    wait(lambda: ui.absent('language-dialog', within=(
        'parent-window' if surface == 'parent' else 'kiosk-request-window')),
        'language chooser commits and closes')


def review_frame(label):
    """Capture the existing spectator feed; pixels never decide test outcomes."""
    import cairo
    from tools.test_retention import allocate
    from tools.ui_watch_transport import Feeds

    feeds = Feeds()
    started = time.monotonic_ns()
    try:
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for frame in feeds.poll().values():
                meta = frame[1]
                if (meta.get('worker') == os.getpid() and meta['state'] == 'live'
                        and meta.get('captured_ns', 0) > started + 300_000_000):
                    directory = Path(allocate(tempfile.mkdtemp, prefix='onpc-localization-review-'))
                    path = directory / (label + '.png')
                    pixels = bytearray(frame[2])
                    texture = cairo.ImageSurface.create_for_data(pixels, cairo.FORMAT_RGB24,
                        meta['width'], meta['height'], meta['stride'])
                    texture.write_to_png(str(path))
                    print('Localization layout review image:', path, flush=True)
                    return
            time.sleep(.05)
        print('Localization layout review image unavailable', flush=True)
    finally:
        feeds.close()
