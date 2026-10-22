#!/usr/bin/python3
"""Qualify Ubuntu installed E2E preparation, stopping before worker input."""
import argparse
import json
import sys
from fixture_e2e_qualification import main
from tools.test_storage import named_input

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--fixture-selection', required=True)
    parser.add_argument('--fixture-source-selection', required=True)
    arguments = parser.parse_args()
    sys.exit(main(assets=named_input(vm_source=True, fixture_source=True),
                  selection=json.loads(arguments.fixture_selection),
                  source_selection=json.loads(arguments.fixture_source_selection)))
