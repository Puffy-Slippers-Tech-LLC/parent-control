#!/usr/bin/python3
"""Qualify public desktop selection and actual station launch, without product edits."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(package_source=True), provision_credentials=True,
                 kiosk_entry='public-desktop-selection')


if __name__ == '__main__':
    sys.exit(main())
