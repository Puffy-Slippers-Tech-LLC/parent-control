#!/usr/bin/env bash
# Shared host selection for setup.sh and its privileged package module.
# Read the actual execution environment; never install host packages from a
# Flatpak runtime or infer a distribution from a stray package-manager binary.
. '/etc/os-release'
case "${ID-}" in
    ubuntu|debian) readonly setup_platform=debian ;;
    fedora)
        if [[ ${VERSION_ID-} != 44 ]]; then
            echo 'setup: Fedora Workstation 44 is required by the native RPM builder' >&2
            exit 1
        fi
        readonly setup_platform=fedora
        ;;
    *)
        echo "setup: unsupported development environment: ${PRETTY_NAME:-${ID:-unknown}}; run setup on Ubuntu or Fedora Workstation 44" >&2
        exit 1
        ;;
esac
