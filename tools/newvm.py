"""Blank VM provisioning. The same finite worker runs locally or over SSH."""
import argparse
import fcntl
import base64
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tests/integration'))
import vm_config
from host_dispatch import tool_host


def confirm(message):
    try:
        answer = input(f'\033[31m{message} [y/N] \033[0m')
    except EOFError:
        answer = ''
    if answer.strip().lower() not in ('y', 'yes'):
        raise ValueError('Cancelled; registry and VM resources unchanged')


def provision(request):
    # Local and SSH workers use the invoking checkout's implementation.
    import fnmatch
    import json
    import os
    from pathlib import Path
    import shutil
    import stat
    import subprocess
    import sys
    import xml.etree.ElementTree as ET
    from test_storage import scratch_descriptors

    def run(args, **kwargs):
        kwargs['pass_fds'] = tuple(dict.fromkeys((*kwargs.get('pass_fds', ()),
                                                *scratch_descriptors())))
        result = subprocess.run(args, text=True, capture_output=True, timeout=120, **kwargs)
        if result.returncode:
            raise ValueError(f'{args[0]} failed: {result.stderr.strip() or result.stdout.strip()}')
        return result.stdout

    def virsh(*args, **kwargs):
        return run(['virsh', '-c', 'qemu:///system', *args], **kwargs)

    for command in ('virsh', 'qemu-img'):
        if shutil.which(command) is None:
            raise ValueError(f'Missing prerequisite on VM host: {command}')
    # Check the finite retirement route before creating or erasing any resources.
    run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
         '/usr/local/libexec/onpc-test-runner', 'pool-retire', '--help'],
        cwd=request['checkout'])
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
    existing = None
    if request['name'] in names:
        existing = ET.fromstring(virsh('dumpxml', request['name'], '--inactive'))
        if not request.get('overwrite_uuid'):
            return {'existing_uuid': existing.findtext('uuid'), 'disk': str(disk)}
        if existing.findtext('uuid') != request['overwrite_uuid']:
            raise ValueError('Existing VM identity changed; run newvm again')
        if request['name'] in virsh('list', '--name').splitlines():
            raise ValueError('Existing VM must be powered off before overwrite')
        sources = existing.findall('./devices/disk[@device="disk"]/source')
        if (len(sources) != 1 or sources[0].get('file') != str(disk) or
                existing.find('./os/nvram') is not None):
            raise ValueError('Overwrite requires one disk at the requested destination and no NVRAM')
        if virsh('snapshot-list', request['name'], '--name').strip():
            raise ValueError('Existing VM has snapshots; remove them through the maintained workflow first')
    def check_references():
        for name in filter(None, virsh('list', '--all', '--name').splitlines()):
            if existing is not None and name == request['name']:
                continue
            for options in ((), ('--inactive',)):
                domain = ET.fromstring(virsh('dumpxml', name, *options))
                for source in domain.findall('./devices/disk//source'):
                    path = source.get('file')
                    if path and Path(path).resolve() == disk.resolve():
                        raise ValueError(f'Disk destination is referenced by existing VM {name}: {disk}')
                if existing is not None:
                    for source in domain.findall('./devices/disk[@device="disk"]/source'):
                        if source.get('file'):
                            chain = json.loads(run(['qemu-img', 'info', '--output=json',
                                                    '--backing-chain', '--force-share', source.get('file')]))
                            if any(Path(image['filename']).resolve() == disk.resolve() for image in chain):
                                raise ValueError(f'Disk is in the backing chain of VM {name}: {disk}')
    check_references()
    domain = ET.fromstring(request['xml'])
    domain.find('./devices/disk[@device="disk"]/source').set('file', str(disk))
    domain.find('./devices/disk[@device="cdrom"]/source').set('file', str(iso))
    xml = ET.tostring(domain, encoding='unicode')
    keeper = None
    descriptor = None
    try:
        if existing is not None:
            keeper = subprocess.Popen(
                ['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                 '/usr/local/libexec/onpc-test-runner', 'pool-provision',
                 request['name'], request['overwrite_uuid']],
                cwd=request['checkout'], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
            receipt = keeper.stdout.readline(1024)
            if not receipt:
                raise ValueError(f'VM checkout failed (status {keeper.wait()}); '
                                 'refresh VM-host helpers with ./setup.sh --test-tools-only')
            if json.loads(receipt)['checkout'].split(':', 1)[0] != request['overwrite_uuid']:
                raise ValueError('VM checkout returned a different identity')
            # Queueing is not ownership: revalidate the exact domain definition.
            if ET.tostring(ET.fromstring(virsh('dumpxml', request['name'], '--inactive'))) != ET.tostring(existing):
                raise ValueError('VM definition changed while waiting for checkout; run newvm again')
            if request['name'] in virsh('list', '--name').splitlines():
                raise ValueError('Existing VM is active; overwrite refused')
            if virsh('snapshot-list', request['name'], '--name').strip():
                raise ValueError('Existing VM acquired snapshots while waiting; overwrite refused')
            check_references()
            descriptor = os.open(disk, os.O_RDWR | os.O_NOFOLLOW)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Overwrite requires a regular disk file with one hard link')
            run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                 '/usr/local/libexec/onpc-test-runner',
                 '--vm-checkout=' + json.loads(receipt)['checkout'],
                 'pool-retire', request['name'], request['overwrite_uuid']], cwd=request['checkout'])
            virsh('undefine', request['name'])
        else:
            if request.get('overwrite_uuid'):
                raise ValueError('Confirmed VM disappeared; run newvm again')
            # Never adopt an unconfirmed existing file or dangling symlink.
            descriptor = os.open(disk, os.O_RDWR | os.O_CREAT | os.O_EXCL, 0o644)
        run(['qemu-img', 'create', '-f', 'qcow2', f'/proc/self/fd/{descriptor}',
             request['size'] + 'G'], pass_fds=(descriptor,))
        virsh('define', '/dev/stdin', '--validate', input=xml)
        actual = ET.fromstring(virsh('dumpxml', request['name'], '--inactive'))
        if actual.findtext('uuid') != request['uuid']:
            raise ValueError('Created domain UUID does not match')
        # A removed domain may still have completed provenance under its name.
        # Retire it before accepting this new lifecycle, then clear installed pins.
        run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
             '/usr/local/libexec/onpc-test-runner', 'pool-retire', request['name']],
            cwd=request['checkout'])
        run([str(Path(request['checkout']) / 'setup.sh'), '--test-tools-only'],
            cwd=request['checkout'])
    except BaseException:
        print(f'newvm: creation interrupted/failed; preserve and inspect disk {disk} '
              f'and domain {request["name"]} before retrying', file=sys.stderr)
        raise
    finally:
        if descriptor is not None:
            os.close(descriptor)
        if keeper is not None:
            keeper.stdin.close()
            keeper.stdout.close()
            keeper.wait()
    return {'disk': str(disk), 'iso': str(iso), 'uuid': request['uuid']}


