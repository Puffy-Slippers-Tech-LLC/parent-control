"""Provision and prepare a desktop VM, or create a powered-off blank VM."""
import argparse
import fcntl
import base64
import json
import os
from pathlib import Path
import re
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
    from vm_snapshots import replacement_snapshots, undefine_for_replacement

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
    if install := request.get('install'):
        from newvm_install import boot_options, check_host, check_media_layout
        check_host()
        boot_options(iso, *install)
        check_media_layout(ET.fromstring(request['xml']))
    disk = Path(request['disk'])
    if not disk.parent.is_dir() or disk.parent.is_symlink():
        raise ValueError(f'Disk directory must already exist and not be a symlink: {disk.parent}')
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
        disks = existing.findall('./devices/disk[@device="disk"]')
        if (len(disks) != 1 or disks[0].get('type') != 'file' or disks[0].find('source') is None or
                disks[0].find('source').get('file') != str(disk) or
                disks[0].find('backingStore/source') is not None or
                disks[0].find('target') is None or not disks[0].find('target').get('dev') or
                disks[0].find('driver') is None or disks[0].find('driver').get('type') != 'qcow2' or
                existing.find('./os/nvram') is not None):
            raise ValueError('Overwrite requires one standalone QCOW2 disk at the requested destination and no NVRAM')
        target = disks[0].find('target').get('dev')
        snapshots = replacement_snapshots(virsh, request['overwrite_uuid'], disk, target)
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
            check_references()
            descriptor = os.open(disk, os.O_RDWR | os.O_NOFOLLOW)
            info = os.fstat(descriptor)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('Overwrite requires a regular disk file with one hard link')
            image = json.loads(run(['qemu-img', 'info', '--output=json', '-f', 'qcow2',
                                    f'/proc/self/fd/{descriptor}'], pass_fds=(descriptor,)))
            specific = image.get('format-specific', {}).get('data', {})
            if (image.get('backing-filename') or image.get('encrypted') or
                    any(specific.get(key) for key in ('data-file', 'encrypt', 'corrupt'))):
                raise ValueError('Overwrite requires a standalone QCOW2 disk without external data')
            if replacement_snapshots(virsh, request['overwrite_uuid'], disk, target) != snapshots:
                raise ValueError('Existing VM snapshots changed while waiting; overwrite refused')
            run(['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd',
                 '/usr/local/libexec/onpc-test-runner',
                 '--vm-checkout=' + json.loads(receipt)['checkout'],
                 'pool-retire', request['name'], request['overwrite_uuid']], cwd=request['checkout'])
            undefine_for_replacement(virsh, request['overwrite_uuid'], disk, target, snapshots)
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
             '/usr/local/libexec/onpc-test-runner', 'pool-retire', request['name'], request['uuid']],
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


def format_environment(document):
    """Keep registry rows and agent presets on one line, as in the source config."""
    def render(value, path=()):
        if isinstance(value, dict):
            compact = (path in (('agents', 'tools'), ('vm_configs',)) or path[-1:] == ('defaults',))
            if path[-1:] == ('capacity_fallbacks',) and value:
                return '{ ' + json.dumps(value)[1:-1] + ' }'
            rows = []
            for key, item in value.items():
                encoded = ('{ ' + json.dumps(item)[1:-1] + ' }'
                           if compact and isinstance(item, dict) else render(item, path + (key,)))
                rows.append('  ' * (len(path) + 1) + json.dumps(key) + ': ' + encoded)
            return '{\n' + ',\n'.join(rows) + '\n' + '  ' * len(path) + '}' if rows else '{}'
        if isinstance(value, list):
            rows = [('  ' * (len(path) + 1) +
                     ('{ ' + json.dumps(item)[1:-1] + ' }'
                      if path[-1:] in (('branches',), ('launchers',), ('vms',))
                      and isinstance(item, dict) else render(item, path + (index,))))
                    for index, item in enumerate(value)]
            return '[\n' + ',\n'.join(rows) + '\n' + '  ' * len(path) + ']' if rows else '[]'
        return json.dumps(value)

    return render(document) + '\n'


