#!/usr/bin/python3
"""Guarded fixture provisioning/staging qualification; no password entry yet.

The existing owner restores the accepted baseline before and after the entire
attempt. This is runner qualification, never customer authentication evidence.
"""

import sys

from check_graphical_smoke import main


if __name__ == '__main__':
    sys.exit(main(provision_credentials=True))
