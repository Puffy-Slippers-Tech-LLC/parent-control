#!/usr/bin/python3
"""Verify that a repeated product fault fails after its allowance ends."""
import sys

from product_fault_qualification import main
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(main(named_input(package_source=True), 'expired-allowance'))
