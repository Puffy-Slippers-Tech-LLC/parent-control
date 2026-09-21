"""Real spectator with four private synthetic worker transports for UI tests."""

import json
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from ui_watch_transport import Feeds, Publication
from ui_watch_viewer import application

from gi.repository import GLib

directory = Path(os.environ['ONPC_UI_WATCH_REGISTRY'])
control = Path(os.environ['ONPC_UI_WATCH_CONTROL'])
evidence = Path(os.environ['ONPC_UI_WATCH_EVIDENCE'])
sources = []
app = application(Feeds(directory))
stage = ''


def tick():
    global stage
    try:
        requested = control.read_text()
    except FileNotFoundError:
        requested = ''
    if requested != stage:
        stage = requested
        if stage == 'start':
            for index in range(4):
                source = Publication(directory)
                source.frames.publish(b'\x10\x20\x30\0' * 12, state='live', worker=index + 1,
                                      width=4, height=3, stride=16, format=0x20020888,
                                      test=f'case-{index + 1}', phase='call')
                sources.append(source)
            evidence.write_text(json.dumps({'runs': [source.run for source in sources]}))
        elif stage == 'resize':
            app.window.set_default_size(840, 620)
            for source in sources:
                source.frames.publish(phase='teardown')
        elif stage == 'stop':
            for source in sources:
                source.close()
            sources.clear()
        elif stage == 'resume':
            source = Publication(directory)
            source.frames.publish(test='subsequent-case', worker=5, phase='setup')
            sources.append(source)
            evidence.write_text(json.dumps({'runs': [source.run]}))
    for source in sources:
        source.serve()
        source.frames.publish()
    return True


GLib.timeout_add(10, tick)
try:
    result = app.run(['watch-ui-test'])
finally:
    for source in sources:
        source.close()
raise SystemExit(result)
