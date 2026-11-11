#!/usr/bin/env bash
set -euo pipefail

# The only public setup entry point. Modules own implementation; this file owns
# selection, ordering and privileges. Product deployment remains in the package.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat <<'USAGE'
Usage: ./setup.sh [MODE] [--vm NAME]
  (no mode)             Set up/refresh an Ubuntu or Fedora 44/45 development machine (no VMs needed)
  --server              Set up an Ubuntu 26.04+ SSH automation server; disable sleep
                       No VM hosting or Codex CLI installation
  --connect-server      Verify SSH access to all configured servers and install Watch for local checkouts
  --dependencies-only   Install development, build and UI/GUI-fixture dependencies
  --vm-host-only        Add VM host dependencies and refresh development helpers/policies
  --ppa-build-tools     Install clean local PPA build prerequisites
  --rpm-build-tools     Install RPM tools and prepare configured Fedora target builders
  --test-tools-only     Refresh test helpers/policies/rules, viewer icon and old bytecode ownership
                       Includes guarded root guest commands through tools/test-vm exec
  --ui-tests-only       Prepare this checkout's UI test environment using installed host packages
  --watch               Install/update only the ONPC Watch VS Code editor extension
  --bootstrap-tools     Install setup authorization once, or refresh its existing grant
  --replace-missing-baseline  Replace an explicitly deleted baseline from a prepared, off VM
                             Requires --vm NAME or ID from config/environment.json
  --install-extension   Install the development extension for the current user
  -h, --help            Show this help

All modes are repeatable. Ordinary host setup preserves the VM. Explicit baseline
replacement is tools/prepare-vm. See tests/integration/Environment.md.
USAGE
}

if (( $# > 1 )) && [[ ${1-} != --replace-missing-baseline || $# != 3 || ${2-} != --vm || -z ${3-} ]]; then
    usage >&2
    exit 2
fi
readonly mode="${1-}"
readonly vm_name="${3-}"
case "$mode" in
    ''|--server|--connect-server|--dependencies-only|--vm-host-only|--ppa-build-tools|--rpm-build-tools|--test-tools-only|--ui-tests-only|--watch|--bootstrap-tools|--replace-missing-baseline|--install-extension) ;;
    -h|--help) usage; exit 0 ;;
    *) usage >&2; exit 2 ;;
esac

cd -- "$script_dir"
# Guest checkouts can live on noexec shared mounts. Check completeness without
# requiring execution of a launcher that guest preparation does not use.
if [[ ! -f Makefile || ! -f child/preview ]]; then
    echo 'setup: run from a complete repository checkout' >&2
    exit 1
fi
source "$script_dir/tools/setup_platform.sh"

if [[ $mode == --server ]]; then
    require_headless_platform
    if (( EUID == 0 )); then
        echo 'setup: run --server as the checkout-owning administrator, without sudo; setup requests sudo only for initial bootstrap' >&2
        exit 1
    fi
fi

if [[ $mode == --ppa-build-tools && $setup_platform == fedora ]]; then
    echo 'setup: PPA build tools require an Ubuntu/Debian host; use --rpm-build-tools on Fedora' >&2
    exit 2
fi

prepare_rpm_builder() {
    /usr/bin/python3 -B "$script_dir/tools/rpm_builder.py"
}

prepare_package_builders() {
    /usr/bin/python3 -B "$script_dir/tools/deb_builder.py"
    prepare_rpm_builder
}

