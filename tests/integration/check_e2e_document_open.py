#!/usr/bin/python3
"""Qualify guarded reads of declared synthetic text in the installed VM."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 fresh_desktop='parent', document_open=True)


if __name__ == '__main__':
    sys.exit(main())
