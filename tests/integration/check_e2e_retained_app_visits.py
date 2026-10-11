#!/usr/bin/python3
"""Qualify FLOW09/FLOW14 distinct-user original-window retention."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True, fixture_source=True),
                 provision_credentials=True, retained_app_visits=True)


if __name__ == '__main__':
    sys.exit(main())
