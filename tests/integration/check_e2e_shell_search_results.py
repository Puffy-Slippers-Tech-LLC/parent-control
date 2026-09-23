#!/usr/bin/python3
"""Qualify the fixed product query and launcher on a fresh installed desktop."""

from pathlib import Path
import sys
from check_graphical_smoke import main as smoke

ASSETS = Path('/tmp/onpc-parent-setup-input')


def main():
    return smoke(assets=ASSETS, provision_credentials=True,
                 shell_search_results=True)


if __name__ == '__main__':
    sys.exit(main())
