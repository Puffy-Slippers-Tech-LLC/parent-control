"""Exercise the child panel's stdin entry point without network submissions."""

import io
import json
import os
import sys

from common.oh_no_parent_control_ui import feedback_transport
from kiosk.oh_no_parent_control_kiosk import main as kiosk_main


class PreviewApplication(kiosk_main.Application):
    # PyGObject wires virtual methods when creating the class. Assigning a
    # replacement to the existing class leaves the native callback unchanged.
    def do_dbus_register(self, connection, object_path):
        registered = super().do_dbus_register(connection, object_path)
        if registered:
            print('ONPC_APPLICATION_UI_ENDPOINT ' + json.dumps({
                'application_id': self.get_application_id(),
                'owner': connection.get_unique_name(),
                'object_path': object_path,
                'pid': os.getpid(),
            }, sort_keys=True), flush=True)
        return registered


kiosk_main.Application = PreviewApplication

feedback_transport.SENDING_ENABLED = False
sys.stdin = io.StringIO("TypeError: child panel could not refresh its timer")
raise SystemExit(kiosk_main.main(["--preview", "--child-overlay", "--error-report-stdin"]))
