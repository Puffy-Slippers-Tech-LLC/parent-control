"""Bounded exception locations for a disposable preview's UI provider.

No exception messages, locals, request arguments or UI contents are recorded.
The real provider still runs once and propagates its original errors.
"""

from functools import wraps
import json
from pathlib import Path
import sys


def enable_provider_diagnostics():
    """Observe adapter and encoding failures before transport masks them."""
    from common.oh_no_parent_control_ui import application_ui as provider

    remaining = 8

    def report(stage, error):
        nonlocal remaining
        if remaining == 0:
            return
        remaining -= 1
        try:
            frames = []
            trace = error.__traceback__
            while trace is not None and len(frames) < 24:
                code = trace.tb_frame.f_code
                frames.append({"file": Path(code.co_filename).name[:128],
                               "function": code.co_name[:128],
                               "line": trace.tb_lineno})
                trace = trace.tb_next
            print("ONPC_APPLICATION_UI_DIAGNOSTICS " + json.dumps({
                "stage": stage, "exception": type(error).__name__[:128],
                "frames": frames,
            }), file=sys.stderr, flush=True)
        except Exception:
            # Diagnostic output must never replace the provider's exception.
            pass

    def observe(function, stage):
        @wraps(function)
        def observed(*args, **kwargs):
            try:
                return function(*args, **kwargs)
            except Exception as error:
                report(stage, error)
                raise
        return observed

    provider.GtkUIAdapter.call = observe(provider.GtkUIAdapter.call, "adapter")
    provider._encode = observe(provider._encode, "encoding")
    print('ONPC_APPLICATION_UI_DIAGNOSTICS {"stage":"enabled"}',
          file=sys.stderr, flush=True)
