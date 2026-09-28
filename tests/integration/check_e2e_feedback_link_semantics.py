#!/usr/bin/python3
"""Qualify linked inline semantics without submitting or navigating."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    return smoke(assets=named_input(), provision_credentials=True, feedback_link_semantics=True)


if __name__ == '__main__':
    sys.exit(main())
