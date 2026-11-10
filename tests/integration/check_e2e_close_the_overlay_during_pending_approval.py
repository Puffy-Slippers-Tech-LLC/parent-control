#!/usr/bin/python3
"""Close a real pending overlay approval and reopen the unchanged child request."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='pending-overlay-close')


if __name__ == '__main__':
    sys.exit(main())
