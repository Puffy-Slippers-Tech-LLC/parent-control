#!/usr/bin/python3
"""137: real extension update, normal child renewal and saved settings."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(session_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, activation_session=True)


if __name__ == '__main__':
    sys.exit(main())
