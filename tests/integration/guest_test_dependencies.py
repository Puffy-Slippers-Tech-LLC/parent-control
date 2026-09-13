"""Shared, product-free guest tool contract; no installation at import time.

Only prepare_vm installs these packages. Controllers and guest tests verify the
same inventory and refuse an incomplete baseline instead of repairing it.
"""

import re

REMOTE_PACKAGES = (
    'slapd=2.6.10+dfsg-1ubuntu5', 'ldap-utils=2.6.10+dfsg-1ubuntu5',
    'sssd-ldap=2.12.0-1ubuntu5.4', 'libnss-sss=2.12.0-1ubuntu5.4',
)
PACKAGES = (
    'openssh-server=1:10.2p1-2ubuntu3.6', 'python3-pytest=9.0.2-4',
    *REMOTE_PACKAGES,
)
VERSIONS = dict(package.split('=', 1) for package in PACKAGES)
DORMANT_PATHS = ('/etc/ldap/slapd.d', '/etc/ldap/slapd.conf', '/etc/sssd/sssd.conf')


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
    """Check dpkg's public status paragraphs, including fully configured state."""
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
    if found != expected:
        raise ValueError('guest-tools:missing-or-mismatched-package; run make prepare-vm before baseline capture')
    return found
