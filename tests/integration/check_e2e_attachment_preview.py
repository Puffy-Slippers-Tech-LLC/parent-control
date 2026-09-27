#!/usr/bin/python3
"""Qualify public attachment preview applicability; never Send."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, attachment_preview=True)


if __name__ == '__main__':
    sys.exit(main())
