#!/usr/bin/env bash
set -euo pipefail

# Caller-owned checkout configuration; invoke through ../setup.sh after packages.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# != 0 )); then
    echo 'setup-checkout: use ./setup.sh --dependencies-only' >&2
    exit 2
fi

# Keep the public development identity and signing settings local to this checkout.
# The private signing key must be restored separately before signing releases.
git -C "$script_dir" config --local user.name 'Puffy Slippers Tech LLC'
git -C "$script_dir" config --local user.email 'dev@tech.puffyslippers.com'
git -C "$script_dir" config --local gpg.format openpgp
git -C "$script_dir" config --local user.signingkey '4449F02C3E57F8215261A57958109B593907EFDE'
echo 'setup: configured checkout-local Git identity and OpenPGP signing key'

ui_venv="$script_dir/.venv/onpc-ui-tests"
/usr/bin/python3 -m venv --system-site-packages "$ui_venv"
"$ui_venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
    --require-hashes -r "$script_dir/tests/ui/requirements.txt"
