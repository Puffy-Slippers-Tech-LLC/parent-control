#!/usr/bin/python3
"""Two independent Shell approval requests, each cancelled without a secret."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


def main():
    for _ in range(2):
        result = smoke(assets=named_input(package_source=True), provision_credentials=True,
                       challenges=True, challenge_profile='overlay-prompt')
        if result:
            return result
    return 0


if __name__ == '__main__':
    sys.exit(main())
