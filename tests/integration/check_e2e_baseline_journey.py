#!/usr/bin/python3
"""Qualify one complete ordered baseline history on an installed target."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True, fixture_source=True),
                 provision_credentials=True, baseline_journey=True)


if __name__ == '__main__':
    sys.exit(main())
