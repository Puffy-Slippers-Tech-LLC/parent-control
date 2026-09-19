"""Input delivery lifecycle shared by the nested-Shell interaction harness."""

import time


def reconnect(backend):
    """Finish the virtual-device session before observing the delivered action."""
    backend.disconnect()
    time.sleep(0.1)
    backend.connectMonitor()


def press_key(backend, keycode):
    backend.generateKeycodePress(keycode)
    time.sleep(0.1)
    backend.generateKeycodeRelease(keycode)
    reconnect(backend)


def click_at(backend, button, x, y):
    """Refuse retained coordinate callers before touching the input backend."""
    raise RuntimeError("pointer input requires an ID-addressed semantic action")
