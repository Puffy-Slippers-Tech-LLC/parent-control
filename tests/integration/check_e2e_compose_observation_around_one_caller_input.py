#!/usr/bin/python3
"""Qualify UI22 around one invalidating caller edit, without submission."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, compose_observation=True)


if __name__ == '__main__':
    sys.exit(main())
