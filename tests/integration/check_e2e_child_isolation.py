#!/usr/bin/python3
"""Qualify healthy and restored requests through one unavailable child home."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 confinement_usability='child-isolation')


if __name__ == '__main__':
    sys.exit(main())
