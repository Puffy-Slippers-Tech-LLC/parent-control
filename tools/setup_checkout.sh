#!/usr/bin/env bash
set -euo pipefail

# Caller-owned checkout configuration; invoke through ../setup.sh after packages.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ui-tests-only' && "$1" != '--headless' ]]; }; then
    echo 'setup-checkout: invoke through ./setup.sh' >&2
    exit 2
fi

if [[ ${1-} == --headless ]]; then
    echo 'setup: remote connection details:'
    printf '  Account: %s\n' "$(id -un)"
    printf '  Hostname: %s\n' "$(hostname)"
    printf '  Addresses: %s\n' "$(hostname -I)"
    printf '  Checkout: %s\n' "$script_dir"
    echo 'setup: next: verify the host key, install your client public key with ssh-copy-id, and verify BatchMode SSH access'
    echo 'setup: on the client, configure an SSH alias and ONPC Watch SSH source using the checkout path above'
    echo 'setup: use a router DHCP reservation for a stable Wi-Fi address; keep the server on external power'
    if ! command -v codex >/dev/null 2>&1; then
        echo 'setup: action needed: install the Codex CLI for this account before using tools/fix-tests'
    else
        echo 'setup: action needed: verify Codex CLI login for this account before using tools/fix-tests'
    fi
fi

# Identity, signing keys and credentials are provisioned separately on every host.

ui_venv="$script_dir/.venv/onpc-ui-tests"
/usr/bin/python3 -m venv --system-site-packages "$ui_venv"
"$ui_venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
    --require-hashes -r "$script_dir/tests/ui/requirements.txt"

if [[ ${1-} != --ui-tests-only ]]; then
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