run_root() {
    # Routine operations never fall back to generic pkexec authentication.
    if (( EUID == 0 )); then
        shift
        "$@"
    else
        if [[ $1 == replace-missing-baseline ]]; then
            /usr/bin/python3 -IB "$script_dir/tools/setup_privileges.py" "$1" --vm "$vm_name"
        else
            /usr/bin/python3 -IB "$script_dir/tools/setup_privileges.py" "$1"
        fi
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

install_agent_rules() {
    echo 'setup: [stage:codex-rules]'
    run_root codex-rules /usr/bin/python3 -IB "$script_dir/tools/install_codex_rules.py" --system
    if [[ $mode == --server ]]; then
        /usr/bin/python3 -IB "$script_dir/tools/agent_adapter.py" --setup --headless
    else
        /usr/bin/python3 -IB "$script_dir/tools/agent_adapter.py" --setup
    fi
}

install_test_tools() {
    echo 'setup: [stage:test-tools]'
    run_root test-tools /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py"
    echo 'setup: [stage:graphical-host-policies]'
    run_root graphical-policy /usr/bin/python3 -IB "$script_dir/tools/install_graphical_test_policy.py"
    install_agent_rules
    install_watch_extension --if-available
}

install_watch_extension() {
    echo 'setup: [stage:watch-extension]'
    /usr/bin/python3 -B "$script_dir/tools/install_watch_extension.py" "$@"
}

case "$mode" in
    --connect-server)
        /usr/bin/python3 -IB "$script_dir/tools/setup_server_connection.py"
        install_watch_extension
        ;;
    --server)
        # Internal headless operation names/arguments remain stable so existing
        # installed dispatchers can refresh through their original grant.
        # Opt-in authorization is established before routine privileged stages.
        # An existing grant must succeed; never retry authentication on denial.
        if [[ -e '/usr/local/libexec/onpc-headless-account' || -L '/usr/local/libexec/onpc-headless-account' ]]; then
            run_root headless-tools /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py" --headless
        else
            echo 'setup: [stage:headless-bootstrap] administrator authorization required once for this automation account'
            sudo -- /usr/bin/python3 -IB "$script_dir/tools/install_test_runner.py" --headless
        fi
        echo 'setup: [stage:dependencies]'
        run_root headless-dependencies /bin/bash "$script_dir/tools/setup_dependencies.sh" --headless
        prepare_package_builders
        echo 'setup: [stage:checkout]'
        /bin/bash "$script_dir/tools/setup_checkout.sh" --headless
        # Do not run the VM-host AppArmor policy installer or desktop extension.
        install_agent_rules
        echo 'setup: headless SSH environment installed; client keys, Git credentials, coding CLI and VM hosting are managed separately'
        ;;
    --watch) install_watch_extension ;;
    --ui-tests-only)
        /bin/bash "$script_dir/tools/setup_checkout.sh" --ui-tests-only
        ;;
    --ppa-build-tools)
        echo 'setup: [stage:ppa-build-tools]'
        run_root ppa-build-tools /bin/bash "$script_dir/tools/setup_dependencies.sh" --ppa-build-tools
        ;;
    --rpm-build-tools)
        echo 'setup: [stage:rpm-build-tools]'
        run_root rpm-build-tools /bin/bash "$script_dir/tools/setup_dependencies.sh" --rpm-build-tools
        prepare_rpm_builder
        ;;
    --vm-host-only)
        run_root vm-host /bin/bash "$script_dir/tools/setup_dependencies.sh" --vm-host-only
        install_test_tools
        ;;
    --test-tools-only) install_test_tools ;;
    --bootstrap-tools)
        bootstrap_tools
        install_agent_rules
        ;;
    --install-extension)
        make --no-print-directory _install-development-extension
        ;;
    --replace-missing-baseline)
        if [[ -z $vm_name ]]; then
            usage >&2
            exit 2
        fi
        # Validate before privilege dispatch, tools refresh or any VM access.
        /usr/bin/python3 -B "$script_dir/tests/integration/test_account_password.py"
        # Explicit recovery recaptures a deleted baseline without restoring it.
        # The controller rejects running, concurrent or replaced resources.
        echo 'setup: [stage:prepare-vm]'
        run_root replace-missing-baseline /usr/bin/python3 -B "$script_dir/tests/integration/prepare_baseline.py" --replace-missing --vm "$vm_name"
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
        prepare_package_builders
        echo 'setup: [stage:checkout]'
        /bin/bash "$script_dir/tools/setup_checkout.sh"
        if [[ -z "$mode" ]]; then
            install_test_tools
        fi
        ;;
esac
case "$mode" in
    ''|--server|--dependencies-only|--vm-host-only|--test-tools-only|--bootstrap-tools)
        /usr/bin/python3 -IB "$script_dir/tools/agent_adapter.py" --readiness
        ;;
esac
echo 'setup: selected setup completed successfully'
