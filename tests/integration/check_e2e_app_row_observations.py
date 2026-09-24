#!/usr/bin/python3
"""Qualify complete public App Limits row reads on the installed VM."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input()

if __name__ == '__main__':
    sys.exit(smoke(assets=ASSETS, provision_credentials=True, app_row_observations=True))
