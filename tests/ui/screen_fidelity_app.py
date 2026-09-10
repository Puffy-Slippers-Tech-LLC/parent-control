"""Production/preview pixel comparison with identical data and frozen animation.

Only the test owns the clock/RNG and broker substitutions. The normal GTK
window, layout, textures, fonts, scale and compositor all remain real.
"""

import json
import os
from pathlib import Path
import random
import sys

from kiosk.oh_no_parent_control_kiosk import main
from kiosk.oh_no_parent_control_kiosk.preview_screen import notify_screen_ready

random.SystemRandom = lambda: random.Random(7321)
main.GLib.get_monotonic_time = lambda: 5_000_000
output = Path(os.environ["ONPC_FIDELITY_APP"])


class Reply:
    def __init__(self, value):
        self.value = value

    def unpack(self):
        return self.value


class Broker:
    def call(self, _name, _path, _interface, method, parameters, _reply_type,
             _flags, _timeout, _cancellable, callback):
        values = parameters.unpack() if parameters else ()
        replies = {
            "GetOwnAccount": main.PREVIEW_USERS[0],
            "ListManagedUsers": (main.PREVIEW_USERS,),
            "ListApprovers": (main.PREVIEW_APPROVERS,),
        }
        if method == "GetPreferences":
            reply = (json.dumps(main.PREVIEW_PREFERENCES[values[0]]),)
        elif method == "GetTimeStatus":
            reply = (0, 900, values[1], 900 + values[1])
        else:
            reply = replies.get(method, ("saved",))
        main.GLib.idle_add(lambda: (callback(self, Reply(reply)), False)[1])

    @staticmethod
    def call_finish(reply):
        return reply


def window_factory(application, **kwargs):
    production = os.environ["ONPC_FIDELITY_PRODUCTION"] == "1"
    window = main.RequestWindow(application, broker_connection=Broker() if production else None,
                                **kwargs)
    keyvals = []
    keys = main.Gtk.EventControllerKey(propagation_phase=main.Gtk.PropagationPhase.CAPTURE)
    keys.connect("key-pressed", lambda _c, value, _code, _state: (keyvals.append(value), False)[1])
    window.add_controller(keys)
    if production:
        window.connect("map", lambda *_: main.GLib.timeout_add(100, notify_screen_ready, window))

    def record():
        form = window._request_content
        widget = form._duration_buttons[0]
        valid, point = widget.compute_point(window, main.Graphene.Point().init(
            widget.get_width() / 2, widget.get_height() / 2))
        assert valid
        output.write_text(json.dumps({
            "width": window.get_width(), "height": window.get_height(),
            "scale": window.get_surface().get_scale(),
            "duration_target": [point.x, point.y],
            "selected": form.time_estimate_selection(),
            "keyvals": keyvals,
            "active": window.is_active(),
            "focus": type(window.get_focus()).__name__,
        }))
        return True

    window.connect("map", lambda *_: main.GLib.timeout_add(200, record))
    return window


production = os.environ["ONPC_FIDELITY_PRODUCTION"] == "1"
main.configure_logging(preview=True)
app = main.Application(
    preview=not production, child_overlay=os.environ["ONPC_SCREEN_CHILD"] == "1",
    window_factory=window_factory,
)
# Pixel comparisons hold their process inputs fixed throughout the run.
app._watch_preview_files = lambda: None
sys.excepthook = sys.__excepthook__
raise SystemExit(app.run([]))
