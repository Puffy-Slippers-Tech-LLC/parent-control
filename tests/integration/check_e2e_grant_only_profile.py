#!/usr/bin/python3
"""Qualify two-minute grant-only time and explicit revoke-first in separate attempts."""

import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for revoke_first in (False, True):
        result = smoke(assets=named_input(), provision_credentials=True,
                       grant_only_profile=True, grant_only_revoke=revoke_first)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
