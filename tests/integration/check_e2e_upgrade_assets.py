#!/usr/bin/env python3
"""300c: genuine v1.2/current FIX04 transfer, without product installation."""
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(upgrade_source=True), provision_credentials=True,
                 upgrade_assets=True)


if __name__ == '__main__':
    raise SystemExit(main())
