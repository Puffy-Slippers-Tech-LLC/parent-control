#!/usr/bin/python3
"""TIME01 presence and limits-off absence in separate guarded live attempts."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for profile in ('countdown-enabled', 'countdown-off'):
        result = smoke(assets=named_input(), provision_credentials=True,
                       challenges=True, challenge_profile=profile)
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
