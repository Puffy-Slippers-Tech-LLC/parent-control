"""Frozen, target-built native fixture inputs; no product builds or VM work."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / 'tools') not in sys.path:
    sys.path.insert(0, str(ROOT / 'tools'))
from tools import artifact_inputs, fixture_manifest, fixture_producer, test_storage, test_retention

TARGETS = {'ubuntu': {'os': 'ubuntu', 'release': '26.04', 'architecture': 'x86_64'},
           'fedora': {'os': 'fedora', 'release': '44', 'architecture': 'x86_64'}}
MAX_SOURCE = 8 * 1024 * 1024
MAX_SCRATCH = 128 * 1024 * 1024


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def source_snapshot(root):
    """Read the exact source closure, refusing links and concurrent mutation."""
    root = Path(root).resolve(strict=True)
    records, contents = {}, {}
    for name in artifact_inputs.NATIVE_RUNTIME_SOURCES:
        path = root / name
        if path.resolve(strict=True) != path:
            raise ValueError('fixture sources contain a link')
        before = path.lstat()
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            opened = os.fstat(stream.fileno())
            if (not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1
                    or opened.st_size > MAX_SOURCE):
                raise ValueError('invalid fixture source')
            data = stream.read(MAX_SOURCE + 1)
            after = os.fstat(stream.fileno())
        identity = lambda info: (info.st_dev, info.st_ino, info.st_size, info.st_mode,
                                  info.st_mtime_ns, info.st_ctime_ns)
        if not identity(before) == identity(opened) == identity(after) == identity(path.lstat()):
            raise ValueError('fixture sources changed during capture')
        records[name] = {'sha256': hashlib.sha256(data).hexdigest(),
                         'length': len(data), 'mode': stat.S_IMODE(opened.st_mode)}
        contents[name] = data
    return records, contents


def environment_inputs(root, target):
    """Only build-environment requirements, never product version/install data."""
    from tools import deb_builder, rpm_builder
    builder = deb_builder if target == 'ubuntu' else rpm_builder
    recipe, requirements, image = builder.inputs(root)
    if target == 'fedora':
        requirements = '\n'.join(line for line in requirements.splitlines()
                                  if line.startswith('BuildRequires:'))
    else:
        # inputs() returns control as well as its already narrowed image key.
        requirements = image.rsplit('-', 1)[-1]
    return {'recipe_sha256': hashlib.sha256(recipe).hexdigest(),
            'requirements_sha256': hashlib.sha256(requirements.encode()).hexdigest(),
            'image': image}


def freeze(root, destination, target):
    records, contents = source_snapshot(root)
    environment = environment_inputs(root, target)
    for name, data in contents.items():
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        path.chmod(records[name]['mode'])
    # Existing target builder image selectors consume these only to derive
    # their recipe/dependency key. They never build product packages here.
    for name in ('rpm/Containerfile', 'rpm/oh-no-parent-control.spec.in',
                 'debian/Containerfile', 'debian/control'):
        path = destination / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, path)
    if (source_snapshot(root)[0] != records or source_snapshot(destination)[0] != records
            or environment_inputs(root, target) != environment
            or environment_inputs(destination, target) != environment):
        raise ValueError('fixture sources changed while freezing')
    return records, environment


def _run(command, *, environment=None, timeout=None):
    return subprocess.run(command, env=environment, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          pass_fds=test_storage.scratch_descriptors(), timeout=timeout)


def assemble(source, compiled, staging, inputs, environment):
    """Assemble exclusively through the frozen codec and declarations."""
    inputs_path = compiled.parent / 'assembly-inputs.json'
    descriptor = os.open(inputs_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(encoded(inputs) + b'\n')
        stream.flush()
        os.fsync(stream.fileno())
    command = [sys.executable, '-I', '-S', '-B', str(source / 'tools/fixture_assembly.py'),
               '--source', str(source), '--compiled', str(compiled),
               '--output', str(staging), '--inputs', str(inputs_path)]
    _run(command, environment=environment, timeout=120)


def target_build(source, workspace, target, environment):
    """Use the exact local OS or the existing offline target build image."""
    from tools import deb_builder, rpm_builder
    release = {}
    for line in Path('/etc/os-release').read_text().splitlines():
        key, separator, value = line.partition('=')
        if separator:
            release[key] = value.strip('\"\'')
    leases = test_storage.scratch_descriptors()
    flags = [value for fd in leases for value in ('--lease-fd', str(fd))]
    image_identity = None
    if (release.get('ID') == target and release.get('VERSION_ID') == TARGETS[target]['release']
            and os.uname().machine == 'x86_64'):
        command = [sys.executable, '-I', '-S', '-B', str(source / 'tools/fixture_target_build.py'),
                   '--source', str(source), '--output', str(workspace / 'compiled'),
                   '--target', target, *flags]
    else:
        builder = deb_builder if target == 'ubuntu' else rpm_builder
        image = builder.require_image(source)
        # Rootless image/storage identity belongs to the authenticated caller.
        # Compiler HOME remains private; Podman must see the same existing
        # caller-owned images as require_image(), never a fresh private store.
        environment = environment | {'HOME': str(Path.home())}
        # Pin actual image bytes, not a mutable tag. No pull, build or network.
        identity = _run(['podman', 'image', 'inspect', '--format', '{{.Id}}', image],
                        environment=environment).stdout.strip()
        if re.fullmatch('[0-9a-f]{64}', identity) is None:
            raise ValueError('fixture target image identity unavailable')
        image_identity = 'sha256:' + identity
        command = [sys.executable, '-I', '-S', '-B', str(source / 'tools/fixture_container.py'),
                   '--source', str(source), '--workspace', str(workspace),
                   '--image', identity, '--target', target, *flags]
    (workspace / 'scratch').mkdir()
    (workspace / 'compiled').mkdir()
    result = _run(command, environment=environment)
    if result.stdout.strip():
        print(result.stdout.strip(), flush=True)
    compiled = workspace / 'compiled'
    toolchain = json.loads((compiled / 'toolchain.json').read_text())
    if toolchain.get('target') != TARGETS[target]:
        raise ValueError('fixture target compiler identity mismatch')
    proofs = toolchain.pop('abi', None)
    identities = ('mechanical', 'A', 'H', 'S', 'N', 'trusted-hard', 'trusted-soft',
                  'trusted-activity')
    if type(proofs) is not dict or set(proofs) != set(identities):
        raise ValueError('fixture target ABI proof inventory mismatch')
    for identity, proof in proofs.items():
        data = (compiled / identity).read_bytes()
        if (type(proof) is not dict or proof.get('sha256') != hashlib.sha256(data).hexdigest()
                or proof.get('class') != 'ELF64' or proof.get('machine') != 'x86_64'
                or proof.get('interpreter') != '/lib64/ld-linux-x86-64.so.2'
                or proof.get('needed') != ['libc.so.6']):
            raise ValueError('fixture target ABI proof mismatch')
        fixture_manifest.verify_elf(data)
    # ABI hashes describe outputs. Keep them in retained command evidence and
    # the output manifest rather than feeding them into the build input identity.
    print('fixture-bundle: target-abi=' + json.dumps({'target': target,
          'executables': {name: proof['sha256'] for name, proof in proofs.items()}},
          sort_keys=True), flush=True)
    toolchain['image_identity'] = image_identity
    return compiled, toolchain


def usage(path):
    paths = [path, *path.rglob('*')]
    return {'bytes': sum(p.stat().st_size for p in paths if p.is_file()),
            'allocated_bytes': sum(p.stat().st_blocks * 512 for p in paths)}


def _output_identity(output, descriptor, original):
    """A retained locator may never redirect publication to a replacement."""
    identity = lambda info: (info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode)
    try:
        current = test_retention.directory(output)
    except (OSError, ValueError) as error:
        raise ValueError('fixture output allocation was replaced') from error
    try:
        if (identity(os.fstat(current)) != identity(original)
                or identity(os.fstat(descriptor)) != identity(original)
                or test_retention.mount_id(current) != test_retention.mount_id(descriptor)):
            raise ValueError('fixture output allocation was replaced')
    finally:
        os.close(current)


def build(output, *, target, root=ROOT, publication='move', publish_guard=None):
    if target not in TARGETS:
        raise ValueError('unsupported fixture target')
    if publication not in ('move', 'copy'):
        raise ValueError('unsupported fixture publication')
    output = Path(output)
    if output.resolve(strict=True) != output:
        raise ValueError('fixture output must be an empty allocated directory')
    descriptor = test_retention.directory(output)
    try:
        original = os.fstat(descriptor)
        if os.listdir(descriptor):
            raise ValueError('fixture output must be an empty allocated directory')
        _output_identity(output, descriptor, original)
        return _build(output, descriptor, original, target=target, root=root,
                      publication=publication, publish_guard=publish_guard)
    finally:
        os.close(descriptor)


def _build(output, output_fd, original, *, target, root, publication, publish_guard):
    transaction = uuid.uuid4().hex
    print('fixture-bundle: transaction=' + transaction, flush=True)
    store = fixture_producer.Store()
    with store.queued_producer(transaction_id=transaction,
                               compatibility_key='native-runtime-' + target,
                               build_key='frozen-native-runtime-v1') as producer:
        source = producer.allocate('sources')
        records, environment_record = freeze(root, source, target)
        workspace = producer.allocate('build')
        environment = producer.environment({'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
            'LANG': 'C.UTF-8', 'HOME': str(workspace), 'SOURCE_DATE_EPOCH': '0',
            'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONNOUSERSITE': '1',
            **test_retention.environment(),
            **({'XDG_RUNTIME_DIR': os.environ['XDG_RUNTIME_DIR']} if 'XDG_RUNTIME_DIR' in os.environ else {})})
        compiled, toolchain = target_build(source, workspace, target, environment)
        staging = producer.allocate('staging') / 'bundle'
        staging.mkdir(mode=0o700)
        inputs = {'source': records, 'toolchain': {'environment': environment_record,
                  'compiler': toolchain}, 'target': TARGETS[target],
                  'dependencies': fixture_manifest.DEPENDENCIES}
        assemble(source, compiled, staging, inputs, environment)
        producer.verifying()
        manifest = fixture_manifest.verify(staging, target=target)
        if (source_snapshot(root)[0] != records or source_snapshot(source)[0] != records
                or environment_inputs(root, target) != environment_record):
            raise ValueError('fixture sources changed during build')
        # Account for both target workspace scratch and the producer's host
        # TMPDIR. These are final retained sizes, not peak construction usage.
        sizes = {'output': usage(staging), 'sources': usage(source),
                 'scratch': usage(workspace), 'host_scratch': usage(Path(environment['TMPDIR']))}
        if sum(item['allocated_bytes'] for item in sizes.values()) > MAX_SCRATCH:
            raise ValueError('fixture construction exceeds reviewed storage limit')
        print('fixture-bundle: sizes=' + json.dumps(sizes, sort_keys=True), flush=True)
        final = output / 'native-runtime'
        _output_identity(output, output_fd, original)
        if os.listdir(output_fd):
            raise ValueError('fixture publication collision')
        # Execution inputs require independent bytes before this producer's
        # lease is released. Preserve a failed copy inside its registered
        # destination; an incomplete nonempty input must never be adopted.
        if publish_guard is not None:
            publish_guard()
        _output_identity(output, output_fd, original)
        if publication == 'copy':
            os.mkdir('.native-runtime-staging', mode=0o700, dir_fd=output_fd)
            copied = os.open('.native-runtime-staging',
                             os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=output_fd)
            try:
                copied_info = os.fstat(copied)
                for name in ('fixture-manifest.json', 'payload.tar', 'complete.json'):
                    _output_identity(output, output_fd, original)
                    source_fd = os.open(staging / name, os.O_RDONLY | os.O_NOFOLLOW)
                    try:
                        descriptor = os.open(name,
                                             os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                             0o600, dir_fd=copied)
                        with os.fdopen(source_fd, 'rb', closefd=False) as source_stream:
                            with os.fdopen(descriptor, 'wb') as destination_stream:
                                shutil.copyfileobj(source_stream, destination_stream)
                                destination_stream.flush()
                                os.fsync(destination_stream.fileno())
                    finally:
                        os.close(source_fd)
                    _output_identity(output, output_fd, original)
                fixture_manifest.verify(staging, target=target)
                if fixture_manifest._verify(copied, target, True) != manifest:
                    raise ValueError('fixture copy identity mismatch')
                os.fsync(copied)
            finally:
                os.close(copied)
        if publish_guard is not None:
            publish_guard()
        _output_identity(output, output_fd, original)
        # Registered roots stay in place; readiness is one atomic child rename.
        if publication == 'copy':
            current = os.stat('.native-runtime-staging', dir_fd=output_fd, follow_symlinks=False)
            if (current.st_dev, current.st_ino) != (copied_info.st_dev, copied_info.st_ino):
                raise ValueError('fixture publication staging was replaced')
            os.rename('.native-runtime-staging', 'native-runtime',
                      src_dir_fd=output_fd, dst_dir_fd=output_fd)
        else:
            os.rename(staging, 'native-runtime', dst_dir_fd=output_fd)
        os.fsync(output_fd)
        _output_identity(output, output_fd, original)
        descriptor = os.open('native-runtime', os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                             dir_fd=output_fd)
        try:
            if fixture_manifest._verify(descriptor, target, True) != manifest:
                raise ValueError('fixture published identity mismatch')
        finally:
            os.close(descriptor)
        _output_identity(output, output_fd, original)
    print('fixture-bundle: output=' + str(final), flush=True)
    print('fixture-bundle: producer-cleanup=passed', flush=True)
    return final


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--target', choices=tuple(TARGETS), required=True)
    parser.add_argument('--verify', action='store_true')
    args = parser.parse_args()
    try:
        if args.verify:
            manifest = fixture_manifest.verify(args.output, target=args.target)
            print('fixture-bundle: verify=passed build=' + manifest['build_identity'])
        else:
            build(args.output, target=args.target)
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            print((error.stderr or '')[-16000:], file=sys.stderr)
        print('fixture-bundle: failed=' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
