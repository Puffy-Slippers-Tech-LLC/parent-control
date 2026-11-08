"""Blank VM provisioning. The same finite worker runs locally or over SSH."""
import argparse
import fcntl
import inspect
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import vm_config


def provision(request):
    # Self-contained so the identical implementation can be sent to an SSH host.
    import fnmatch
    import os
    from pathlib import Path
    import shutil
    import subprocess
    import sys
    import xml.etree.ElementTree as ET

    def run(args, **kwargs):
        result = subprocess.run(args, text=True, capture_output=True, timeout=120, **kwargs)
        if result.returncode:
            raise ValueError(f'{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}')
        return result.stdout

    def virsh(*args, **kwargs):
        return run(['virsh', '-c', 'qemu:///system', *args], **kwargs)

    for command in ('virsh', 'qemu-img'):
        if shutil.which(command) is None:
            raise ValueError(f'Missing prerequisite on VM host: {command}')
    root = Path(request['root'])
    if not root.is_dir() or root.is_symlink():
        raise ValueError(f'VM directory must already exist and not be a symlink: {root}')
    iso_dir = root / 'ISO'
    matches = sorted(p for p in iso_dir.iterdir()
                     if fnmatch.fnmatchcase(p.name, request['iso']))
    if len(matches) != 1:
        raise ValueError(f'Expected exactly one ISO matching {iso_dir / request["iso"]}; '
                         f'found {len(matches)}: {", ".join(p.name for p in matches) or "none"}')
    iso = matches[0]
    if not iso.is_file() or iso.is_symlink():
        raise ValueError(f'ISO must be a regular file, not a symlink: {iso}')
    disk = root / (request['name'] + '.qcow2')
    # Check every domain, including inactive ones, before reserving any storage.
    names = virsh('list', '--all', '--name').splitlines()
    if request['name'] in names:
        raise ValueError(f'VM already exists in libvirt: {request["name"]}')
    for name in filter(None, names):
        domain = ET.fromstring(virsh('dumpxml', name))
        for source in domain.findall('./devices/disk/source'):
            if source.get('file') and Path(source.get('file')).resolve() == disk.resolve():
                raise ValueError(f'Disk destination is referenced by existing VM {name}: {disk}')
    domain = ET.fromstring(request['xml'])
    domain.find('./devices/disk[@device="disk"]/source').set('file', str(disk))
    domain.find('./devices/disk[@device="cdrom"]/source').set('file', str(iso))
    xml = ET.tostring(domain, encoding='unicode')
    # O_EXCL refuses existing files and dangling symlinks. Preserve the reserved
    # file on any later failure: never delete something libvirt may have adopted.
    descriptor = os.open(disk, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    os.close(descriptor)
    try:
        run(['qemu-img', 'create', '-f', 'qcow2', str(disk), request['size'] + 'G'])
        virsh('define', '/dev/stdin', '--validate', input=xml)
        actual = ET.fromstring(virsh('dumpxml', request['name'], '--inactive'))
        if actual.findtext('uuid') != request['uuid']:
            raise ValueError('Created domain UUID does not match')
    except BaseException:
        print(f'newvm: creation interrupted/failed; preserve and inspect disk {disk} '
              f'and domain {request["name"]} before retrying', file=sys.stderr)
        raise
    return {'disk': str(disk), 'iso': str(iso), 'uuid': request['uuid']}


def create(name, host_name, family_name, *, root=ROOT):
    config = root / 'config/environment.json'
    # A directory lock remains stable across atomic registry replacements.
    descriptor = os.open(config.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        original = config.read_bytes()
        document = vm_config.read_document(config, validate_agent=False)
        registered = vm_config.registry(config)
        vm_config.validate_name(name)
        vm_config.validate_name(host_name)
        if name in registered or any(vm.id == name for vm in registered.values()):
            raise ValueError(f'VM name/ID already registered: {name}')
        host = next((h for h in document['hosts'] if h['name'] == host_name), None)
        family = next((f for f in document['families'] if f['family'] == family_name), None)
        if host is None:
            raise ValueError(f'Unknown host: {host_name}')
        if family is None:
            raise ValueError(f'Unknown family: {family_name}')
        if 'virt-manager' not in host or 'iso' not in family:
            raise ValueError('Host requires virt-manager and family requires iso configuration')
        template = root / 'config' / (host_name + '-vm-template.xml')
        domain = ET.fromstring(template.read_text())
        capacity = domain.find('./metadata/{urn:onpc:newvm}disk')
        size = capacity.get('size-gib', '') if capacity is not None else ''
        if not size.isdecimal() or not 1 <= int(size) <= 65536:
            raise ValueError('Template disk size-gib must be between 1 and 65536')
        if (domain.find('uuid') is not None or domain.find('name') is None or
                len(domain.findall('./devices/disk[@device="disk"]')) != 1 or
                len(domain.findall('./devices/disk[@device="cdrom"]')) != 1 or
                domain.find('./devices/disk[@device="disk"]/source') is None or
                domain.find('./devices/disk[@device="cdrom"]/source') is None or
                domain.find('./os/loader') is not None or domain.find('./os/nvram') is not None):
            raise ValueError('Template requires name, one disk and one CD-ROM with sources, '
                             'and BIOS; omit UUID')
        identifier = str(uuid.uuid4())
        domain.find('name').text = name
        ET.SubElement(domain, 'uuid').text = identifier
        for interface in domain.findall('./devices/interface'):
            for mac in interface.findall('mac'):
                interface.remove(mac)  # libvirt allocates a fresh address
        request = dict(name=name, root=host['virt-manager'], iso=family['iso'],
                       xml=ET.tostring(domain, encoding='unicode'), uuid=identifier, size=size)
        entry = dict(id=str(max([int(vm.id) for vm in registered.values() if vm.id] + [0]) + 1),
                     name=name, enabled='false', host=host_name,
                     disk_anchor=str(Path(host['virt-manager']) / (name + '.qcow2')), owning_branch='')
        family['vms'].append(entry)
        updated = (json.dumps(document, indent=2) + '\n').encode()
        # Reserve registry staging before any external mutation.
        fd, staging = tempfile.mkstemp(prefix='.environment-', suffix='.json', dir=config.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(staging, config.stat().st_mode & 0o777)
            vm_config.registry(Path(staging))
            print(f'newvm: creating {name} on {host_name}; powered off, registry disabled', flush=True)
            if host['transport'] == 'local':
                result = provision(request)
            else:
                source = ('import json\n' + inspect.getsource(provision) +
                          '\nprint(json.dumps(provision(' + repr(request) + ')))\n')
                command = ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
                           '-p', str(host.get('ssh_port', 22)), host_name,
                           shlex.join(['python3', '-c', 'import sys; exec(sys.stdin.read())'])]
                completed = subprocess.run(command, input=source, text=True, capture_output=True,
                                           timeout=600)
                if completed.returncode:
                    raise ValueError('SSH creation failed; inspect remote resources before retrying: ' +
                                     completed.stderr.strip())
                result = json.loads(completed.stdout)
            print(f'newvm: domain {name} ({identifier}) and disk {result["disk"]} created; '
                  'publishing disabled registry entry', flush=True)
            if config.read_bytes() != original:
                raise ValueError('Registry changed during creation; VM/disk preserved; register manually')
            os.replace(staging, config)
            print(f'Created {name}: disk={result["disk"]}, ISO={result["iso"]}, '
                  f'UUID={result["uuid"]}; enabled=false')
            return result
        finally:
            if os.path.exists(staging):
                os.unlink(staging)
    finally:
        os.close(descriptor)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--name', required=True)
    parser.add_argument('--host', required=True, help='Existing host name in config/environment.json')
    parser.add_argument('--family', required=True, help='Existing family name in config/environment.json')
    args = parser.parse_args()
    try:
        create(args.name, args.host, args.family)
        return 0
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f'newvm: {error}', file=sys.stderr)
        return 1
