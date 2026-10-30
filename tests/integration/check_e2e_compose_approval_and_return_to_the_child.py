#!/usr/bin/python3
"""FLOW20: independent new Riley/Jamie and open Jordan/Casey overlay approvals."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    # Each binding gets a fresh restored attempt. Retain the affected fixed
    # English and translated approval branches as product regressions.
    for profile in ('approval-return-new', 'approval-return-open',
                    'overlay-approved-exit', 'overlay-translated-approval'):
        result = smoke(assets=named_input(fixture_source=True), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
