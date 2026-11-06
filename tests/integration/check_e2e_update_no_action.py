#!/usr/bin/python3
"""135a: a real version-only update preserves the parent's open child settings."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(no_action_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, update_no_action=True)


if __name__ == '__main__':
    sys.exit(main())
