"""Install the selected desktop OS and verify its first boot under a VM checkout."""

from contextlib import contextmanager
import copy
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET

from test_account_password import read_password

ROOT = Path(__file__).resolve().parents[1]
GUEST = '/var/lib/onpc-newvm'
SERVICE = 'onpc-newvm-first-boot.service'
TIMEZONE = 'America/Los_Angeles'
REAL_NAME = 'Puffy Slippers Tech LLC'
USERNAME = 'edgar'
SETUP = '/usr/local/libexec/onpc-setup'
BOOT_TIMEOUT = 90 * 60


def command(*args, input=None, pass_fds=()):
    result = subprocess.run(args, input=input, capture_output=True, text=True,
                            pass_fds=pass_fds, timeout=120, env={**os.environ, 'LC_ALL': 'C'})
    if result.returncode:
        raise ValueError(f'{args[0]} exited with status {result.returncode}: {result.stderr.strip()}')
    return result.stdout


def virsh(*args, input=None):
    return command('virsh', '-c', 'qemu:///system', *args, input=input)


def check_host():
    from dev_privileges import check

    for program in ('xorriso', 'openssl'):
        if shutil.which(program) is None:
            raise ValueError(f'Missing unattended installation prerequisite on VM host: {program}')
    read_password()
    check(SETUP)


def boot_options(iso, distribution, version):
    common = 'console=ttyS0,115200n8'
    info = command('xorriso', '-indev', str(iso), '-pvd_info')
    label = re.search(r'^Volume Id\s*:\s*(.+)$', info, re.MULTILINE)
    if distribution == 'ubuntu':
        if label is None or not label[1].startswith(f'Ubuntu {version}'):
            raise ValueError(f'Expected Ubuntu {version} Desktop installation media: {iso}')
        return '/casper/vmlinuz', '/casper/initrd', f'autoinstall ds=nocloud noprompt {common}'
    expected = f'Fedora-E-dvd-x86_64-{version}'
    if label is None or label[1] != expected:
        raise ValueError(f'Expected Fedora {version} Everything netinstall media: {iso}')
    return ('/images/pxeboot/vmlinuz', '/images/pxeboot/initrd.img',
            f'inst.stage2=hd:LABEL={expected} inst.ks=hd:LABEL=ONPCKS:/ks.cfg '
            f'inst.nosave=all_ks inst.cmdline ip=dhcp {common}')


def first_boot(distribution, version, hostname, identifier):
    unit = f"""[Unit]
Description=Update the newly provisioned VM
Wants=network-online.target
After=network-online.target
Before=display-manager.service

[Service]
Type=oneshot
TimeoutStartSec=75min
ExecStart=/usr/bin/python3 -B {GUEST}/newvm_guest.py {distribution} {version} {hostname} {identifier}
ExecStopPost=/usr/bin/systemctl --no-block poweroff

[Install]
WantedBy=multi-user.target
"""
    path = '/etc/systemd/system/' + SERVICE
    guest_updates = ROOT / 'tests/integration/guest_updates.py'
    script = [f'install -d -m 0700 {GUEST}']
    for target, contents in (
        (GUEST + '/newvm_guest.py', (ROOT / 'tools/newvm_guest.py').read_text()),
        (GUEST + '/guest_updates.py', guest_updates.read_text()),
        (path, unit),
    ):
        script.append(f"cat > {target} <<'ONPC_NEWVM_PAYLOAD'\n{contents.rstrip()}\nONPC_NEWVM_PAYLOAD")
    if distribution == 'fedora':
        script.append(f'restorecon -RF {GUEST} {path}')
    script.append(f'systemctl enable {SERVICE}')
    return 'set -eu\n' + '\n'.join(script) + '\n'


