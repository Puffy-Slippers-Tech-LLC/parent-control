"""Exercise the child panel's stdin entry point without network submissions."""

import io
import sys

from common.oh_no_parent_control_ui import feedback_transport
from kiosk.oh_no_parent_control_kiosk.main import main

feedback_transport.SENDING_ENABLED = False
sys.stdin = io.StringIO("TypeError: child panel could not refresh its timer")
raise SystemExit(main(["--preview", "--child-overlay", "--error-report-stdin"]))
