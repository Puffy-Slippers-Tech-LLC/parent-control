#!/usr/bin/python3
"""Qualify read-only ordinary feedback entry and synthetic observations."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, feedback_read=True)


if __name__ == '__main__':
    sys.exit(main())
