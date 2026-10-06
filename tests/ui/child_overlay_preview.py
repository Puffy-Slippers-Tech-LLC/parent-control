"""Launch the child-overlay preview under the hermetic GTK test session."""

from kiosk.oh_no_parent_control_kiosk.main import main
from tests.support.application_ui_diagnostics import enable_provider_diagnostics


enable_provider_diagnostics()
raise SystemExit(main(["--preview", "--child-overlay"]))
