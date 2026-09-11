#!/usr/bin/python3
"""Guarded one-shot VT6 authentication and nonsecret command qualification."""

import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(provision_credentials=True, vt6_auth=True))
