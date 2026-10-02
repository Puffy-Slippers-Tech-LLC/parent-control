#!/usr/bin/python3
"""Qualify overlay Help/About information and unchanged form without following links."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='overlay-information')


if __name__ == '__main__':
    sys.exit(main())
