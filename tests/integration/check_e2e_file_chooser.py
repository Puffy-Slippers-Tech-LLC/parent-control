#!/usr/bin/python3
"""Qualify installed feedback chooser Open and Cancel without sending."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, file_chooser=True)


if __name__ == '__main__':
    sys.exit(main())
