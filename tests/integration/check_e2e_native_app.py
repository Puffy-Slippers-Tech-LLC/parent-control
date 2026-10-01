#!/usr/bin/python3
"""Qualify guarded native command launch and normal public app input/effect."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 native_app=True)


if __name__ == '__main__':
    sys.exit(main())
