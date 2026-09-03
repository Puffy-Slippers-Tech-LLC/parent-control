#!/usr/bin/env bash
set -euo pipefail

# Installs only the tools needed to develop and preview this checkout.  Product
# deployment, account provisioning, and system-service configuration remain the
# responsibility of install.sh.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly apt_lock_timeout_seconds=300

usage() {
    echo "Usage: ./setup.sh"
}

if (( $# > 1 )); then
    usage >&2
    exit 2
fi
case "${1-}" in
    "") ;;
    -h|--help)
        usage
        exit 0
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

if [[ ! -f "$script_dir/Makefile" || ! -x "$script_dir/child/preview" ]]; then
    echo "setup: run this script from a complete repository checkout" >&2
    exit 1
fi

if ! command -v apt-get >/dev/null; then
    echo "setup: Ubuntu/Debian with apt-get is required" >&2
    exit 1
fi

if (( EUID == 0 )); then
    apt_get=(apt-get -o "DPkg::Lock::Timeout=$apt_lock_timeout_seconds")
else
    command -v sudo >/dev/null || {
        echo "setup: sudo is required to install development dependencies" >&2
        exit 1
    }
    apt_get=(sudo apt-get -o "DPkg::Lock::Timeout=$apt_lock_timeout_seconds")
fi

"${apt_get[@]}" update
"${apt_get[@]}" install -y software-properties-common
add_repository=(add-apt-repository -y universe)
if (( EUID != 0 )); then
    add_repository=(sudo "${add_repository[@]}")
fi
"${add_repository[@]}"
"${apt_get[@]}" update
"${apt_get[@]}" install -y \
    dbus-user-session \
    gir1.2-adw-1 \
    gir1.2-gtk-4.0 \
    gnome-shell \
    libpam0g-dev=1.7.0-5ubuntu3.2 \
    libglib2.0-bin \
    make \
    mutter-dev-bin \
    nodejs \
    python3 \
    python3-dbusmock=0.38.1-1 \
    python3-gi \
    python3-gi-cairo \
    python3-hypothesis=6.151.5-1 \
    python3-pytest=9.0.2-4

echo "Development dependencies installed. Run: make check"