def run_remote(root, host, args, *, output=None):
    from remote_sources import RemoteVM
    from regression_process import Control
    import test_launcher

    with Control().installed() as control:
        status = RemoteVM(root, host=host).run(control,
            ['/usr/bin/python3', '-IBu', str(root / 'tools/newvm'), *args],
            env=test_launcher.environment(root), output=output,
            stderr_output=lambda data: sys.stderr.buffer.write(data), wait_on_cancel=True)
    if status:
        raise ValueError(f'newvm: operation failed on {host.name} (status {status})')


def install_and_prepare(root, vm, identifier):
    from dev_privileges import check
    from host_disk import operation
    import newvm_install
    import test_activity
    import test_source
    from test_storage import scratch_descriptors
    from vm_pool import arguments, reservation

    if vm_config.select(vm.name) != vm:
        raise ValueError('VM registry entry changed before unattended installation')
    check(newvm_install.SETUP)
    with reservation(vm.name) as receipt, test_activity.activity(root, named_vm=True):
        if receipt.split(':', 1)[0] != identifier:
            raise ValueError('VM UUID changed before unattended installation')
        with operation('Installing and updating the guest OS'):
            newvm_install.install(vm, identifier)
        print(f'newvm: preparing the baseline and current app snapshot for {vm.name}', flush=True)
        with test_source.reader(root):
            result = subprocess.run(
                ['/usr/bin/pkexec', '--disable-internal-agent', '--keep-cwd', newvm_install.SETUP,
                 *arguments(), 'prepare-vm', '--mode', 'manual', '--y', '--vm', vm.name],
                cwd=root, pass_fds=scratch_descriptors(), check=False,
                env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin', 'LANG': 'C.UTF-8'})
            if result.returncode:
                raise ValueError(f'Manual preparation failed (status {result.returncode})')
    with test_source.reader(root):
        result = subprocess.run([str(root / 'setup.sh'), '--test-tools-only'], cwd=root,
                                pass_fds=scratch_descriptors(), check=False)
        if result.returncode:
            raise ValueError(f'Test tool refresh failed (status {result.returncode})')


def create(vm_id, host_name, family_name, *, profile_name=None, blank=False, root=ROOT):
    if len(vm_id) > vm_config.MAX_NAME_LENGTH or not re.fullmatch(r'[1-9][0-9]*', vm_id):
        raise ValueError(f'VM ID must be a positive decimal integer of at most '
                         f'{vm_config.MAX_NAME_LENGTH} digits')
    config = root / 'config/environment.json'
    # A directory lock remains stable across atomic registry replacements.
    descriptor = os.open(config.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        original = config.read_bytes()
        document = vm_config.read_document(config, validate_agent=False)
        if 'hosts' not in document:
            raise ValueError('configure provisioning hosts in config/environment.json')
        owner = tool_host(root, document)
        hosts = vm_config.host_registry(document)
        registered = vm_config.parse_configuration(document)[1]
        family = vm_config.family_selectors(document).get(family_name.casefold())
        if family is None:
            raise ValueError(f'Unknown family: {family_name}')
        family_name = family['family']
        profiles = vm_config.vm_profiles(document)
        entry = dict(id=int(vm_id))
        default_profile = family['parent_config']
        if profile_name is not None and profile_name != default_profile:
            entry['parent_config'] = profile_name
        if host_name is not None:
            entry['host'] = vm_config.validate_name(host_name)
        effective = vm_config.resolve_vm_entry(entry, family, profiles)
        if 'host' in entry:
            inherited = {key: value for key, value in entry.items() if key != 'host'}
            try:
                if vm_config.resolve_vm_entry(inherited, family, profiles) == effective:
                    entry = inherited
            except ValueError:
                pass  # The explicit host can satisfy another property's template.
        if 'name' not in effective:
            raise ValueError('The selected VM profile must supply a name')
        vm = vm_config.validate_entry(effective, family, hosts)
        name, host_name = vm.name, vm.host.name
        existing = registered.get(name)
        if any(vm.id == vm_id and vm.name != name for vm in registered.values()):
            raise ValueError(f'VM ID already registered: {vm_id}')
        if existing is not None:
            if existing.id != vm_id:
                raise ValueError(f'VM name already registered with a different ID: {name}')
            vm_config.require_branch(existing, vm_config.current_branch())
        host = next(h for h in document['hosts'] if h['name'] == host_name)
        if 'virt-manager' not in host:
            raise ValueError('Host requires virt-manager configuration')
        if vm.owning_branch:
            vm_config.require_branch(vm, vm_config.current_branch())
        enabled = 'true' if vm.enabled else 'false'
        iso = vm.iso if blank else vm.install_iso or vm.iso
        if iso is None or vm.vm_config_xml is None:
            raise ValueError('VM profile needs an ISO pattern and vm_config_xml')
        target = None
        if not blank:
            from vm_pool import binding

            if binding() is not None:
                raise ValueError('Check in the existing VM reservation before provisioning')
            vm_config.require_online(vm)
            target = vm.require_build_target()
            if vm.compute_unit > vm.host.max_compute_unit:
                raise ValueError('VM compute cost exceeds the selected host capacity')
        template = (root / vm.vm_config_xml).resolve()
        if not template.is_relative_to(root.resolve()):
            raise ValueError('VM XML template must be inside the checkout')
        domain = ET.fromstring(template.read_text())
        if (domain.find('./cpu/numa/cell') is not None or
                domain.find('maxMemory') is not None or
                domain.find('./devices/memory') is not None):
            raise ValueError('VM RAM sizing from compute_unit requires a template without '
                             'guest NUMA cells or memory hotplug settings')
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
        memory_kib = vm.compute_unit * 1024 ** 2
        # Libvirt's XML parser caps RAM below 2**63 bytes.
        if not 1 <= memory_kib < 2 ** 53:
            raise ValueError('VM compute_unit yields a RAM size outside libvirt XML limits')
        memory_value = str(round(memory_kib))
        for tag in ('memory', 'currentMemory'):
            memory = domain.find(tag)
            if memory is None:
                memory = ET.SubElement(domain, tag)
            memory.set('unit', 'KiB')
            memory.text = memory_value
        for interface in domain.findall('./devices/interface'):
            for mac in interface.findall('mac'):
                interface.remove(mac)  # libvirt allocates a fresh address
        request = dict(name=name, root=host['virt-manager'], iso=iso, disk=str(vm.disk_anchor),
                       xml=ET.tostring(domain, encoding='unicode'), uuid=identifier, size=size)
        if target is not None:
            request['install'] = [target.distribution, target.version]
        request['checkout'] = (str(root) if host_name == owner.name else next(
            (b['repo_root'] for b in document.get('branches', []) if b['host'] == host_name), ''))
        if not request['checkout']:
            raise ValueError('VM host requires a configured branch checkout and refreshed VM-host helpers')
        if existing is not None:
            confirm(f'VM {name} is already registered on {existing.host.name} '
                    f'in family {existing.family}. Overwrite its registry entry with '
                    f'host {host_name}, family {family_name}, ID {vm_id}, enabled={enabled}?')
            group = vm_config.family_selectors(document)[existing.family.casefold()]
            group['vms'] = [row for row in group['vms']
                            if vm_config.resolve_vm_entry(row, group, profiles)['name'] != name]
        family['vms'].append(entry)
        for group in document['families']:
            group['vms'].sort(key=lambda row: vm_config.resolve_vm_entry(row, group, profiles)['id'])
        updated = format_environment(document).encode()
        # Reserve registry staging before any external mutation.
        fd, staging = tempfile.mkstemp(prefix='.environment-', suffix='.json', dir=config.parent)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(updated)
                stream.flush()
                os.fsync(stream.fileno())
            os.chmod(staging, config.stat().st_mode & 0o777)
            vm_config.registry(Path(staging))
            print(f'newvm: creating {name} on {host_name} (registry enabled={enabled})', flush=True)
            def execute():
                if host_name == owner.name:
                    return provision(request)
                output = bytearray()
                def collect(data):
                    if len(output) + len(data) > 65536:
                        raise ValueError('newvm: oversized provisioning response')
                    output.extend(data)
                encoded = base64.b64encode(json.dumps(request).encode()).decode('ascii')
                run_remote(root, hosts[host_name], ['--provision-worker', encoded], output=collect)
                return json.loads(output)
            result = execute()
            if 'existing_uuid' in result:
                confirm(f'VM {name} already exists in libvirt on {host_name}. '
                        f'Overwrite it and ERASE ITS SNAPSHOTS AND ALL DATA on {result["disk"]}?')
                request['overwrite_uuid'] = result['existing_uuid']
                result = execute()
            print(f'newvm: domain {name} ({identifier}) and disk {result["disk"]} created; '
                  'publishing registry entry', flush=True)
            if config.read_bytes() != original:
                raise ValueError('Registry changed during creation; VM/disk preserved; register manually')
            os.replace(staging, config)
            print(f'Created {name}: disk={result["disk"]}, ISO={result["iso"]}, '
                  f'UUID={result["uuid"]}; enabled={enabled}')
        finally:
            if os.path.exists(staging):
                os.unlink(staging)
    finally:
        os.close(descriptor)

    if not blank:
        try:
            if host_name == owner.name:
                install_and_prepare(root, vm, identifier)
            else:
                run_remote(root, vm.host, ['--install-worker', vm.name, identifier])
        except BaseException:
            print(f'newvm: provisioning incomplete for {name} ({identifier}) on {host_name}; '
                  'the registered VM and disk were preserved', file=sys.stderr, flush=True)
            raise
    return result


def main():
    try:
        return dispatch()
    except KeyboardInterrupt:
        print('newvm: interrupted', file=sys.stderr)
        return 130
    except (OSError, ValueError, ET.ParseError, subprocess.SubprocessError) as error:
        print(f'newvm: {error}', file=sys.stderr)
        return 1


def dispatch():
    if len(sys.argv) == 3 and sys.argv[1] == '--provision-worker':
        if vm_config.remote_origin() is None:
            raise ValueError('newvm: transferred source worker only')
        request = json.loads(base64.b64decode(sys.argv[2], validate=True))
        request['checkout'] = str(ROOT)
        print(json.dumps(provision(request)), flush=True)
        return 0
    if len(sys.argv) == 4 and sys.argv[1] == '--install-worker':
        from vm_pool import identity

        if vm_config.remote_origin() is None:
            raise ValueError('newvm: transferred source worker only')
        vm = vm_config.load(sys.argv[2])
        if vm.host.name != tool_host(ROOT).name:
            raise ValueError('newvm: selected VM belongs to another host')
        install_and_prepare(ROOT, vm, identity(sys.argv[3]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--id', required=True, metavar='ID',
                        help='Positive decimal VM ID used to resolve the VM name from its profile')
    parser.add_argument(vm_config.VMHOST_OPTION, metavar='HOST',
                        help='Override the host inherited from the VM profile')
    parser.add_argument('--vmconfig', metavar='PROFILE',
                        help='Select a VM profile in place of the family default')
    parser.add_argument('--family', required=True,
                        help='Existing family name or ID in config/environment.json (case-insensitive)')
    parser.add_argument('--blank', action='store_true',
                        help='Create a powered-off blank VM with the configured ISO inserted')
    args = parser.parse_args()
    create(args.id, args.vmhost, args.family, profile_name=args.vmconfig, blank=args.blank)
    action = 'created' if args.blank else 'installed and prepared'
    print(f'\033[32mnewvm: SUCCESS: VM {args.id} {action}; powered off\033[0m', flush=True)
    return 0
