#!/usr/bin/python3
"""Guarded fixture provisioning and real GDM authentication qualification.

The existing owner restores the accepted baseline before and after the entire
attempt. This is runner qualification, not a complete customer scenario.
"""

import sys

from check_graphical_smoke import main


if __name__ == '__main__':
    sys.exit(main(provision_credentials=True))
