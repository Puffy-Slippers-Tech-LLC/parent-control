#!/usr/bin/env bash
set -euo pipefail

# Caller-owned checkout configuration; invoke through ../setup.sh after packages.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ui-tests-only' && "$1" != '--headless' ]]; }; then
    echo 'setup-checkout: invoke through ./setup.sh' >&2
    exit 2
fi

# Server setup supplies missing checkout-local identity; keys and credentials
# are provisioned separately on every host.

ui_venv="$script_dir/.venv/onpc-ui-tests"
/usr/bin/python3 -m venv --system-site-packages "$ui_venv"
"$ui_venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
    --require-hashes -r "$script_dir/tests/ui/requirements.txt"

if [[ ${1-} != --ui-tests-only ]]; then
    if [[ ${1-} == --headless ]]; then
        # Preserve effective values, including account-wide and worktree settings.
        # Local defaults are shared by this clone's linked worktrees, without
        # changing the automation account's identity for unrelated repositories.
        if [[ -z $(git -C "$script_dir" config --get user.name) ]]; then
            git -C "$script_dir" config --local user.name 'Puffy Slippers Tech LLC'
            echo 'setup: configured checkout-local Git user.name: Puffy Slippers Tech LLC'
        fi
        if [[ -z $(git -C "$script_dir" config --get user.email) ]]; then
            git -C "$script_dir" config --local user.email 'dev@tech.puffyslippers.com'
            echo 'setup: configured checkout-local Git user.email: dev@tech.puffyslippers.com'
        fi
    fi
    if ! git -C "$script_dir" var GIT_AUTHOR_IDENT >/dev/null 2>&1 ||
       ! git -C "$script_dir" var GIT_COMMITTER_IDENT >/dev/null 2>&1; then
        echo 'setup: action needed: configure Git user.name and user.email for the automation account'
    fi
    if ! git -C "$script_dir" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' >/dev/null 2>&1; then
        echo 'setup: action needed: configure the automation branch upstream before launcher commit/push operations'
    fi
    echo 'setup: existing Git identity, signing settings and credentials preserved; push access is not tested'
    if [[ ${1-} != --headless ]]; then
        echo 'setup: remote Git authentication is not tested in this mode'
    fi
fi

if [[ ${1-} == --headless ]]; then
    echo 'setup: server connection summary (keep this output for client onboarding; do not commit it):'
    printf '  Account: %s\n' "$(id -un)"
    printf '  Hostname: %s\n' "$(hostname)"
    printf '  Addresses: %s\n' "$(hostname -I)"
    printf '  Checkout: %s\n' "$script_dir"
    echo 'setup: public SSH host-key fingerprints (compare with the client SSH prompt):'
    for host_key in /etc/ssh/ssh_host_*_key.pub; do
        [[ -f "$host_key" ]] || continue
        ssh-keygen -lf "$host_key"
    done
    echo 'setup: registered Git worktrees (Watch discovers these from the starting checkout):'
    git -C "$script_dir" worktree list
    # Read-only and bounded: never prompt, accept a new Git host key, or push.
    if timeout 20s env GIT_TERMINAL_PROMPT=0 GIT_ASKPASS=/bin/false GCM_INTERACTIVE=Never \
        GIT_SSH_COMMAND='ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=10' \
        git -C "$script_dir" ls-remote >/dev/null 2>&1; then
        echo 'setup: Git remote read access verified; push permissions must be configured separately'
    else
        echo 'setup: action needed: configure Git remote read access for this account, then rerun ./setup.sh --server'
    fi
    echo 'setup: next: on the client, run ./setup.sh --connect-server using this summary'
    echo 'setup: the client reads host names, SSH ports and checkout paths from config/environment.json; addresses and usernames stay private'
    echo 'setup: use a router DHCP reservation for a stable Wi-Fi address; keep the server on external power'
fi
