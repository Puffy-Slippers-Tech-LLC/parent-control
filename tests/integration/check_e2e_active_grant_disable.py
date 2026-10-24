#!/usr/bin/python3
"""Finite installed active-grant disable qualification; no complete-case credit."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    assets = named_input(package_source=True, fixture_source=True)
    engineering = smoke(assets=assets, provision_credentials=True,
                        active_grant_disable='engineering')
    if engineering != 0:
        return engineering
    return smoke(assets=assets, provision_credentials=True, active_grant_disable='public')


if __name__ == '__main__':
    sys.exit(main())
