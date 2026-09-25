#!/usr/bin/python3
"""Qualify bounded nonsecret text replacement in installed Parent feedback."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, text_qualification=True)


if __name__ == '__main__':
    sys.exit(main())
