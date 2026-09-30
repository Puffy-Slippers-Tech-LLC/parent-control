"""Resume a guarded app snapshot and replace its preparation credentials.

One small root-private record per pinned VM survives evidence rotation. Its
credentials are usable only for the exact snapshot XML recorded under the VM
lease; they are never printed or placed in libvirt's public description.
"""
import hashlib
from contextlib import contextmanager
import inspect
import json
import os
from pathlib import Path
import re
import time
import uuid
import xml.etree.ElementTree as ET

import system_runner as system
from tools import test_storage, test_retention


def record_store(source, *, create=False):
    system.require(re.fullmatch(r'[0-9a-f-]{36}', source.uuid) is not None,
                   'online-snapshot:invalid-uuid')
    path = test_storage.directory('state') / ('online-appsnapshot-' + source.uuid)
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    return test_retention.Store(path)


def fingerprint(xml):
    return hashlib.sha256(xml.encode()).hexdigest()


def recover_identity(lease):
    """Bind explicitly authorized interrupted-start cleanup to a saved snapshot."""
    live = ET.fromstring(lease.source.domain.XMLDesc(0))
    tag = live.findtext('description', '')
    matches = []
    for snap in lease.source.domain.listAllSnapshots(0):
        if re.fullmatch(r'onpc-v[0-9]+(?:\.[0-9]+)*', snap.getName()) is None:
            continue
        xml = snap.getXMLDesc(0)
        root = ET.fromstring(xml)
        domain = root.find('domain')
        if (domain is None or domain.findtext('description') != tag or
                root.findtext('state') != 'running' or
                root.find('memory') is None or root.find('memory').get('snapshot') != 'internal'):
            continue
        record = load(lease.source, snap.getName(), xml)
        if record is None or tag != system.TAG + record['run']:
            continue
        system.require(json.loads(root.findtext('description'))['baseline_sha256'] ==
                       lease.state['baseline_sha256'], 'online-snapshot:baseline-changed')
        expected = dict(lease.capture.state['source']['layout'], source_shares=[])
        for tree in (domain, live):
            system.require(system.baseline.domain_layout(ET.tostring(tree, encoding='unicode'),
                lease.source.uuid) == expected, 'online-snapshot:source-changed')
            system.validate_private_vnc(tree)
            system.require(not any(tree.findall('devices/' + kind) for kind in
                ('filesystem', 'hostdev', 'channel', 'redirdev')), 'online-snapshot:host-sharing')
        matches.append(record['run'])
    system.require(len(matches) == 1, 'online-snapshot:recovery-identity')
    return matches[0]


