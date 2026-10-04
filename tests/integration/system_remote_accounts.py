"""Real LDAP/NSS identities, provisioned only inside the guarded reset guest.

The retained baseline is the cleanup boundary. No private AccountsService
records, local passwd identities, passwords or new process cleanup are used.
"""

import grp
import os
from pathlib import Path
import pwd
import re
import stat
import time

import system_guest as guest
from guest_test_dependencies import (REMOTE_PACKAGES as PACKAGES, FEDORA_REMOTE_VERSIONS,
                                     dormant_paths, verify_fedora_packages, verify_packages)

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


def package_versions():
    fedora = guest.package_path().suffix == '.rpm'
    names = list(FEDORA_REMOTE_VERSIONS) if fedora else [item.split('=')[0] for item in PACKAGES]
    command = (['rpm', '-q', '--queryformat', '%{NAME}=%{VERSION}\n', *names] if fedora else
               ['dpkg-query', '-W', '-f=${Package}=${Version}\n', *names])
    value = guest.run(command, timeout=10)
    rows = [line.split('=', 1) for line in value.splitlines()]
    guest.require(len(rows) == len(names) and {row[0] for row in rows} == set(names)
                  and all(len(row) == 2 and re.fullmatch(r'[0-9][A-Za-z0-9.+:~\-]{0,127}', row[1])
                          for row in rows), 'remote:package-versions')
    return value


def configure_ubuntu():
    """Reconfigure the dormant DEB through its package's public interface."""
    guest.commands.run(['debconf-set-selections'], input=(
        'slapd slapd/domain string onpc.invalid\n'
        'slapd shared/organization string ONPC test directory\n'
        'slapd slapd/no_configuration boolean false\n').encode(), merge_stderr=False)
    defaults = Path('/etc/default/slapd')
    lines = defaults.read_text().splitlines()
    guest.require(sum(line.startswith('SLAPD_SERVICES=') for line in lines) == 1,
                  'remote:ldap-listener-configuration')
    defaults.write_text('\n'.join(
        'SLAPD_SERVICES="ldap://127.0.0.1/ ldapi:///"'
        if line.startswith('SLAPD_SERVICES=') else line for line in lines) + '\n')
    guest.run(['dpkg-reconfigure', '--frontend=noninteractive', 'slapd'], timeout=120)
    guest.run(['systemctl', 'restart', 'slapd.service'])


def configure_fedora():
    """Create isolated slapd configuration; preserve RPM defaults and SELinux."""
    for unit in ('slapd.service', 'sssd.service'):
        state = guest.run(['systemctl', 'show', unit, '--property=ActiveState', '--value'])
        guest.require(state in {'inactive', 'failed'}, 'remote:directory-active')
    ldap = pwd.getpwnam('ldap')
    # cn=config is a writable database. Fedora labels the native slapd.d
    # directory and /var/lib/ldap trees slapd_db_t, but arbitrary /etc/openldap
    # subdirectories get a read-only configuration context. Keep the isolated
    # config under the native database tree so online LDAP changes can persist.
    config = Path('/var/lib/ldap/onpc-system-fixture-config')
    database = Path('/var/lib/ldap/onpc-system-fixture')
    for path in (config, database):
        path.mkdir(mode=0o700)
        os.chown(path, ldap.pw_uid, ldap.pw_gid)
    # slapadd's configuration import is the same public API used by the RPM.
    # It accepts schema includes; no directory-manager password is configured.
    schema = '\n'.join(f'include: file:///etc/openldap/schema/{name}.ldif'
                       for name in ('core', 'cosine', 'nis', 'inetorgperson'))
    configuration = f'''dn: cn=config
objectClass: olcGlobal
cn: config

dn: cn=schema,cn=config
objectClass: olcSchemaConfig
cn: schema

{schema}

dn: olcDatabase=config,cn=config
objectClass: olcDatabaseConfig
olcDatabase: config
olcAccess: to * by dn.exact="gidNumber=0+uidNumber=0,cn=peercred,cn=external,cn=auth" manage by * none

dn: olcDatabase=mdb,cn=config
objectClass: olcDatabaseConfig
objectClass: olcMdbConfig
olcDatabase: mdb
olcSuffix: {BASE}
olcDbDirectory: {database}
olcDbIndex: objectClass eq
'''
    guest.run(['restorecon', '-RF', str(config), str(database)])
    guest.commands.run(['runuser', '--user', 'ldap', '--', 'slapadd', '-F', str(config), '-n', '0'],
                       input=configuration.encode(), timeout=30, merge_stderr=False)
    guest.run(['restorecon', '-RF', str(config)])
    dropin = Path('/etc/systemd/system/slapd.service.d/onpc-system-fixture.conf')
    dropin.parent.mkdir(mode=0o755, exist_ok=True)
    with dropin.open('x') as stream:
        stream.write('[Service]\nExecStart=\nExecStart=/usr/sbin/slapd -u ldap '
                     f'-F {config} -h "ldap://127.0.0.1/ ldapi:///"\n')
    guest.run(['restorecon', str(dropin)])
    guest.run(['systemctl', 'daemon-reload'])
    guest.run(['systemctl', 'start', 'slapd.service'])


