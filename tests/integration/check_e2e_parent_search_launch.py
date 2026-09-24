#!/usr/bin/python3
"""Qualify administrator Parent launch through its installed search entry."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

from tools.test_storage import named_input
ASSETS = named_input()


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 parent_search_launch=True)


if __name__ == '__main__':
    sys.exit(main())
