"""Exercise the child panel's stdin entry point without network submissions."""

import io
import json
import os
import sys

from common.oh_no_parent_control_ui import feedback_transport
from kiosk.oh_no_parent_control_kiosk.main import Application, main


_register = Application.do_dbus_register


def register_application_ui(self, connection, object_path):
    registered = _register(self, connection, object_path)
    if registered:
        print('ONPC_APPLICATION_UI_ENDPOINT ' + json.dumps({
            'application_id': self.get_application_id(),
            'owner': connection.get_unique_name(),
            'object_path': object_path,
            'pid': os.getpid(),
        }, sort_keys=True), flush=True)
    return registered


Application.do_dbus_register = register_application_ui

feedback_transport.SENDING_ENABLED = False
sys.stdin = io.StringIO("TypeError: child panel could not refresh its timer")
raise SystemExit(main(["--preview", "--child-overlay", "--error-report-stdin"]))
