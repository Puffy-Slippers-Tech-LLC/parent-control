"""Qualify case 5's search adapter on the existing owned nested Shell."""

import json
from pathlib import Path
import sys
import time

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib
from dogtail.hermetic.mutter import MutterInputBackend
from mutter_input import reconnect, click_at

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from accessible_ui import AccessibleUI, PRODUCT


def main():
    Atspi.set_timeout(2000, 5000)
    ui = AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                      dispatch=lambda: GLib.MainContext.default().iteration(False))
    backend = MutterInputBackend()
    try:
        backend.connectMonitor()
        ui.run('standard-desktop', '')
        backend.generateKeycodePress(133)  # Super+A, like the customer worker.
        backend.generateKeycodePress(38)
        backend.generateKeycodeRelease(38)
        backend.generateKeycodeRelease(133)
        reconnect(backend)
        ui.system_prompt = lambda point: click_at(backend, 1, point['x'], point['y'])
        ui.run('standard-system-prompt', '')
        point = ui.run('standard-app-grid', '')['pointer']
        click_at(backend, 1, point['x'], point['y'])
        ui.run('standard-search-focused', '')
        backend.generateKeysymEvent(ord(PRODUCT[0]))
        reconnect(backend)
        ui.run('standard-search-started', '')
        for character in PRODUCT[1:]:
            backend.generateKeysymEvent(ord(character))
            time.sleep(.1)
        reconnect(backend)
        ui.wait_search(lambda: ui.search_query(PRODUCT), 'typed-query')
        print('e2e-search: typed-query-passed', flush=True)
    except Exception:
        # Local diagnostic vocabulary is fixed. Never print UI names/text.
        print(json.dumps(ui.search_diagnostic()), flush=True)
        root = ui.find('Overview')
        if root is not None:
            for node in ui.nodes(root):
                role = node.get_role_name()
                if role not in ('text', 'entry') or not ui.has_state(node, Atspi.StateType.EDITABLE):
                    continue
                text = node.get_text_iface()
                print(json.dumps({'role': role, 'showing': ui.showing(node),
                    'focused': ui.has_state(node, Atspi.StateType.FOCUSED),
                    'characters': min(Atspi.Text.get_character_count(text), 256)
                        if text is not None else -1}),
                    flush=True)
        raise
    finally:
        backend.disconnect()


if __name__ == '__main__':
    main()
