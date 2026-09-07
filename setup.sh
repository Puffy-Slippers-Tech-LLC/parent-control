#!/usr/bin/env bash
set -euo pipefail

# The only public setup entry point. Modules own implementation; this file owns
# selection, ordering and privileges. Product deployment remains in the package.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'USAGE'
Usage: ./setup.sh [MODE]
  (no mode)             Set up/refresh the development machine and VM host
  --dependencies-only   Install development, build, UI and VM host dependencies
  --test-tools-only     Refresh test helpers, graphical policies and Codex rules
  --codex-rules-only    Refresh machine-wide and checkout Codex rules
  --bootstrap-tools     Install setup authorization once, or refresh its existing grant
  --prepare-host        Prepare/reconcile the existing test VM baseline on the host
  --prepare-vm          Prepare test accounts INSIDE the source VM only
  --install-extension   Install the development extension for the current user
  -h, --help            Show this help

All modes are repeatable. Baseline and guest preparation are explicit operations;
ordinary host setup preserves the VM. See tests/integration/Environment.md.
USAGE
}

if (( $# > 1 )); then
    usage >&2
    exit 2
fi
readonly mode="${1-}"
case "$mode" in
    ''|--dependencies-only|--test-tools-only|--codex-rules-only|--bootstrap-tools|--prepare-host|--prepare-vm|--install-extension) ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

cd -- "$script_dir"
if [[ ! -f Makefile || ! -x child/preview ]]; then
    echo 'setup: run from a complete repository checkout' >&2
    exit 1
fi

run_root() {
    # Routine operations never fall back to generic pkexec authentication.
    if (( EUID == 0 )); then
        shift
        "$@"
    else
        /usr/bin/python3 -IB "$script_dir/tools/setup_privileges.py" "$1"
    fi
}

bootstrap_tools() {
    if (( EUID == 0 )); then
        echo 'setup: [stage:bootstrap-tools] installing authorization as root'
        /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py"
    elif [[ -e "/usr/local/libexec/onpc-setup" || -L "/usr/local/libexec/onpc-setup" ]]; then
        echo 'setup: [stage:bootstrap-tools] reusing installed noninteractive authorization'
        run_root test-tools /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py"
    else
        echo 'setup: [stage:bootstrap-tools] first installation requires administrator authorization'
        pkexec --keep-cwd /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py"
    fi
}

install_codex_rules() {
    echo 'setup: [stage:codex-rules]'
    run_root codex-rules /usr/bin/python3 -IB "$script_dir/tools/install_codex_rules.py" --system
    /usr/bin/python3 -IB "$script_dir/tools/install_codex_rules.py"
    echo 'setup: Codex rules installed; restart Codex with this checkout trusted'
}

install_test_tools() {
    echo 'setup: [stage:test-tools]'
    run_root test-tools /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py"
    echo 'setup: [stage:graphical-host-policies]'
    run_root graphical-policy /usr/bin/python3 -IB "$script_dir/tools/install_graphical_test_policy.py"
    install_codex_rules
}

case "$mode" in
    --codex-rules-only) install_codex_rules ;;
    --test-tools-only) install_test_tools ;;
    --bootstrap-tools)
        bootstrap_tools
        install_codex_rules
        ;;
    --install-extension)
        make --no-print-directory _install-development-extension
        ;;
    --prepare-vm)
        # Guest identity is validated before account changes. Never run host
        # dependency/policy installation or baseline capture in this mode.
        /bin/bash "$script_dir/tests/integration/prepare-vm"
        ;;
    --prepare-host)
        # The controller owns provenance and resumability, preserving accepted
        # baselines and rejecting concurrent or replaced resources.
        echo 'setup: [stage:prepare-host]'
        run_root prepare-host /usr/bin/python3 -B "$script_dir/tests/integration/prepare_host.py"
        # Pin the accepted UUID only after successful baseline reconciliation.
        install_test_tools
        ;;
    ''|--dependencies-only)
        # Establish the grant before installing host dependencies. All later
        # privileged stages reuse it, including repeated bootstrap requests.
        if [[ -z "$mode" && ! -e "/usr/local/libexec/onpc-setup" && ! -L "/usr/local/libexec/onpc-setup" ]]; then
            bootstrap_tools
        fi
        echo 'setup: [stage:dependencies]'
        run_root dependencies /bin/bash "$script_dir/tools/setup_dependencies.sh"
        echo 'setup: [stage:checkout]'
        /bin/bash "$script_dir/tools/setup_checkout.sh"
        if [[ -z "$mode" ]]; then
            install_test_tools
        fi
        ;;
esac
echo 'setup: selected setup completed successfully'
