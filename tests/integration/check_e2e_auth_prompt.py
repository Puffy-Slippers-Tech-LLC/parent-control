#!/usr/bin/python3
"""Qualify REQUEST09/AUTH01 kiosk proofs and refusal matrix without secrets."""
import sys
from check_graphical_smoke import main as smoke
from tools.test_storage import named_input


if __name__ == '__main__':
    sys.exit(smoke(assets=named_input(), provision_credentials=True, mate_prompt=True))
