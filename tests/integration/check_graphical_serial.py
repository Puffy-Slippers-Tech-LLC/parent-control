#!/usr/bin/python3
"""Guarded real fixture serial authentication and fixed harmless command."""

import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(provision_credentials=True, serial=True))
