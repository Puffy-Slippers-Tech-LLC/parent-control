#!/usr/bin/env bash
set -euo pipefail

# Dependency and checkout configuration module; invoke through ../setup.sh.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly apt_lock_timeout_seconds=300
if (( $# != 0 )); then
    echo 'setup-dependencies: use ./setup.sh --dependencies-only' >&2
    exit 2
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
    7zip \
    apparmor \
    strace=6.19+ds-0ubuntu5 \
    build-essential \
    at-spi2-core=2.60.4-0ubuntu0.1 \
    dbus-daemon=1.16.2-2ubuntu4 \
    dbus-user-session \
    debhelper \
    devscripts \
    dpkg-dev \
    dh-python \
    dput \
    flatpak=1.16.6-1 \
    git \
    gnome-ponytail-daemon=0.0.11-1build1 \
    gnupg \
    gir1.2-adw-1 \
    gir1.2-gtk-4.0 \
    gir1.2-webkit-6.0 \
    gnome-shell=50.1-0ubuntu1.2 \
    inotify-tools=4.25.9.0-1 \
    gjs=1.88.0-1 \
    libpam0g-dev=1.7.0-5ubuntu3.2 \
    libglib2.0-bin \
    libvirt-daemon-system \
    qemu-system-x86 \
    virtiofsd \
    libvirt-clients=12.0.0-1ubuntu5.3 \
    libguestfs-tools=1:1.58.1-3ubuntu3 \
    lintian \
    make \
    mutter=50.1-0ubuntu2.2 \
    mutter-dev-bin=50.1-0ubuntu2.2 \
    nodejs=22.22.1+dfsg+~cs22.19.15-1ubuntu1 \
    openssh-client=1:10.2p1-2ubuntu3.6 \
    pipewire=1.6.2-1ubuntu1.1 \
    python3 \
    python3-dbusmock=0.38.1-1 \
    python3-gi \
    python3-gi-cairo \
    python3-hypothesis=6.151.5-1 \
    python3-libvirt=12.0.0-1build1 \
    python3-guestfs=1:1.58.1-3ubuntu3 \
    python3-pytest=9.0.2-4 \
    python3-pytest-cov \
    python3-requests \
    python3-venv \
    qemu-utils=1:10.2.1+ds-1ubuntu3.2 \
    curl \
    ripgrep \
    shellcheck=0.11.0-2

# The graphical backend does not need recommended host networking services or
# a separate VNC server. Feature::Compat::Try is used by the packaged entry
# point but is missing from this os-autoinst package's dependency declaration.
"${apt_get[@]}" install -y --no-install-recommends \
    os-autoinst=5.1768577300.b85e4864-1 \
    libfeature-compat-try-perl=0.05-1 \
    util-linux=2.41.3-3ubuntu2.2 \
    iproute2=6.19.0-1ubuntu1.1

"${apt_get[@]}" build-dep -y "$script_dir"

# Keep the public development identity and signing settings local to this checkout.
# The private signing key must be restored separately before signing releases.
git -C "$script_dir" config --local user.name 'Puffy Slippers Tech LLC'
git -C "$script_dir" config --local user.email 'dev@tech.puffyslippers.com'
git -C "$script_dir" config --local gpg.format openpgp
git -C "$script_dir" config --local user.signingkey '4449F02C3E57F8215261A57958109B593907EFDE'
echo "setup: configured checkout-local Git identity and OpenPGP signing key"

# GNOME Shell 50 supplies the public org.gnome.Shell.Screenshot interface used
# by isolated child component evidence capture; no host screenshot tool or
# desktop-session access is used.

ui_venv="$script_dir/.venv/onpc-ui-tests"
"/usr/bin/python3" -m venv --system-site-packages "$ui_venv"
"$ui_venv/bin/python" -m pip install --disable-pip-version-check --no-deps \
    --require-hashes -r "$script_dir/tests/ui/requirements.txt"
