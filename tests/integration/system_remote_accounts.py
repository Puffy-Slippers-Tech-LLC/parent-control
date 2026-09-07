"""Real LDAP/NSS identities, provisioned only inside the guarded reset guest.

The retained baseline is the cleanup boundary. No private AccountsService
records, local passwd identities, passwords or new process cleanup are used.
"""

import grp
from pathlib import Path
import pwd
import time

import system_guest as guest

PACKAGES = (
    'slapd=2.6.10+dfsg-1ubuntu5', 'ldap-utils=2.6.10+dfsg-1ubuntu5',
    'sssd-ldap=2.12.0-1ubuntu5.4', 'libnss-sss=2.12.0-1ubuntu5.4',
)
IDENTITIES = {'child': ('onpc-remote-child', 24001),
              'administrator': ('onpc-remote-admin', 24002)}
BASE = 'dc=onpc,dc=invalid'


def nss_configuration(original):
    """Preserve every existing source/action and enable only passwd/group NSS."""
    lines, found = [], set()
    for line in original.splitlines():
        body, separator, comment = line.partition('#')
        database, colon, sources = body.partition(':')
        if colon and database.strip() in {'passwd', 'group'}:
            guest.require(database.strip() not in found, 'remote:nss-duplicate-database')
            found.add(database.strip())
            if 'sss' not in sources.split():
                body = body.rstrip() + ' sss '
        lines.append(body + separator + comment)
    guest.require(found == {'passwd', 'group'}, 'remote:nss-missing-database')
    return '\n'.join(lines) + '\n'


def ldap_input(tool, value):
    return guest.commands.run([tool, '-Q', '-Y', 'EXTERNAL', '-H', 'ldapi:///'],
                              input=value.encode(), merge_stderr=False)


def provision():
    guest.guard()  # Must precede even fixture/precondition filesystem access.
    guest.enable_diagnostics()
    for path in ('/etc/ldap/slapd.d', '/etc/sssd/sssd.conf'):
        guest.require(not Path(path).exists(), 'remote:configuration-collision')
    for name, uid in IDENTITIES.values():
        for lookup, value in ((pwd.getpwnam, name), (pwd.getpwuid, uid), (grp.getgrgid, uid)):
            try:
                lookup(value)
            except KeyError:
                continue
            raise guest.GuestError('remote:identity-collision')
    print('onpc-system: stage=remote-packages outcome=starting', flush=True)
    guest.run(['apt-cache', 'policy', *[package.split('=')[0] for package in PACKAGES]])
    # APT metadata was refreshed by the guarded package-install phase. LDAP
    # administration uses root peer credentials; no password is configured.
    guest.commands.run(['debconf-set-selections'], input=(
        'slapd slapd/domain string onpc.invalid\n'
        'slapd shared/organization string ONPC test directory\n'
        'slapd slapd/no_configuration boolean false\n').encode(), merge_stderr=False)
    guest.run(['env', 'DEBIAN_FRONTEND=noninteractive', 'apt-get',
               '-o', 'DPkg::Lock::Timeout=120', 'install', '--no-install-recommends',
               '-y', *PACKAGES], timeout=600)
    # Use the packaged service/configuration API; confine anonymous identity
    # queries to loopback. There is no LDAP authentication or PAM modification.
    defaults = Path('/etc/default/slapd')
    lines = defaults.read_text().splitlines()
    guest.require(sum(line.startswith('SLAPD_SERVICES=') for line in lines) == 1,
                  'remote:ldap-listener-configuration')
    defaults.write_text('\n'.join(
        'SLAPD_SERVICES="ldap://127.0.0.1/ ldapi:///"'
        if line.startswith('SLAPD_SERVICES=') else line for line in lines) + '\n')
    guest.run(['systemctl', 'restart', 'slapd.service'])
    database = guest.run(['ldapsearch', '-LLL', '-Q', '-Y', 'EXTERNAL', '-H', 'ldapi:///',
                          '-b', 'cn=config', f'(olcSuffix={BASE})', 'dn'])
    guest.require(database == 'dn: olcDatabase={1}mdb,cn=config', 'remote:ldap-database')
    ldap_input('ldapmodify', f'''dn: olcDatabase={{1}}mdb,cn=config
changetype: modify
replace: olcAccess
olcAccess: to * by dn.exact="gidNumber=0+uidNumber=0,cn=peercred,cn=external,cn=auth" manage by * read
''')
    entries = []
    for name, uid in IDENTITIES.values():
        entries.append(f'''dn: cn={name},{BASE}
objectClass: posixGroup
cn: {name}
gidNumber: {uid}

dn: uid={name},{BASE}
objectClass: inetOrgPerson
objectClass: posixAccount
cn: {name}
sn: Fixture
uid: {name}
uidNumber: {uid}
gidNumber: {uid}
homeDirectory: /home/{name}
loginShell: /bin/bash
''')
    ldap_input('ldapadd', '\n'.join(entries))
    config = Path('/etc/sssd/sssd.conf')
    with config.open('x') as stream:
        config.chmod(0o600)
        stream.write(f'''[sssd]
config_file_version = 2
services = nss
domains = onpc.invalid

[domain/onpc.invalid]
id_provider = ldap
auth_provider = none
access_provider = deny
ldap_uri = ldap://127.0.0.1
ldap_search_base = {BASE}
ldap_id_use_start_tls = false
enumerate = true
cache_credentials = false
use_fully_qualified_names = false
''')
    nss = Path('/etc/nsswitch.conf')
    nss.write_text(nss_configuration(nss.read_text()))
    guest.run(['systemctl', 'start', 'sssd.service'])
    started = time.monotonic()
    while True:
        seen = {entry.pw_name: entry.pw_uid for entry in pwd.getpwall()}
        if all(seen.get(name) == uid for name, uid in IDENTITIES.values()):
            break
        guest.require(time.monotonic() - started < 30, 'remote:nss-readiness')
        time.sleep(0.25)
    # Group membership is a public system operation and creates no passwd
    # record. AccountsService derives the administrator flag from getgrouplist.
    guest.run(['gpasswd', '--add', IDENTITIES['administrator'][0], 'sudo'])
    for name, uid in IDENTITIES.values():
        guest.require(pwd.getpwnam(name).pw_uid == uid and pwd.getpwuid(uid).pw_name == name,
                      'remote:nss-resolution')
        local = guest.commands.run(['getent', '-s', 'files', 'passwd', name],
                                   check=False, merge_stderr=False)
        guest.require(guest.commands.last_returncode == 2 and not local,
                      'remote:unexpected-local-account')
        guest.run(['busctl', '--system', 'call', 'org.freedesktop.Accounts',
                   '/org/freedesktop/Accounts', 'org.freedesktop.Accounts',
                   'CacheUser', 's', name])
    print('onpc-system: stage=remote-nss outcome=ready', flush=True)
    return {role: uid for role, (_, uid) in IDENTITIES.items()}
