#!/usr/bin/python3
"""Close the station under real pending approval and reopen unchanged choices."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(package_source=True), provision_credentials=True,
                   challenges=True, challenge_profile='pending-station-close'))