def create(name, host_name, family_name, *, root=ROOT):
    config = root / 'config/environment.json'
    # A directory lock remains stable across atomic registry replacements.
    descriptor = os.open(config.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        original = config.read_bytes()
        document = vm_config.read_document(config, validate_agent=False)
        owner = tool_host(root, document)
        hosts = vm_config.host_registry(document)
        registered = vm_config.registry(config)
        vm_config.validate_name(name)
        vm_config.validate_name(host_name)
        existing = registered.get(name)
        if existing is None and any(vm.id == name for vm in registered.values()):
            raise ValueError(f'VM ID already registered: {name}')
        if existing is not None:
            vm_config.require_branch(existing, vm_config.current_branch())
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
        request['checkout'] = (str(root) if host_name == owner.name else next(
            (b['repo_root'] for b in document.get('branches', []) if b['host'] == host_name), ''))
        if not request['checkout']:
            raise ValueError('VM host requires a configured branch checkout and refreshed VM-host helpers')
        if existing is not None:
            confirm(f'VM {name} is already registered on {existing.host.name} '
                    f'in family {existing.family}. Overwrite its registry entry with '
                    f'host {host_name}, family {family_name}, enabled=false?')
            for group in document['families']:
                group['vms'] = [vm for vm in group['vms'] if vm['name'] != name]
        entry = dict(id=(existing.id if existing is not None and existing.id else
                         str(max([int(vm.id) for vm in registered.values() if vm.id] + [0]) + 1)),
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
            def execute():
                if host_name == owner.name:
                    return provision(request)
                from remote_sources import RemoteVM
                from regression_process import Control
                import test_launcher
                output = bytearray()
                def collect(data):
                    if len(output) + len(data) > 65536:
                        raise ValueError('newvm: oversized provisioning response')
                    output.extend(data)
                encoded = base64.b64encode(json.dumps(request).encode()).decode('ascii')
                with Control().installed() as control:
                    status = RemoteVM(root, host=hosts[host_name]).run(control,
                        ['/usr/bin/python3', '-IBu', str(root / 'tools/newvm'),
                         '--provision-worker', encoded],
                        env=test_launcher.environment(root), output=collect,
                        stderr_output=lambda data: sys.stderr.buffer.write(data), wait_on_cancel=True)
                if status:
                    raise ValueError('SSH creation failed; inspect remote resources before retrying')
                return json.loads(output)
            result = execute()
            if 'existing_uuid' in result:
                confirm(f'VM {name} already exists in libvirt on {host_name}. '
                        f'Overwrite it and ERASE ALL DATA on {result["disk"]}?')
                request['overwrite_uuid'] = result['existing_uuid']
                result = execute()
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
    if len(sys.argv) == 3 and sys.argv[1] == '--provision-worker':
        if vm_config.remote_origin() is None:
            raise ValueError('newvm: transferred source worker only')
        request = json.loads(base64.b64decode(sys.argv[2], validate=True))
        request['checkout'] = str(ROOT)
        print(json.dumps(provision(request)), flush=True)
        return 0
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--name', required=True)
    parser.add_argument('--host', required=True, help='Existing host name in config/environment.json')
    parser.add_argument('--family', required=True, help='Existing family name in config/environment.json')
    args = parser.parse_args()
    try:
        create(args.name, args.host, args.family)
        print(f'\033[32mnewvm: SUCCESS: {args.name} created; powered off, enabled=false\033[0m', flush=True)
        return 0
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f'newvm: {error}', file=sys.stderr)
        return 1
