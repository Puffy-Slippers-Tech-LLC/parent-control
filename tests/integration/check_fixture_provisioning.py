#!/usr/bin/python3
"""Engineering qualification of Ubuntu/Fedora attempt-owned fixture provisioning."""
import argparse
import json
import sys

from fixture_provision_qualification import main
from tools.test_storage import named_input


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--fixture-selection', required=True)
    arguments = parser.parse_args()
    sys.exit(main(assets=named_input(vm_source=True, fixture_source=True),
                  selection=json.loads(arguments.fixture_selection)))
