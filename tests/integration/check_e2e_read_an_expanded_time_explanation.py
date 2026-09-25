#!/usr/bin/python3
"""Qualify PARENT20 through the guarded installed VM envelope."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, time_explanation=True)


if __name__ == '__main__':
    sys.exit(main())
