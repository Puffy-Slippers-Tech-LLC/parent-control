#!/usr/bin/env bash
set -euo pipefail

# Host package module; setup.sh supplies the scoped privilege authorization.
readonly script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
readonly apt_lock_timeout_seconds=300
if (( EUID != 0 || $# > 1 )) || { (( $# == 1 )) && [[ "$1" != '--ppa-build-tools' && "$1" != '--rpm-build-tools' && "$1" != '--vm-host-only' ]]; }; then
    echo 'setup-dependencies: use ./setup.sh with installed setup authorization' >&2
    exit 2
fi
source "$script_dir/tools/setup_platform.sh"

if [[ $setup_platform == fedora ]]; then
    if [[ ${1-} == --ppa-build-tools ]]; then
        echo 'setup: PPA build tools require an Ubuntu/Debian host' >&2
        exit 2
    fi
    # Keep this inventory aligned with rpm/oh-no-parent-control.spec.in.
    # Development RPM builds stay native; clean publishing checks use Podman.
    # Full setup also adds the Ubuntu DEB builder.
    rpm_packages=(rpm-build gcc gettext make pam-devel glib2 nodejs python3
                  redhat-rpm-config systemd-rpm-macros tar xz)
    if [[ ${1-} == --rpm-build-tools ]]; then
        dnf -y install "${rpm_packages[@]}" podman shadow-utils-subid \
            passt slirp4netns fuse-overlayfs
        exit 0
    fi
    if [[ ${1-} == --vm-host-only ]]; then
        dnf -y install libvirt-daemon-kvm libvirt-client qemu-kvm qemu-img \
            guestfs-tools python3-libvirt python3-libguestfs os-autoinst \
            perl-Feature-Compat-Try util-linux iproute ffmpeg-free
        exit 0
    fi
    # Dogtail's input layer needs GTK 3 and Fedora's separate Ponytail client,
    # including when the application under test uses GTK 4.
    dnf -y install "${rpm_packages[@]}" \
        7zip strace at-spi2-core dbus-daemon dbus-tools dbus-x11 \
        flatpak squashfs-tools snapd dejavu-sans-fonts xkeyboard-config \
        glibc glibc-langpack-en git gnupg2 gnome-ponytail-daemon python3-gnome-ponytail-daemon \
        libadwaita gtk3 gtk4 vte291-gtk4 webkitgtk6.0 gtk-update-icon-cache \
        gnome-shell gjs mutter mutter-devkit inotify-tools openssh-clients openssl \
        pipewire wireplumber pipewire-gstreamer gstreamer1-plugin-gtk4 \
        python3-dbusmock python3-gobject python3-cairo python3-hypothesis \
        python3-pytest python3-pytest-cov python3-requests python3-rich \
        python3-pip curl ripgrep ShellCheck polkit util-linux iproute ffmpeg-free \
        debhelper dpkg-dev perl-Feature-Compat-Try podman shadow-utils-subid \
        passt slirp4netns fuse-overlayfs
    exit 0
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
if [[ "${1-}" == '--vm-host-only' ]]; then
    "${apt_get[@]}" install -y --no-install-recommends \
        apparmor libvirt-daemon-system libvirt-clients qemu-system-x86 \
        qemu-system-modules-opengl qemu-utils libguestfs-tools \
        python3-libvirt python3-guestfs os-autoinst libfeature-compat-try-perl \
        util-linux iproute2 ffmpeg
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
    ffmpeg \
    xkb-data \
    git \
    gnome-ponytail-daemon \
    gnupg \
    gir1.2-adw-1 \
    gir1.2-glib-2.0 \
    gir1.2-gtk-3.0 \
    gir1.2-gtk-4.0 \
    gir1.2-vte-3.91 \
    gir1.2-webkit-6.0 \
    gnome-shell \
    inotify-tools \
    gjs \
    libpam0g-dev \
    libglib2.0-bin \
    libc-bin \
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
    python3-pytest \
    python3-pytest-cov \
    python3-requests \
    python3-rich \
    python3-venv \
    curl \
    ripgrep \
    shellcheck \
    polkitd \
    pkexec

"${apt_get[@]}" install -y --no-install-recommends \
    util-linux \
    iproute2

"${apt_get[@]}" build-dep -y "$script_dir"
install_ppa_build_tools
install_rpm_build_tools
