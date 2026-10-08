#!/usr/bin/env bash
set -euo pipefail

# Host package module; setup.sh supplies the scoped privilege authorization.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly apt_lock_timeout_seconds=300
if (( EUID != 0 || $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ppa-build-tools' && "$1" != '--rpm-build-tools' ]]; }; then
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

install_rpm_build_tools() {
    "${apt_get[@]}" install -y --no-install-recommends rpm podman uidmap passt slirp4netns fuse-overlayfs
}

"${apt_get[@]}" update
if [[ "${1-}" == '--ppa-build-tools' ]]; then
    install_ppa_build_tools
    exit 0
fi
if [[ "${1-}" == '--rpm-build-tools' ]]; then
    install_rpm_build_tools
    exit 0
fi
if ! command -v add-apt-repository >/dev/null 2>&1; then
    "${apt_get[@]}" install -y software-properties-common
fi
add-apt-repository -y universe
"${apt_get[@]}" update
# Use repository candidates: exact distro revisions can disappear as updates
# supersede them, and related packages must be resolved together by APT.
"${apt_get[@]}" install -y \
    7zip \
    apparmor \
    strace \
    build-essential \
    at-spi2-core \
    dbus-daemon \
    dbus-user-session \
    debhelper \
    devscripts \
    dpkg-dev \
    dh-python \
    dput \
    flatpak \
    squashfs-tools \
    snapd \
    fonts-dejavu-core \
    xkb-data \
    git \
    gnome-ponytail-daemon \
    gnupg \
    gir1.2-adw-1 \
    gir1.2-glib-2.0 \
    gir1.2-gtk-4.0 \
    gir1.2-vte-3.91 \
    gir1.2-webkit-6.0 \
    gnome-shell \
    inotify-tools \
    libfeature-compat-try-perl \
    gjs \
    libpam0g-dev \
    libglib2.0-bin \
    libc-bin \
    libvirt-daemon-system \
    qemu-system-x86 \
    qemu-system-modules-opengl \
    libvirt-clients \
    libguestfs-tools \
    lintian \
    make \
    mutter \
    mutter-dev-bin \
    nodejs \
    openssh-client \
    openssl \
    pipewire \
    wireplumber \
    gstreamer1.0-pipewire \
    gstreamer1.0-gtk4 \
    python3 \
    python3-dbusmock \
    python3-gi \
    python3-gi-cairo \
    python3-hypothesis \
    python3-libvirt \
    python3-guestfs \
    python3-pytest \
    python3-pytest-cov \
    python3-requests \
    python3-rich \
    python3-venv \
    qemu-utils \
    curl \
    ripgrep \
    shellcheck

# The graphical backend does not need recommended host networking services or
# a separate VNC server. Feature::Compat::Try is included with the build
# prerequisites above because os-autoinst omits that dependency.
"${apt_get[@]}" install -y --no-install-recommends \
    os-autoinst \
    util-linux \
    iproute2

"${apt_get[@]}" build-dep -y "$script_dir"
install_ppa_build_tools
install_rpm_build_tools
