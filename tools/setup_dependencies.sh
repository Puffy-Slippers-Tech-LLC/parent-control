#!/usr/bin/env bash
set -euo pipefail

# Host package module; setup.sh supplies the scoped privilege authorization.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly apt_lock_timeout_seconds=300
if (( EUID != 0 || $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ppa-build-tools' ]]; }; then
    echo 'setup-dependencies: use ./setup.sh with installed setup authorization' >&2
    exit 2
fi
if ! command -v apt-get >/dev/null; then
    echo "setup: Ubuntu/Debian with apt-get is required" >&2
    exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt_get=(apt-get -o "DPkg::Lock::Timeout=$apt_lock_timeout_seconds")

install_ppa_build_tools() {
    "${apt_get[@]}" install -y --no-install-recommends sbuild mmdebstrap uidmap ubuntu-keyring
}

"${apt_get[@]}" update
if [[ "${1-}" == '--ppa-build-tools' ]]; then
    install_ppa_build_tools
    exit 0
fi
"${apt_get[@]}" install -y software-properties-common
add-apt-repository -y universe
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
    openssl=3.5.5-1ubuntu3.5 \
    pipewire=1.6.2-1ubuntu1.1 \
    wireplumber \
    gstreamer1.0-pipewire \
    gstreamer1.0-gtk4 \
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
    python3-rich \
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
install_ppa_build_tools
