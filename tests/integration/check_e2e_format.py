#!/usr/bin/python3
"""Qualify installed bold formatting through independent public Text runs."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, format_qualification=True)


if __name__ == '__main__':
    sys.exit(main())
