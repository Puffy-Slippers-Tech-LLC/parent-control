#!/usr/bin/python3
"""300b: qualify one guarded AccountsService desktop-language setting."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, desktop_language=True)


if __name__ == '__main__':
    sys.exit(main())
