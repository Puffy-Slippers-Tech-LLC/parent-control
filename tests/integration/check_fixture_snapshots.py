#!/usr/bin/python3
"""Engineering qualification of Ubuntu's fixture-independent saved captures."""
import sys

from fixture_snapshot_qualification import main
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(main(assets=named_input(vm_source=True, fixture_source=True)))