def load(source, name, xml):
    store = record_store(source)
    if not store.path.exists():
        return None
    with store.opened() as fd:
        try:
            source_fd = os.open('snapshot.json', os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
        except FileNotFoundError:
            return None
        with os.fdopen(source_fd) as stream:
            info = os.fstat(stream.fileno())
            test_retention.private(info, regular=True)
            system.require(info.st_size <= 16384, 'online-snapshot:invalid-record')
            value = json.load(stream)
    system.require(isinstance(value, dict) and value.get('schema_version') == 1,
                   'online-snapshot:invalid-record')
    if (value.get('name'), value.get('snapshot_sha256')) != (name, fingerprint(xml)):
        return None
    system.require(set(value) == {'schema_version', 'name', 'snapshot_sha256',
        'run', 'host_key', 'private_key', 'public_key'}
        and isinstance(value['run'], str)
        and re.fullmatch(r'[0-9a-f]{32}', value['run']) is not None
        and all(isinstance(value[key], str) for key in
                ('host_key', 'private_key', 'public_key')),
        'online-snapshot:invalid-record')
    return value


def publish(lease, setup, host_key):
    lease.guard()
    value = dict(schema_version=1, name=lease.installed_name,
        snapshot_sha256=fingerprint(lease.installed_xml), run=lease.state['run'],
        host_key=host_key, private_key=(setup / 'ssh-key').read_text(),
        public_key=(setup / 'ssh-key.pub').read_text())
    store = record_store(lease.source, create=True)
    with store.opened() as fd:
        store.save(fd, value, name='snapshot.json')


def stage(commands, lease, directory):
    """Prepare fresh attempt keys while the VM remains off for worker startup."""
    from app_snapshot import mode_mismatch
    lease.guard(off=True)
    system.require(mode_mismatch(lease.installed_xml, 'online') is None,
                   'online-snapshot:expired-or-invalid')
    record = load(lease.source, lease.installed_name, lease.installed_xml)
    system.require(record is not None, 'online-snapshot:credentials-missing')
    commands.run(['ssh-keygen', '-q', '-t', 'ed25519', '-N', '',
                  '-C', 'onpc-system-test', '-f', str(directory / 'ssh-key')])
    lease.online_bootstrap = (directory, record)
    return record['host_key']


# Executed through Transport's existing host and saved-guest identity guards.
# stdin carries the fresh public key and marker; no secret is logged.
REBIND = '''import json,os,pathlib,re,stat,sys,uuid
data=json.load(sys.stdin)
marker_path=pathlib.Path('/etc/onpc-system-test.json')
marker=json.loads(marker_path.read_text())
assert marker['baseline_sha256']==data['baseline_sha256']
assert marker['preparation_sha256']==data['preparation_sha256']
assert re.fullmatch(r'[0-9a-f]{32}',data['run'])
assert re.fullmatch(r'ssh-ed25519 [A-Za-z0-9+/=]+(?: [^\\r\\n]*)?\\n?',data['public_key'])
ssh=pathlib.Path('/root/.ssh'); authorized=ssh/'authorized_keys'
assert ssh.resolve()==ssh and authorized.resolve()==authorized
for p,mode in ((ssh,448),(authorized,384)):
 s=p.lstat(); assert s.st_uid==s.st_gid==0 and stat.S_IMODE(s.st_mode)==mode
assert authorized.is_file() and authorized.stat().st_nlink==1
old=authorized.read_text().splitlines()
assert data['old_public_key'].strip() in old
contents='\\n'.join([line for line in old if line!=data['old_public_key'].strip()]+[data['public_key'].strip()])+'\\n'
payload=pathlib.Path('/var/tmp/onpc-system-input')
assert pathlib.Path('/var/tmp').resolve()==pathlib.Path('/var/tmp') and not payload.is_symlink()
if payload.exists():
 s=payload.stat(); assert stat.S_ISDIR(s.st_mode) and s.st_uid==s.st_gid==0 and not stat.S_IMODE(s.st_mode)&18
 previous=payload.with_name(payload.name+'-snapshot-'+data['run']+'-'+uuid.uuid4().hex)
 assert not previous.exists() and not previous.is_symlink()
 payload.rename(previous)
 assert not payload.exists() and previous.is_dir()
for key in ('run','selected_inputs_sha256','package_sha256'):
 marker[key]=data[key]
marker.pop('scope',None)
def replace(path,contents):
 temporary=path.with_name(path.name+'.'+uuid.uuid4().hex)
 fd=os.open(temporary,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,384)
 with os.fdopen(fd,'w') as stream:
  stream.write(contents); stream.flush(); os.fsync(stream.fileno())
 os.replace(temporary,path)
 assert path.read_text()==contents
 s=path.lstat(); assert stat.S_ISREG(s.st_mode) and s.st_uid==s.st_gid==0 and stat.S_IMODE(s.st_mode)==384
replace(authorized,contents)
replace(marker_path,json.dumps(marker,sort_keys=True))
'''


def validate_saved_snapshot(lease, xml, record):
    """Shared identity/isolation proof for restoration and current-guest probes."""
    root = ET.fromstring(xml)
    system.require(json.loads(root.findtext('description'))['baseline_sha256'] ==
                   lease.state['baseline_sha256'], 'online-snapshot:baseline-changed')
    domain = root.find('domain')
    system.require(domain is not None and domain.findtext('uuid') == lease.source.uuid
        and domain.findtext('description') == system.TAG + record['run'],
        'online-snapshot:domain-identity')
    layout = system.baseline.domain_layout(ET.tostring(domain, encoding='unicode'), lease.source.uuid)
    expected = dict(lease.capture.state['source']['layout'], source_shares=[])
    system.require(layout == expected, 'online-snapshot:source-changed')
    system.validate_private_vnc(domain)
    system.require(not any(domain.findall('devices/' + kind) for kind in
        ('filesystem', 'hostdev', 'channel', 'redirdev')),
        'online-snapshot:host-sharing')


@system.observed('Restoring the running app snapshot')
def restore(lease, record, *, maintenance=False):
    from app_snapshot import mode_mismatch
    lease.guard()
    system.require(mode_mismatch(lease.installed_xml, 'online') is None,
                   'online-snapshot:expired-or-invalid')
    snap = lease.source.domain.snapshotLookupByName(lease.installed_name, 0)
    system.require(snap.getXMLDesc(0) == lease.installed_xml,
                   'suite:snapshot-metadata-changed')
    validate_saved_snapshot(lease, lease.installed_xml, record)
    lease.capture.retire_vm_ownership()
    if maintenance:
        # Finish every refusal check before replacing an existing maintenance
        # identity. A rejected snapshot must leave that guest stoppable.
        from vm_control import save_owner
        if lease.state['phase'] == 'running':
            lease.state['run'] = uuid.uuid4().hex
            lease.ownership_run = lease.state['run']
        save_owner(lease)
    lease.state['domain_id'] = None
    lease.save('start-requested')
    started = time.monotonic()
    with lease.snapshot_status('Restoring', lease.installed_name):
        lease.source.domain.revertToSnapshot(snap,
            lease.source.api.VIR_DOMAIN_SNAPSHOT_REVERT_FORCE)
    system.log(f'online-snapshot:memory-restored seconds={time.monotonic() - started:.2f}')
    # Snapshot revert can recreate QEMU without refreshing the old virDomain
    # handle's cached ID. Resolve the pinned UUID again before recording it.
    lease.source.domain = lease.source.connection.lookupByUUIDString(lease.source.uuid)
    from vm_control import check_identity
    check_identity(lease.source, lease.source.uuid)
    lease.view.run = record['run']
    lease.view.domain_id = lease.source.domain.ID()
    system.require(lease.view.domain_id >= 0, 'start:identity-unavailable')
    lease.state['domain_id'] = lease.view.domain_id
    lease.guard()
    lease.source.domain.setMetadata(lease.source.api.VIR_DOMAIN_METADATA_DESCRIPTION,
        system.TAG + lease.state['run'], None, None,
        lease.source.api.VIR_DOMAIN_AFFECT_LIVE | lease.source.api.VIR_DOMAIN_AFFECT_CONFIG)
    lease.view.run = lease.state['run']
    lease.guard()
    lease.capture.begin_vm_ownership(lease)
    lease.save('running')
    from e2e_watch import attach
    attach(lease)
    reconnect_network(lease)
    return system.address(lease.source)


def network_link(lease):
    """Return the guarded live-only carrier updater for the one guest NIC."""
    lease.guard()
    domain = lease.source.domain
    interfaces = ET.fromstring(domain.XMLDesc(0)).findall('devices/interface')
    system.require(len(interfaces) == 1 and interfaces[0].get('type') == 'network',
                   'online-snapshot:network-layout')
    interface = interfaces[0]
    mac = interface.find('mac')
    network = interface.find('source')
    link = interface.find('link')
    system.require(mac is not None and re.fullmatch(
        r'(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}', mac.get('address', '')) is not None
        and network is not None and bool(network.get('network'))
        and (link is None or link.get('state') in ('up', 'down')),
        'online-snapshot:network-layout')
    state = 'up' if link is None else link.get('state')
    if link is None:
        link = ET.SubElement(interface, 'link')

    def update(state):
        lease.guard()
        link.set('state', state)
        domain.updateDeviceFlags(ET.tostring(interface, encoding='unicode'),
                                 lease.source.api.VIR_DOMAIN_AFFECT_LIVE)
        lease.guard()
        current = ET.fromstring(domain.XMLDesc(0)).findall('devices/interface')
        system.require(len(current) == 1
            and current[0].find('mac') is not None
            and current[0].find('mac').attrib == mac.attrib
            and current[0].find('link') is not None
            and current[0].find('link').get('state') == state,
            'online-snapshot:network-link-not-applied')
    return state, update


@contextmanager
def disconnected_network(lease):
    """Pay NetworkManager's carrier-loss grace once, before saving memory."""
    with system.operation('Disconnecting the VM network for a reusable snapshot'):
        state, update = network_link(lease)
        system.require(state == 'up', 'online-snapshot:network-already-down')
        try:
            update('down')
            # NetworkManager's default carrier-wait-timeout is six seconds.
            time.sleep(10)
            yield
        finally:
            update('up')


@system.observed('Renewing the restored VM network connection')
def reconnect_network(lease):
    """New snapshots already contain disconnected networking; reconnect now.

    Older snapshots retain DHCP state in RAM and need the carrier-loss grace
    on restore. Neither path relies on SSH or a potentially expired host lease.
    """
    state, update = network_link(lease)
    if state == 'down':
        update('up')
        system.log('online-snapshot:network-reconnected')
        return
    with disconnected_network(lease):
        pass
    system.log('online-snapshot:network-reconnected')


def connect_saved_transport(lease, directory, record, hostname):
    """Authenticate the current guest without restoring or changing its clock."""
    from vm_transport import Transport
    old = directory / 'snapshot-transport'
    old.mkdir(mode=0o700)
    key = old / 'ssh-key'
    key.write_text(record['private_key'])
    key.chmod(0o600)
    (old / 'known-hosts').write_text(f"{hostname} {record['host_key']}\n")
    config = dict(directory=str(old), hostname=hostname, run=record['run'],
                  domain_uuid=lease.source.uuid, domain_id=lease.view.domain_id)
    transport = Transport(config, lease.commands, guard=lambda _: lease.guard())
    transport.probe_ready()
    return transport


def saved_transport(lease, directory, record, hostname):
    transport = connect_saved_transport(lease, directory, record, hostname)
    # Resuming RAM may resume an old realtime clock. Correct it before tests
    # establish time expectations; no boot or customer action has begun.
    before = int(time.time())
    transport.call(['date', '--set', '@' + str(before)])
    # Setting time can be delayed by SSH or guest scheduling. Compare the
    # readback with its own host interval, not the earlier requested value.
    read_started = int(time.time())
    current = transport.call(['date', '+%s']).strip()
    system.require(current.isdigit() and read_started - 2 <= int(current) <= int(time.time()) + 2,
                   'online-snapshot:clock-not-corrected')
    return transport


@system.observed('Preparing fresh test inputs in the restored running VM')
def start(lease):
    from vm_transport import Transport
    started = time.monotonic()
    directory, record = lease.online_bootstrap
    hostname = restore(lease, record)
    transport = saved_transport(lease, directory, record, hostname)
    data = dict(run=lease.state['run'], baseline_sha256=lease.state['baseline_sha256'],
        preparation_sha256=lease.capture.state['guest']['preparation_record_sha256'],
        selected_inputs_sha256=system.baseline.digest(directory / 'input/selected-inputs.json'),
        package_sha256=system.baseline.digest(directory / 'input' /
            ('package.' + system.package_format(lease.capture.state['guest']))),
        public_key=(directory / 'ssh-key.pub').read_text(), old_public_key=record['public_key'])
    transport.call(['/usr/bin/python3', '-c', REBIND], input=system.baseline.encode(data))
    (directory / 'known-hosts').write_text(f"{hostname} {record['host_key']}\n")
    fresh = Transport(dict(transport.config, directory=str(directory), run=lease.state['run']),
                      lease.commands, guard=lambda _: lease.guard())
    fresh.probe_ready()
    verify_credentials(fresh, lease)
    system.log(f'online-snapshot:attempt-ready seconds={time.monotonic() - started:.2f}')
    lease.online_bootstrap = None


def verify_credentials(transport, lease):
    """Check the resumed fixture before graphical authentication is enabled."""
    import test_account_password
    import prepare_vm
    from watch_activity import secret
    password = test_account_password.read_password()
    secret(password)
    program = ('import ctypes,hmac,json,pathlib,stat,sys,threading\n'
               '_crypt_lock=threading.Lock()\n' + inspect.getsource(test_account_password.matches) + '''
data=json.load(sys.stdin)
for name in ('/etc/passwd','/etc/shadow'):
 p=pathlib.Path(name); s=p.lstat()
 assert p.resolve()==p and stat.S_ISREG(s.st_mode) and s.st_uid==0 and s.st_nlink==1
 assert s.st_size<=1048576
rows=[line.split(':') for line in pathlib.Path('/etc/passwd').read_text().splitlines()]
hashes=[line.split(':') for line in pathlib.Path('/etc/shadow').read_text().splitlines()]
assert all(len(row)==9 for row in hashes) and len({row[0] for row in hashes})==len(hashes)
for name,uid in data['accounts'].items():
 row=[r for r in rows if r[0]==name]; saved=[r for r in hashes if r[0]==name]
 assert len(row)==len(saved)==1 and len(row[0])==7
 assert row[0][2]==str(uid) and row[0][5]=='/home/'+name and row[0][6]==data['shell']
 assert matches(data['password'],saved[0][1])
''')
    data = dict(password=password, shell=prepare_vm.INTERACTIVE_SHELL,
        accounts={account.username: lease.capture.state['guest']['accounts'][account.username]['uid']
                  for account in prepare_vm.IDENTITIES})
    transport.call(['/usr/bin/python3', '-c', program], input=system.baseline.encode(data))
