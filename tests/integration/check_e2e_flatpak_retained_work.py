#!/usr/bin/python3
"""Qualify independent Flatpak work through command denial and captured closure."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(vm_source=True, fixture_source=True),
                   provision_credentials=True, flatpak_retained_work=True, fixture_profile='flatpak'))
