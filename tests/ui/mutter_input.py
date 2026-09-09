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
    # Mutter queues device events. Allow pointer crossing to reach Shell before
    # pressing, and allow each button transition to dispatch before ending the
    # session. A combined motion/press/release can leave only hover delivered.
    backend.generateMotionEvent(x, y)
    time.sleep(0.1)
    backend.generateButtonPress(button)
    time.sleep(0.1)
    backend.generateButtonRelease(button)
    time.sleep(0.1)
    reconnect(backend)
