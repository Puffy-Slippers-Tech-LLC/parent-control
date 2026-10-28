#!/usr/bin/python3
"""Qualify one broker outage, safe kiosk exit and fresh genuine approval."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True), provision_credentials=True,
                   confinement_usability='service-recovery'))
