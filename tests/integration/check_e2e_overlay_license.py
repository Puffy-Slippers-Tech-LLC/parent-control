#!/usr/bin/python3
"""Qualify overlay About/license without following external links."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='overlay-license')


if __name__ == '__main__':
    sys.exit(main())
