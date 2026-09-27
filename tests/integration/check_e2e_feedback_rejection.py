#!/usr/bin/python3
"""Qualify public invalid-only feedback rejection without a valid submission."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, feedback_rejection=True)


if __name__ == '__main__':
    sys.exit(main())
