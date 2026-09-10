#!/usr/bin/python3
"""Guarded VT6 fixture challenge inspection; no password input or provisioning."""

import sys
from check_graphical_smoke import main

if __name__ == '__main__':
    sys.exit(main(vt6_prompt=True))
