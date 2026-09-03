"""Launch the kiosk preview under the hermetic GTK test session."""

from kiosk.oh_no_parent_control_kiosk.main import main


raise SystemExit(main(["--preview"]))
