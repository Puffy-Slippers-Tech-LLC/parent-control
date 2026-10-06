"""Run the real kiosk notification provider on the fixture's private bus/display."""
from kiosk.oh_no_parent_control_kiosk.notifications import NotificationApplication

raise SystemExit(NotificationApplication().run(None))
