#!/usr/bin/python3
"""Qualify existing-window activation and unchanged public feedback draft."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, window_switch=True)


if __name__ == '__main__':
    sys.exit(main())
