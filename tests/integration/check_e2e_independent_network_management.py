#!/usr/bin/python3
"""Fixed owned-VM Internet isolation, controller visibility and recovery slice."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 fresh_desktop='parent', independent_network=True)


if __name__ == '__main__':
    sys.exit(main())
