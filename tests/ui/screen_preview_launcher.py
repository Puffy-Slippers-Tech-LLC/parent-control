"""Run the real Save/replacement supervisor with its actual video viewer."""

import sys

from kiosk.oh_no_parent_control_kiosk.preview import PreviewSession, main
from tests.support.paths import ROOT


def session_factory(screen, host, **kwargs):
    return PreviewSession(screen, host,
                          app_command=[sys.executable, str(ROOT / "tests/ui/screen_preview_probe.py")],
                          **kwargs)


raise SystemExit(main([], session_factory=session_factory))
