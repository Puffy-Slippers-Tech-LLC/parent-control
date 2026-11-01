#!/usr/bin/env bash
set -euo pipefail

# Caller-owned checkout configuration; invoke through ../setup.sh after packages.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ui-tests-only' && "$1" != '--headless' ]]; }; then
    echo 'setup-checkout: invoke through ./setup.sh' >&2
    exit 2
fi

# Keep the public development identity and signing settings local to this checkout.
# The private signing key must be restored separately before signing releases.
if [[ -z ${1-} ]]; then
    git -C "$script_dir" config --local user.name 'Puffy Slippers Tech LLC'
    git -C "$script_dir" config --local user.email 'dev@tech.puffyslippers.com'
    git -C "$script_dir" config --local gpg.format openpgp
    git -C "$script_dir" config --local user.signingkey '4449F02C3E57F8215261A57958109B593907EFDE'
    echo 'setup: configured checkout-local Git identity and OpenPGP signing key'
fi

ui_venv="$script_dir/.venv/onpc-ui-tests"
/usr/bin/python3 -m venv --system-site-packages "$ui_venv"
"$ui_venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
    --require-hashes -r "$script_dir/tests/ui/requirements.txt"

if [[ ${1-} == --headless ]]; then
    # Inspect only: automation must not replace identity, signing or credentials.
    if ! git -C "$script_dir" var GIT_AUTHOR_IDENT >/dev/null 2>&1 ||
       ! git -C "$script_dir" var GIT_COMMITTER_IDENT >/dev/null 2>&1; then
        echo 'setup: action needed: configure Git user.name and user.email for the automation account'
    fi
    if ! git -C "$script_dir" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
        echo 'setup: action needed: configure the automation branch upstream before launcher commit/push operations'
    fi
    echo 'setup: Git identity/signing settings and credentials preserved; remote authentication and push access are not tested'
fi
