#!/usr/bin/python3
"""Qualify Jordan's daily access, retained Parent window and countdown bindings."""
import sys

from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(vm_source=True), provision_credentials=True,
                 challenges=True, challenge_profile='jordan-daily-access')


if __name__ == '__main__':
    sys.exit(main())
