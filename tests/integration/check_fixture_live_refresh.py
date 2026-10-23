#!/usr/bin/python3
"""Qualify idle maintenance A/use, host edit/build B, sync/use and owned recovery."""
import argparse
import json
import sys

from fixture_live_refresh_qualification import main


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--fixture-refresh-phase', required=True, choices=('retain-a', 'replace-b'))
    parser.add_argument('--fixture-selection', required=True)
    parser.add_argument('--fixture-source-selection', required=True)
    parser.add_argument('--fixture-replacement-selection')
    arguments = parser.parse_args()
    sys.exit(main(phase=arguments.fixture_refresh_phase,
        selection=json.loads(arguments.fixture_selection),
        source_selection=json.loads(arguments.fixture_source_selection),
        replacement_selection=(None if arguments.fixture_replacement_selection is None else
                               json.loads(arguments.fixture_replacement_selection))))
