#!/usr/bin/python3
"""Qualify each FLOW07 branch in its own restored, owned VM attempt."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for outcome in ('rejection', 'cancel'):
        result = smoke(assets=named_input(), provision_credentials=True, approval_flow=outcome)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
