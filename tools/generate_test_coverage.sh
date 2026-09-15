#!/bin/sh
# Regenerate the test inventory document using local test collectors only.
set -eu
exec /usr/bin/python3 -IB "$(dirname -- "$0")/generate_test_coverage.py" "$@"
