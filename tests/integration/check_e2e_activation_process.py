#!/usr/bin/python3
"""135: a process-only update keeps the parent's child settings usable."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input

ASSETS = named_input(process_source=True)


def main():
    return smoke(assets=ASSETS, provision_credentials=True, activation_process=True)


if __name__ == '__main__':
    sys.exit(main())
