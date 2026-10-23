#!/usr/bin/python3
"""Qualify recorded serial preparation before any worker or serial input."""
import argparse
import json
import sys

from fixture_recorded_serial_qualification import main
from tools.test_storage import named_input


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--fixture-selection', required=True)
    arguments = parser.parse_args()
    sys.exit(main(assets=named_input(vm_source=True, fixture_source=True),
                  selection=json.loads(arguments.fixture_selection)))