def installer_answers(distribution, version, hostname, mac, identifier, password_hash):
    script = first_boot(distribution, version, hostname, identifier)
    installed = f"printf '%s\\n' 'ONPC-NEWVM-INSTALLED {identifier}' > /dev/ttyS0"
    if distribution == 'ubuntu':
        config = {
            'version': 1,
            'refresh-installer': {'update': False},
            'network': {'version': 2, 'renderer': 'NetworkManager', 'ethernets': {
                'wired': {'match': {'macaddress': mac}, 'dhcp4': True}}},
            'storage': {'layout': {'name': 'direct', 'match': {'path': '/dev/vda'}}},
            'drivers': {'install': True},
            'identity': {'realname': REAL_NAME, 'hostname': hostname,
                         'username': USERNAME, 'password': password_hash},
            'timezone': TIMEZONE,
            'shutdown': 'poweroff',
            'late-commands': [
                'curtin in-target -- /bin/sh -c ' + shlex.quote(script),
                installed,
            ],
        }
        return 'cidata', {
            'meta-data': f'instance-id: {identifier}\nlocal-hostname: {hostname}\n',
            'user-data': '#cloud-config\n' + json.dumps({'autoinstall': config}) + '\n',
        }

    repository = f'https://download.fedoraproject.org/pub/fedora/linux/releases/{version}/Everything/x86_64/os/'
    kickstart = f"""cmdline
lang en_US.UTF-8
keyboard us
timezone {TIMEZONE} --utc
network --device={mac} --bootproto=dhcp --activate --hostname={hostname}
url --url={repository}
ignoredisk --only-use=vda
zerombr
clearpart --all --initlabel --drives=vda
autopart --type=btrfs
bootloader --boot-drive=vda
rootpw --lock
user --name={USERNAME} --groups=wheel --gecos="{REAL_NAME}" --iscrypted --password={password_hash}
firstboot --disable
poweroff

%packages
@^workstation-product-environment
dbus-daemon
fedora-workstation-repositories
fedora-third-party
%end

%post --erroronfail
{script}grep -qx 'VARIANT_ID=workstation' /etc/os-release || grep -qx 'VARIANT_ID="workstation"' /etc/os-release
{installed}
%end
"""
    return 'ONPCKS', {'ks.cfg': kickstart}


def make_seed(stage, vm, target, mac, identifier):
    from test_storage import scratch_descriptors, scratch_directory

    # Read from the VM host's private configuration and pass only the hash
    # to the installers. Neither plaintext nor hash is passed in host argv.
    value = command('openssl', 'passwd', '-6', '-stdin', input=read_password() + '\n').strip()
    if re.fullmatch(r'\$6\$[./a-zA-Z0-9]{1,16}\$[./a-zA-Z0-9]{86}', value) is None:
        raise ValueError('Could not generate the installer password hash')
    label, files = installer_answers(target.distribution, target.version, vm.hostname, mac,
                                     identifier, value)
    seed = stage / 'seed.iso'
    seed.touch(mode=0o600, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix='newvm-seed-', dir=scratch_directory()) as scratch:
        for filename, contents in files.items():
            (Path(scratch) / filename).write_text(contents)
        command('xorriso', '-as', 'mkisofs', '-quiet', '-R', '-V', label, '-o', str(seed),
                scratch, pass_fds=scratch_descriptors())
    return seed


def check_media_layout(xml):
    devices = xml.find('devices')
    disk = xml.find('./devices/disk[@device="disk"]/target')
    if (devices is None or len(devices.findall('interface')) != 1 or
            disk is None or disk.get('dev') != 'vda' or
            len(devices.findall('disk')) != 2 or len(devices.findall('serial')) != 1 or
            xml.find('./os/kernel') is not None or xml.find('./os/initrd') is not None or
            xml.find('./os/cmdline') is not None):
        raise ValueError('Unattended installation needs one vda disk, one CD-ROM, one NIC and one serial port')


def configure_install(boot, stage, seed, options):
    os_element = boot.find('os')
    for key, value in (('kernel', str(stage / 'vmlinuz')),
                       ('initrd', str(stage / 'initrd')), ('cmdline', options[2])):
        ET.SubElement(os_element, key).text = value
    devices = boot.find('devices')
    cdrom = devices.find('./disk[@device="cdrom"]/target')
    drive = ET.SubElement(devices, 'disk', type='file', device='cdrom')
    ET.SubElement(drive, 'driver', name='qemu', type='raw')
    ET.SubElement(drive, 'source', file=str(seed))
    ET.SubElement(drive, 'target', dev='sdc' if cdrom.get('dev') == 'sdb' else 'sdb', bus='sata')
    ET.SubElement(drive, 'readonly')


def boot_and_wait(identifier, xml, log, witness, phase):
    deadline = time.monotonic() + BOOT_TIMEOUT
    # Start the inactive persistent domain with one-time XML. A later ordinary
    # start must never inherit the unattended installer or its answer media.
    virsh('create', '/dev/stdin', '--validate', input=ET.tostring(xml, encoding='unicode'))
    while time.monotonic() < deadline:
        state = virsh('domstate', identifier, '--reason').strip()
        if state.startswith('shut off'):
            if state != 'shut off (shutdown)':
                raise ValueError(f'{phase}: unexpected power-off reason: {state}')
            with log.open('rb') as stream:
                stream.seek(max(0, os.fstat(stream.fileno()).st_size - 131072))
                if witness.encode('ascii') not in stream.read().splitlines():
                    raise ValueError(f'{phase}: guest shut down without confirming success')
            return
        time.sleep(min(5, max(0, deadline - time.monotonic())))
    raise ValueError(f'{phase}: guest did not shut down within {BOOT_TIMEOUT // 60} minutes')


