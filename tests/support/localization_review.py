"""Public language actions and optional rendered review aids for host previews."""

import os
import tempfile
import time
from pathlib import Path


def switch_language(ui, wait, surface, language):
    # Keep the existing preview facade while using the installed adapter's
    # exact public-ID operations, ownership checks and independent results.
    ui.reader.open_language_preferences(surface)
    ui.reader.choose_language(surface, language)
    ui.reader.save_language(surface)


def public_label_names(ui, identity):
    """Read bounded public content of one identified logical container."""
    from tests.support.application_ui import is_product_node
    root = ui.target(identity)
    if is_product_node(root):
        text = root.getText()
        assert len(text) <= 65536
        return text.splitlines()
    pending = [(root, 0)]
    names = []
    visited = 0
    while pending:
        node, depth = pending.pop()
        visited += 1
        assert visited <= 512 and depth <= 24
        if node.get_role_name() == 'label':
            names.append(node.get_name())
        count = node.get_child_count()
        assert 0 <= count <= 128
        pending.extend((node.get_child_at_index(index), depth + 1) for index in range(count))
    return names


def review_frame(label):
    """Capture the existing spectator feed; pixels never decide test outcomes."""
    import cairo
    from tools.test_retention import allocate
    from tools.ui_watch_transport import Feeds

    feeds = Feeds()
    try:
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for frame in feeds.poll().values():
                meta = frame[1]
                if meta.get('worker') == os.getpid() and meta['state'] == 'live':
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
