#!/usr/bin/python3
"""Qualify Ubuntu/Fedora product-free E2E preparation before customer or worker input."""
import argparse
import json
import sys
from fixture_e2e_product_free_qualification import main
from tools.test_storage import named_input

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--fixture-selection', required=True)
    parser.add_argument('--fixture-source-selection', required=True)
    arguments = parser.parse_args()
    sys.exit(main(assets=named_input(upgrade_source=True, vm_source=True, fixture_source=True),
                  selection=json.loads(arguments.fixture_selection),
                  source_selection=json.loads(arguments.fixture_source_selection)))
