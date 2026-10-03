#!/usr/bin/python3
"""300a: qualify Chinese readiness without installing or configuring the product."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True,
                 chinese_language_assets=True)


if __name__ == '__main__':
    sys.exit(main())
