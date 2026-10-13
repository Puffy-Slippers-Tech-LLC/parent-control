#!/usr/bin/python3
"""Engineering fault/recovery qualification; never a customer case."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(package_source=True)

if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True,
                   kiosk_eligible_choices=True, kiosk_feedback_confinement=True))