def configure_fedora_nss(restoration):
    """Clone the live authselect profile, retaining its PAM stack and features."""
    guest.run(['authselect', 'check'])
    original = guest.run(['authselect', 'current', '--raw']).split()
    guest.require(original and all(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_/-]*', part)
                                  and '..' not in part for part in original),
                  'remote:authselect-selection')
    restoration['original'] = original
    guest.run(['authselect', 'create-profile', 'onpc-remote-fixture', '-b', original[0]])
    nss = Path('/etc/authselect/custom/onpc-remote-fixture/nsswitch.conf')
    metadata = nss.lstat()
    guest.require(stat.S_ISREG(metadata.st_mode) and metadata.st_uid == 0
                  and not metadata.st_mode & 0o022, 'remote:authselect-profile')
    nss.write_text(nss_configuration(nss.read_text()))
    restoration['profile_sha256'] = guest.sha(nss)
    guest.run(['authselect', 'select', 'custom/onpc-remote-fixture', *original[1:]])
    guest.run(['authselect', 'check'])


def restore_nss(restoration):
    """Return to the exact product profile before later upgrade/removal phases."""
    if not restoration:
        return
    guest.guard()
    original = restoration['original']
    current = guest.run(['authselect', 'current', '--raw']).split()
    if current == original:
        return  # Creation/select failure did not change the active profile.
    guest.require(current == ['custom/onpc-remote-fixture', *original[1:]],
                  'remote:authselect-restore-collision')
    guest.require(guest.sha(Path('/etc/authselect/custom/onpc-remote-fixture/nsswitch.conf')) ==
                  restoration['profile_sha256'], 'remote:authselect-profile-changed')
    guest.run(['systemctl', 'stop', 'sssd.service'])
    guest.run(['authselect', 'select', *original])
    guest.run(['authselect', 'check'])


def provision(*, restoration=None):
    guest.guard()  # Must precede even fixture/precondition filesystem access.
    guest.enable_diagnostics()
    fedora = guest.package_path().suffix == '.rpm'
    guest.require(not fedora or isinstance(restoration, dict), 'remote:restoration-required')
    for path in dormant_paths('fedora' if fedora else 'ubuntu'):
        guest.require(not Path(path).exists() and not Path(path).is_symlink(),
                      'remote:configuration-collision')
    for name, uid in IDENTITIES.values():
        for lookup, value in ((pwd.getpwnam, name), (pwd.getpwuid, uid), (grp.getgrgid, uid)):
            try:
                lookup(value)
            except KeyError:
                continue
            raise guest.GuestError('remote:identity-collision')
    if fedora:
        versions = package_versions()
        verify_fedora_packages([line.split('=', 1) for line in versions.splitlines()],
                               FEDORA_REMOTE_VERSIONS)
    else:
        verify_packages(Path('/var/lib/dpkg/status').read_text(), PACKAGES)
    print('onpc-system: stage=remote-packages outcome=prepared', flush=True)
    configure_fedora() if fedora else configure_ubuntu()
    database = guest.run(['ldapsearch', '-LLL', '-Q', '-Y', 'EXTERNAL', '-H', 'ldapi:///',
                          '-b', 'cn=config', f'(olcSuffix={BASE})', 'dn'])
    guest.require(database == 'dn: olcDatabase={1}mdb,cn=config', 'remote:ldap-database')
    ldap_input('ldapmodify', f'''dn: olcDatabase={{1}}mdb,cn=config
changetype: modify
replace: olcAccess
olcAccess: to * by dn.exact="gidNumber=0+uidNumber=0,cn=peercred,cn=external,cn=auth" manage by * read
''')
    entries = [f'dn: {BASE}\nobjectClass: dcObject\nobjectClass: organization\ndc: onpc\no: ONPC test directory\n'] if fedora else []
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
    if fedora:
        configure_fedora_nss(restoration)
        guest.run(['restorecon', str(config)])
    else:
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
    guest.run(['gpasswd', '--add', IDENTITIES['administrator'][0], 'wheel' if fedora else 'sudo'])
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
