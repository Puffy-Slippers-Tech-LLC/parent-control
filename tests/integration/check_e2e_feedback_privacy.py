#!/usr/bin/python3
"""Qualify Privacy and dialog draft persistence without submitting feedback."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, feedback_privacy=True)


if __name__ == '__main__':
    sys.exit(main())
