"""Shared, product-free guest tool contract; no installation at import time.

prepare_vm installs these packages; auto baseline preparation updates them.
Controllers and guest tests verify the same minimum inventory and refuse an
incomplete baseline instead of repairing it.
"""

import re
import subprocess
from chinese_language_assets import PACKAGES as CHINESE_PACKAGES, FEDORA_PACKAGES as FEDORA_CHINESE_PACKAGES

REMOTE_PACKAGES = (
    'slapd=2.6.10+dfsg-1ubuntu5', 'ldap-utils=2.6.10+dfsg-1ubuntu5',
    'sssd-ldap=2.12.0-1ubuntu5.4', 'libnss-sss=2.12.0-1ubuntu5.4',
)
PACKAGES = (
    'openssh-server=1:10.2p1-2ubuntu3.6', 'python3-pytest=9.0.2-4',
    # Native GUI fixtures use the distribution's maintained GTK 4 bindings.
    'python3-gi=0', 'gir1.2-gtk-4.0=0',
    # The SPICE channel needs the guest daemon and desktop session agent.
    'spice-vdagent=0',
    *REMOTE_PACKAGES,
    *CHINESE_PACKAGES,
)
VERSIONS = dict(package.split('=', 1) for package in PACKAGES)
# Qualified minimum versions. Security and maintenance updates may be newer.
DORMANT_PATHS = ('/etc/ldap/slapd.d', '/etc/ldap/slapd.conf', '/etc/sssd/sssd.conf')
FEDORA_REMOTE_VERSIONS = {'openldap-servers': '2.6.10', 'openldap-clients': '2.6.10',
                          'sssd-ldap': '2.12.0', 'sssd-client': '2.12.0'}
FEDORA_VERSIONS = {'openssh-server': '10.2p1', 'python3-pytest': '8.4.2',
                   'python3-gobject': '0', 'gtk4': '0', 'spice-vdagent': '0', **FEDORA_REMOTE_VERSIONS,
                   **dict.fromkeys(FEDORA_CHINESE_PACKAGES, '0')}
# Fedora's RPM generates its own default slapd.d. The fixture uses separate
# configuration/database paths and leaves those package defaults untouched.
FEDORA_DORMANT_PATHS = ('/etc/sssd/sssd.conf',
                       '/var/lib/ldap/onpc-system-fixture-config',
                       '/var/lib/ldap/onpc-system-fixture',
                       '/etc/systemd/system/slapd.service.d/onpc-system-fixture.conf',
                       '/etc/authselect/custom/onpc-remote-fixture')


def dormant_paths(os_id):
    if os_id == 'ubuntu':
        return DORMANT_PATHS
    if os_id == 'fedora':
        return FEDORA_DORMANT_PATHS
    raise ValueError('guest-tools:unsupported-os')


def versions(os_id):
    if os_id == 'ubuntu':
        return VERSIONS
    if os_id == 'fedora':
        return FEDORA_VERSIONS
    raise ValueError('guest-tools:unsupported-os')


def verify_fedora_packages(packages, expected=FEDORA_VERSIONS):
    """Compare stable upstream versions, independently of RPM release counters.

    These projects use numeric releases (OpenSSH also uses pN). Refuse
    prerelease/unknown formats rather than guessing their RPM ordering.
    """
    def stable_version(value):
        if not isinstance(value, str) or not re.fullmatch(r'[0-9]+(?:[.p][0-9]+)*', value):
            raise ValueError('guest-tools:unsupported-package-version')
        return tuple(int(part) for part in re.split(r'[.p]', value))
    found = {}
    for name, version in packages:
        if name not in expected:
            continue
        if name in found:
            raise ValueError('guest-tools:ambiguous-package-status')
        if stable_version(version) < stable_version(expected[name]):
            raise ValueError('guest-tools:missing-or-mismatched-package')
        found[name] = version
    if set(found) != set(expected):
        raise ValueError('guest-tools:missing-or-mismatched-package')
    return found


def verify_installed(os_id, *, runner, root):
    if os_id == 'ubuntu':
        found = verify_packages((root / 'var/lib/dpkg/status').read_text())
        from chinese_language_assets import LocalFiles, verify
        verify(LocalFiles(root))
        return found
    if os_id != 'fedora':
        raise ValueError('guest-tools:unsupported-os')
    result = runner.run(['rpm', '-qa', '--queryformat', '%{NAME}\t%{VERSION}\n'])
    rows = [line.split('\t') for line in result.stdout.splitlines()]
    if any(len(row) != 2 for row in rows):
        raise ValueError('guest-tools:ambiguous-package-status')
    found = verify_fedora_packages(rows)
    from chinese_language_assets import LocalFiles, verify
    verify(LocalFiles(root), os_id)
    return found


def ubuntu_archive_sources(contents):
    """Normalize only official Ubuntu URIs; preserve other Deb822 fields."""
    lines = []
    uri_field = False
    for line in contents.splitlines(keepends=True):
        if line.strip() and not line.lstrip().startswith('#'):
            if not line[0].isspace():
                uri_field = line.lower().startswith('uris:')
            if uri_field:
                line = re.sub(
                    r'(?<!\S)https?://(?:(?:[a-z]{2}\.)?archive|security)\.ubuntu\.com/ubuntu/?(?=\s|$)',
                    'https://archive.ubuntu.com/ubuntu/', line)
        elif not line.strip():
            uri_field = False
        lines.append(line)
    return ''.join(lines)


def verify_packages(status, packages=PACKAGES):
    """Require fully configured packages at or above their qualified versions."""
    expected = dict(package.split('=', 1) for package in packages)
    found = {}
    for paragraph in status.split('\n\n'):
        fields = {}
        for line in paragraph.splitlines():
            if line.startswith((' ', '\t')) or ':' not in line:
                continue
            name, value = line.split(':', 1)
            if name in fields:
                raise ValueError('guest-tools:ambiguous-package-status')
            fields[name] = value.strip()
        name = fields.get('Package')
        if name not in expected:
            continue
        if name in found:
            raise ValueError('guest-tools:ambiguous-package-status')
        if fields.get('Status') != 'install ok installed':
            raise ValueError('guest-tools:package-not-configured')
        found[name] = fields.get('Version')
    if set(found) != set(expected) or any(
            not version or subprocess.run(
                ['/usr/bin/dpkg', '--compare-versions', version, 'ge', expected[name]],
                check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                timeout=10).returncode != 0
            for name, version in found.items()):
        raise ValueError('guest-tools:missing-or-mismatched-package; run tools/prepare-vm on the host')
    return found
