#!/usr/bin/python3
"""Installed active-grant disable engineering assertions outside customer E2E."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    assets = named_input(package_source=True, fixture_source=True)
    return smoke(assets=assets, provision_credentials=True,
                 active_grant_disable='engineering')


if __name__ == '__main__':
    sys.exit(main())