@contextmanager
def staging(disk, identifier):
    # These files are directly opened by system QEMU. Stage only its per-VM
    # media beside the disk; credentials in the seed remain mode 0600.
    stage = Path(tempfile.mkdtemp(prefix=f'.newvm-{identifier}-', dir=disk.parent))
    stage.chmod(0o711)
    try:
        yield stage
    except BaseException:
        print(f'newvm: preserved provisioning files for {identifier} at {stage}',
              file=sys.stderr, flush=True)
        raise
    else:
        for name in ('vmlinuz', 'initrd', 'serial.log'):
            (stage / name).unlink()
        stage.rmdir()


def install(vm, identifier):
    target = vm.require_build_target()
    def require_off():
        if virsh('domstate', identifier).strip() != 'shut off':
            raise ValueError('Unattended installation requires the same powered-off VM')

    require_off()
    original = ET.fromstring(virsh('dumpxml', identifier, '--inactive'))
    check_media_layout(original)
    disk = original.find('./devices/disk[@device="disk"]/source')
    cdrom = original.find('./devices/disk[@device="cdrom"]')
    source = cdrom.find('source')
    if (original.findtext('name') != vm.name or disk is None or
            disk.get('file') != str(vm.disk_anchor) or source is None or not source.get('file')):
        raise ValueError('VM definition changed before unattended installation')
    extents = json.loads(command('qemu-img', 'map', '--output=json', str(vm.disk_anchor)))
    if not extents or any(not extent['zero'] for extent in extents):
        raise ValueError('Unattended installation requires a blank disk')
    iso = Path(source.get('file'))
    options = boot_options(iso, target.distribution, target.version)
    interface_mac = original.find('./devices/interface/mac')
    mac = interface_mac.get('address', '') if interface_mac is not None else ''
    if re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}', mac) is None:
        raise ValueError('Missing or invalid VM MAC address')
    with staging(vm.disk_anchor, identifier) as stage:
        for member, name in zip(options[:2], ('vmlinuz', 'initrd'), strict=True):
            command('xorriso', '-indev', str(iso), '-osirrox', 'on', '-extract',
                    member, str(stage / name))
        seed = make_seed(stage, vm, target, mac, identifier)
        log = stage / 'serial.log'
        log.touch(mode=0o600, exist_ok=False)
        boot = copy.deepcopy(original)
        reboot = boot.find('on_reboot')
        if reboot is None:
            reboot = ET.SubElement(boot, 'on_reboot')
        reboot.text = 'destroy'
        devices = boot.find('devices')
        for device in (*devices.findall('filesystem'), *devices.findall('console')):
            devices.remove(device)
        serial = devices.find('serial')
        serial.set('type', 'file')
        for child in serial.findall('source'):
            serial.remove(child)
        ET.SubElement(serial, 'source', path=str(log), append='on')

        def eject(xml):
            drive = xml.find('./devices/disk[@device="cdrom"]')
            drive.remove(drive.find('source'))
            if (order := drive.find('boot')) is not None:
                drive.remove(order)
            drive = xml.find('./devices/disk[@device="disk"]/boot')
            if drive is not None:
                drive.set('order', '1')

        installer = copy.deepcopy(boot)
        configure_install(installer, stage, seed, options)
        print(f'newvm: installing {target.distribution} {target.version} on {vm.name}', flush=True)
        boot_and_wait(identifier, installer, log, 'ONPC-NEWVM-INSTALLED ' + identifier, 'OS installation')
        require_off()
        eject(original)
        virsh('define', '/dev/stdin', '--validate', input=ET.tostring(original, encoding='unicode'))
        eject(boot)
        seed.unlink()
        print(f'newvm: booting {vm.name} from disk and applying updates', flush=True)
        boot_and_wait(identifier, boot, log, 'ONPC-NEWVM-UPDATED ' + identifier, 'First-boot updates')
        actual = ET.fromstring(virsh('dumpxml', identifier, '--inactive'))
        if actual.find('./devices/disk[@device="cdrom"]/source') is not None:
            raise ValueError('Installer media is still attached after provisioning')
