#!/usr/bin/python3
"""Qualify edit-only feedback validation/Send observations, without sending."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, feedback_states=True)


if __name__ == '__main__':
    sys.exit(main())
