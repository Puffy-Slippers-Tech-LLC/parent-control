"""Transfer controller source through SSH into owned, disposable disk scratch."""

import inspect
from contextlib import contextmanager
import base64
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from host_dispatch import ssh_command, ssh_environment


def _receive(anchor):
    """Self-contained remote bootstrap; the receiver is supplied by the caller."""
    import json
    import os
    from pathlib import Path
    import subprocess
    import sys
    import tempfile
    import stat

    root = Path(anchor)
    if not root.is_absolute() or root.resolve(strict=True) != root:
        raise ValueError('remote source: invalid storage checkout')
    # Only allocation uses the host's installed checkout. The VM command below
    # starts a fresh interpreter exclusively from the transferred controller
    # source. It imports no VM implementation from the host's own checkout.
    sys.path.insert(0, str(root / 'tools'))
    import test_storage

    incoming = os.fdopen(0, 'rb', buffering=0, closefd=False)
    def receive(size):
        chunks = []
        while size:
            block = incoming.read(min(1024 * 1024, size))
            if not block:
                raise ValueError('remote source: interrupted request')
            chunks.append(block)
            size -= len(block)
        return b''.join(chunks)
    header_size = int.from_bytes(receive(8), 'big')
    if not 0 < header_size <= 64 * 1024 * 1024:
        raise ValueError('remote source: invalid request header')
    request = json.loads(receive(header_size))
    mode = request.get('mode')
    if mode not in ('operation', 'pool', 'setup'):
        raise ValueError('remote source: invalid operation mode')
    if mode == 'setup' and (request['command'] != [request['controller_root'] + '/setup.sh',
                                                  '--test-tools-only']
                            or request['cooperative']):
        raise ValueError('remote source: setup accepts only the helper refresh entry point')
    size = request['size']
    if type(size) is not int or size <= 0:
        raise ValueError('remote source: invalid archive size')
    # The shared scratch allocation, not the immediate SSH worker, owns this
    # tree. Its recorded identity is reclaimed on the next allocation after
    # the last descendant closes its lease. An early worker exit must never
    # unlink sources still used by a privileged descendant.
    storage = tempfile.mkdtemp(prefix='vm-source-', dir=test_storage.scratch_directory())
    storage = Path(storage)
    archive = storage / 'source.tar.gz'
    with archive.open('xb') as stream:
        remaining = size
        while remaining:
            block = incoming.read(min(1024 * 1024, remaining))
            if not block:
                raise ValueError('remote source: interrupted transfer')
            stream.write(block)
            remaining -= len(block)
    destination = storage / 'source'
    with archive.open('rb') as stream:
        receive_transfer(stream, destination, request['manifest'])
    archive.unlink()
    git_size = request.get('git_size', 0)
    if type(git_size) is not int or git_size < 0:
        raise ValueError('remote source: invalid Git snapshot size')
    if git_size:
        git_pack = storage / 'source.pack'
        with git_pack.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            while git_size:
                block = incoming.read(min(1024 * 1024, git_size))
                if not block:
                    raise ValueError('remote source: interrupted Git snapshot')
                stream.write(block)
                git_size -= len(block)
        request['git_pack'] = str(git_pack)
    for index, bundle in enumerate(request.get('bundles', [])):
        remaining = bundle['size']
        if type(remaining) is not int or remaining <= 0:
            raise ValueError('remote source: invalid artifact archive size')
        path = storage / ('artifacts-' + str(index) + '.tar.gz')
        with path.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            while remaining:
                block = incoming.read(min(1024 * 1024, remaining))
                if not block:
                    raise ValueError('remote source: interrupted artifact transfer')
                stream.write(block)
                remaining -= len(block)
        bundle['archive'] = str(path)
    input_size = request.get('stdin_size')
    if input_size is not None:
        if type(input_size) is not int or not 0 <= input_size <= 64 * 1024 * 1024:
            raise ValueError('remote source: invalid guest input size')
        input_path = storage / 'guest-input'
        with input_path.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            while input_size:
                block = incoming.read(min(1024 * 1024, input_size))
                if not block:
                    raise ValueError('remote source: interrupted guest input')
                stream.write(block)
                input_size -= len(block)
        request['stdin_path'] = str(input_path)
    placement = subprocess.run(['git', '-C', str(root), 'symbolic-ref',
                                '--quiet', '--short', 'HEAD'], check=True,
                               capture_output=True, text=True).stdout.strip()
    document = json.loads((destination / 'config/environment.json').read_bytes())
    branch = next((item for item in document.get('branches', [])
                   if item['name'] == placement), None)
    if (branch is None or branch['host'] != request['host']
            or Path(branch['repo_root']) != root):
        raise ValueError('remote source: storage checkout placement differs from controller registry')
    origin = dict(branch=request['branch'], host=request['host'],
                  storage_branch=placement, storage_root=str(root),
                  controller_root=request['controller_root'],
                  source_identity=request['source_identity'])
    if request.get('git'):
        origin['package_revision'] = request['git']['package_revision']
        origin['package_epoch'] = request['git']['package_epoch']
    allocate = '''import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / 'tools'))
from test_storage import remote_directory
print(remote_directory(sys.argv[2], sys.argv[3], sys.argv[4]))
'''
    runtime = subprocess.run(['/usr/bin/python3', '-IBu', '-c', allocate,
        str(destination), str(root), request['controller_root'], request['branch']],
        check=True, capture_output=True, text=True).stdout.strip()
    request['runtime_root'] = runtime
    receipt = destination / '.onpc-remote-source.json'
    receipt.write_text(json.dumps(origin))
    receipt.chmod(0o400)
    # Older installed resolvers cannot retain transferred source across
    # pkexec. Refuse before they can start a VM operation.
    for name in (() if mode == 'setup' else ('onpc-test-runner', 'onpc-setup')):
        helper = Path('/usr/local/libexec') / name
        info = helper.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022
                or 'def pin_remote_scratch(root, uid):' not in helper.read_text()):
            raise ValueError('remote source: refresh VM-host helpers with '
                             './setup.sh --test-tools-only before using transferred source')
    request_file = storage / 'request.json'
    request_file.write_text(json.dumps(request))
    request_file.chmod(0o600)
    bootstrap = '''import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / 'tools'))
from remote_sources import worker
sys.exit(worker(Path(sys.argv[1])))
'''
    result = subprocess.run(['/usr/bin/python3', '-IBu', '-c', bootstrap,
                             str(request_file)], cwd=destination, check=False,
                            pass_fds=test_storage.scratch_descriptors())
    print('vm-source-transfer: finished; source scratch is automatically reclaimed',
          file=sys.stderr, flush=True)
    return result.returncode


RESULT = 'ONPC_REMOTE_RESULT '


def artifact_inputs(root, command, files):
    """Find explicit artifact selectors, including a queued family assignment."""
    selectors = list(command[:command.index('--')] if '--' in command else command)
    for encoded in files.values():
        work = json.loads(base64.b64decode(encoded, validate=True))
        selectors.extend(work.get('selection', ()))
    result = {}
    for index, value in enumerate(selectors):
        option, separator, path = str(value).partition('=')
        if option not in ('--artifacts', '--previous-artifacts', '--native-artifacts', '--candidate'):
            continue
        if not separator:
            if index + 1 >= len(selectors):
                continue  # The public parser owns the missing-value diagnostic.
            path = selectors[index + 1]
        candidate = Path(path)
        candidate = candidate if candidate.is_absolute() else Path(root) / candidate
        if not candidate.exists():
            continue  # It may name an existing VM-host allocation on a later step.
        if candidate.resolve() != candidate or not candidate.is_dir():
            raise ValueError('remote source: artifact input must be an unlinked directory')
        verify_artifacts(candidate)
        result[str(path)] = candidate
    return result


def verify_artifacts(path):
    from build_test_artifacts import verify, verify_matrix, verify_upgrade, MATRIX_NAME, PACKAGE_INPUT_NAME
    from native_transaction_inputs import verify as verify_native, MANIFEST_NAME as NATIVE_NAME
    if (path / MATRIX_NAME).is_file():
        verify_matrix(path)
    elif (path / 'current').is_dir() and (path / 'previous').is_dir():
        verify_upgrade(path)
    elif (path / 'product').is_dir() and (path / 'native').is_dir():
        verify(path / 'product')
        verify_native(path / 'native')
    elif (path / NATIVE_NAME).is_file():
        verify_native(path)
    else:
        verify(path, package_only=(path / PACKAGE_INPUT_NAME).is_file())


@contextmanager
def capsule(root, host, command, environment, *, mode='operation', cooperative=False,
            execution=None, cwd=None, separate_stderr=False, stdin_file=None):
    """Capture before dispatch; keep source ownership only while reading it."""
    import test_source
    from vm_selection import vm_config
    from test_storage import scratch_directory
    from tools.vm_source_snapshot import transfer_archive, transfer_git, tree_paths, receive_transfer, input_bytes
    from contextlib import ExitStack
    from vm_test_queue import source_identity

    root = Path(root)
    document = vm_config.read_document(root / 'config/environment.json', validate_agent=False)
    anchor = next((item['repo_root'] for item in vm_config.branch_registry(document).values()
                   if item['host'] == host.name), None)
    if anchor is None:
        raise ValueError(f'no configured storage checkout on {host.name}')
    bootstrap = (inspect.getsource(receive_transfer) + '\n' + inspect.getsource(_receive)
                 + '\nimport sys\nsys.exit(_receive(sys.argv[1]))\n')
    ssh = ssh_command(host, ['/usr/bin/python3', '-IBu', '-c', bootstrap, anchor])
    with ExitStack() as inputs, tempfile.TemporaryFile(dir=scratch_directory()) as archive, \
            tempfile.TemporaryFile(dir=scratch_directory()) as payload, \
            tempfile.TemporaryFile(dir=scratch_directory()) as guest_input, \
            tempfile.TemporaryFile(dir=scratch_directory()) as git_pack:
        if stdin_file is not None:
            for block in iter(lambda: stdin_file.read(1024 * 1024), b''):
                guest_input.write(block)
                if guest_input.tell() > 64 * 1024 * 1024:
                    raise ValueError('remote source: guest input exceeds 64 MiB')
        # Pool capture is control plumbing, not test admission. It must remain
        # available behind impact holds so shutdown can acquire/release its VM.
        # Never wait for a source writer here; queue owners can retry without
        # retaining a VM or an execution slot.
        with (test_source.startup(root, ['--resume'], repair=True, wait=False)
              if mode == 'pool' else test_source.reader(root)):
            manifest = transfer_archive(root, archive)
            git_snapshot = transfer_git(root, git_pack) if mode != 'pool' else None
            files = {}
            # A family assignment is small controller-owned input, never an
            # ambient descriptor or a request for another controller's files.
            work = environment.get('ONPC_TEST_FAMILY_WORK')
            if work:
                path = Path(work)
                if not path.is_relative_to(root):
                    raise ValueError('remote source: unconfined family assignment')
                data, _ = input_bytes(path)
                files[work] = base64.b64encode(data).decode('ascii')
            bundles, bundle_streams = [], []
            for original, path in artifact_inputs(root, command, files).items():
                from test_retention import MAX_RETAINED_BYTES
                used = sum(entry['size'] for bundle in bundles for entry in bundle['manifest'].values())
                if used + sum(item.stat(follow_symlinks=False).st_size for item in tree_paths(path)) > MAX_RETAINED_BYTES:
                    raise ValueError('remote source: artifact input exceeds the retention budget')
                stream = inputs.enter_context(tempfile.TemporaryFile(dir=scratch_directory()))
                bundle_manifest = transfer_archive(path, stream, inventory=tree_paths)
                if (sum(entry['size'] for entry in bundle_manifest.values())
                        + used
                        > MAX_RETAINED_BYTES):
                    raise ValueError('remote source: artifact input exceeds the retention budget')
                bundles.append(dict(original=original, controller_path=str(path),
                                    size=stream.tell(), manifest=bundle_manifest))
                bundle_streams.append(stream)
                stream.seek(0)
            request = dict(mode=mode, receipt=uuid.uuid4().hex, host=host.name, branch=vm_config.current_branch(),
                controller_root=str(root), source_identity=source_identity(root),
                command=list(map(str, command)),
                environment={key: value for key, value in environment.items() if key != 'SSH_AUTH_SOCK'},
                cooperative=cooperative, execution=execution or {}, cwd=str(cwd or root),
                stdin_size=guest_input.tell() if stdin_file is not None else None,
                separate_stderr=separate_stderr, files=files, manifest=manifest, size=archive.tell())
            request.update(git=git_snapshot, git_size=git_pack.tell(), bundles=bundles)
            header = json.dumps(request).encode()
            payload.write(len(header).to_bytes(8, 'big') + header)
            archive.seek(0)
            shutil.copyfileobj(archive, payload)
            git_pack.seek(0)
            shutil.copyfileobj(git_pack, payload)
            # ExitStack owns these finite bundle streams through transmission.
            for stream in bundle_streams:
                shutil.copyfileobj(stream, payload)
            guest_input.seek(0)
            shutil.copyfileobj(guest_input, payload)
            payload.seek(0)
        yield ssh, payload, request


@contextmanager
def received_inputs(root, request):
    """Register copies before populating them; ordinary retention owns cleanup."""
    if not request.get('bundles'):
        yield {}
        return
    import test_retention
    from test_storage import directory
    from tools.vm_source_snapshot import receive_transfer
    # Keep explicit transferred inputs separate from the command's execution
    # retention. A live owner prevents rotation while any command uses them.
    vm = request['environment'].get('ONPC_TEST_VM', 'inputs')
    from vm_selection import vm_config
    vm_config.validate_name(vm)
    store = test_retention.Store(directory('state') / ('retention-transferred-' + vm))
    with store.session():
        paths = {}
        for bundle in request['bundles']:
            allocation = Path(test_retention.allocate(tempfile.mkdtemp, prefix='onpc-transferred-'))
            target = allocation / 'input'
            with open(bundle['archive'], 'rb') as archive:
                receive_transfer(archive, target, bundle['manifest'])
            verify_artifacts(target)
            paths[bundle['original']] = paths[bundle['controller_path']] = str(target)
        yield paths


def worker(request_file):
    request = json.loads(request_file.read_bytes())
    root = Path(__file__).resolve().parents[1]
    from contextlib import ExitStack
    from vm_recording import Session, VARIABLE as RECORDING
    from vm_selection import select
    if request['mode'] != 'pool':
        restore_git(root, request)
    with ExitStack() as stack:
        if request['mode'] != 'pool' and RECORDING in request['environment']:
            vm = request['environment']['ONPC_TEST_VM']
            select(vm)
            stack.enter_context(Session(root, vm_names=[vm]))
        paths = stack.enter_context(received_inputs(root, request))
        return run_worker(root, request_file, request, paths)


def restore_git(root, request):
    """Restore finite controller objects before source consumers start."""
    from vm_selection import vm_config
    origin = vm_config.remote_origin()
    if origin is None or vm_config.execution_host() != request['host']:
        raise ValueError('remote source: destination identity changed')
    subprocess.run(['git', 'init', '--quiet', '-b', origin['branch']], cwd=root, check=True)
    with open(request['git_pack'], 'rb') as packed:
        subprocess.run(['git', 'index-pack', '--stdin'], cwd=root, stdin=packed,
                       stdout=subprocess.DEVNULL, check=True)
    snapshot = request['git']
    (root / '.git/shallow').write_text('\n'.join(snapshot['commits']) + '\n')
    subprocess.run(['git', 'update-ref', 'refs/heads/' + origin['branch'], snapshot['head']],
                   cwd=root, check=True)
    for name, revision in snapshot['tags'].items():
        subprocess.run(['git', 'update-ref', 'refs/tags/' + name, revision], cwd=root, check=True)
    subprocess.run(['git', 'read-tree', 'HEAD'], cwd=root, check=True)
    (root / '.git/info/exclude').write_text('.onpc-remote-source.json\n')


def run_worker(root, request_file, request, paths):
    """Run one transferred command with state owned by the VM host."""
    from vm_selection import vm_config
    import test_storage
    import test_launcher
    from regression_process import Control

    origin = vm_config.remote_origin()
    if origin is None or vm_config.execution_host() != request['host']:
        raise ValueError('remote source: destination identity changed')
    runtime = test_storage.storage_root()
    if str(runtime) != request['runtime_root']:
        raise ValueError('remote source: operation storage changed')
    controller = request['controller_root']

    def mapped(value):
        if not isinstance(value, str):
            return value
        if value in paths:
            return paths[value]
        for original, destination in paths.items():
            if value.startswith(original + '/'):
                return destination + value[len(original):]
        # Work requests/explicit inputs stay in the durable operation namespace;
        # code paths point only at this invocation's transferred source.
        if value == controller:
            return str(root)
        if value.startswith(controller + '/output/'):
            return str(runtime) + value[len(controller):]
        if value.startswith(controller + '/'):
            return str(root) + value[len(controller):]
        option, separator, argument = value.partition('=')
        if separator and option.startswith('--'):
            return option + '=' + mapped(argument)
        return value

    environment = test_launcher.environment(root)
    if request.get('bundles'):
        import test_retention
        environment.pop(test_retention.VARIABLE, None)
        environment.pop(test_retention.OWNER_VARIABLE, None)
    # Local descriptors and owner receipts have no meaning across SSH. The
    # remote command establishes its own activity, source, scratch and retention
    # owners; only the host-verified VM checkout receipt crosses as text.
    allowed = ('ONPC_VM_CHECKOUT', 'ONPC_TEST_VM', 'ONPC_TEST_VM_WORKER',
               'ONPC_TEST_FAMILY_WORK', 'ONPC_TEST_REVERSE')
    for name in allowed:
        if name in request['environment']:
            environment[name] = mapped(request['environment'][name])
            os.environ[name] = environment[name]
    environment['ONPC_LAUNCHER_CONTROLLER_ROOT'] = str(root)
    # A guest exec's arguments belong to the guest, including absolute paths.
    # Map only the host command before its explicit argument boundary.
    boundary = (request['command'].index('--') if '--' in request['command']
                else len(request['command']))
    command = [mapped(value) if index < boundary else value
               for index, value in enumerate(request['command'])]
    if request['mode'] == 'pool':
        # The pool helper reads EOF as check-in. Preserve that channel directly;
        # no cancellation listener may consume its lifetime bytes.
        return subprocess.run(command, cwd=root, env=environment, check=False,
                              pass_fds=test_storage.scratch_descriptors()).returncode

    for name, encoded in request['files'].items():
        if name != request['environment'].get('ONPC_TEST_FAMILY_WORK'):
            raise ValueError('remote source: unconfined assignment destination')
        target = request_file.with_name('family-work.json')
        with target.open('xb') as stream:
            os.fchmod(stream.fileno(), 0o600)
            def map_values(value):
                if isinstance(value, dict):
                    return {key: map_values(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [map_values(item) for item in value]
                return mapped(value)
            work = json.loads(base64.b64decode(encoded, validate=True))
            mapped_work = map_values(work)
            # The controller's claim is an opaque identity, not an execution
            # path container. Return it byte-for-byte equivalent in evidence.
            mapped_work['assignment'] = work['assignment']
            stream.write(json.dumps(mapped_work).encode())
        environment['ONPC_TEST_FAMILY_WORK'] = str(target)
        os.environ['ONPC_TEST_FAMILY_WORK'] = str(target)

    response = dict(evidence=None, handoffs=[])
    def event(kind, **fields):
        sys.stdout.buffer.write(b'\0' + (RESULT + request['receipt'] + ' ').encode()
                                + json.dumps(dict(kind=kind, **fields)).encode() + b'\0')
        sys.stdout.buffer.flush()
    pending = b''
    dropping = False
    def output(data):
        nonlocal pending, dropping
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()
        if dropping:
            index = data.find(b'\n')
            if index < 0:
                return
            data, dropping = data[index + 1:], False
        pending += data
        while b'\n' in pending:
            line, pending = pending.split(b'\n', 1)
            text = line.decode('utf-8', errors='replace')
            if text.startswith('Failure handoff: '):
                path = Path(text.removeprefix('Failure handoff: '))
                if (path.is_absolute() and '..' not in path.parts
                        and path.is_relative_to(runtime / 'output/test-runs/host')
                        and path.resolve() == path and path.stat().st_size <= 4 * 1024 * 1024):
                    from tools.vm_source_snapshot import input_bytes
                    handoff = dict(failure=json.loads(input_bytes(path)[0]),
                                   host=origin['host'], context=None)
                    # Reuse the existing finite failure-copy mechanism. The
                    # controller receives useful diagnostics without adopting
                    # VM-host logs or depending on disposable source paths.
                    from repair_evidence import capture
                    context = request_file.with_name('failure-context-' +
                                                    str(len(response['handoffs'])) + '.json')
                    try:
                        capture(root, context, path, '')
                        handoff['context'] = json.loads(input_bytes(context)[0])
                    except (OSError, ValueError, subprocess.TimeoutExpired):
                        pass  # The original report and streamed output remain.
                    def fits():
                        return len(json.dumps(dict(response,
                            handoffs=[*response['handoffs'], handoff])).encode()) <= 12 * 1024 * 1024
                    if not fits():
                        handoff['context'] = None
                    if fits():
                        response['handoffs'].append(handoff)
                    else:
                        response['omitted_handoffs'] = response.get('omitted_handoffs', 0) + 1
        if len(pending) > 8192:
            pending, dropping = b'', True

    def stderr(data):
        event('stderr', data=base64.b64encode(data).decode('ascii'))
    from contextlib import nullcontext
    with (open(request['stdin_path'], 'rb') if 'stdin_path' in request else nullcontext()) as guest_input, \
            Control().installed(pipe=True) as control:
        status = control.run(command, cwd=mapped(request.get('cwd', controller)), env=environment,
            cooperative=request['cooperative'], output=output, stdin_file=guest_input,
            stderr_output=stderr if request.get('separate_stderr') else None,
            started=lambda: event('started'), **request.get('execution', {}))
    if 'ONPC_TEST_FAMILY_WORK' in environment:
        from test_checkpoint import Checkpoint
        from test_commands import selections
        work = json.loads(Path(environment['ONPC_TEST_FAMILY_WORK']).read_bytes())
        saved = Checkpoint(root, selections(root, work['selection']), resume=True,
                           binding=work['assignment']['vm'])
        response['evidence'] = saved.state.get('queue_evidence')
    # A private nonce separates host completion from arbitrary guest stdout.
    # NUL framing also preserves binary output and a final unterminated line.
    event('result', value=response)
    return status


class RemoteVM:
    def __init__(self, root, vm=None, *, host=None):
        self.root, self.vm = Path(root), vm
        self.host = vm.host if vm is not None else host
        if self.host is None:
            raise ValueError('remote source: a destination host is required')
        self.result = {}

    def pool_process(self, command, environment):
        """Return a live SSH keeper with the ordinary pool receipt/EOF contract."""
        from test_storage import scratch_descriptors
        with capsule(self.root, self.host, command, environment, mode='pool') as (ssh, payload, _):
            child = subprocess.Popen(ssh, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     env=ssh_environment(environment),
                                     pass_fds=scratch_descriptors())
            try:
                shutil.copyfileobj(payload, child.stdin)
                child.stdin.flush()
            except BaseException:
                child.stdin.close()
                child.stdout.close()
                child.wait()
                raise
            return child

    def run(self, control, command, *, env, output=None, cooperative=False, cwd=None,
            timeout=None, kill_after=30.0, cancel_signal=2, owned_group=False,
            started=None, stderr_output=None, stdin_file=None, wait_on_cancel=False,
            mode='operation', **options):
        pending = b''
        prefix = None
        self.result = {}
        env = dict(env)
        if self.vm is not None:
            env['ONPC_TEST_VM'] = self.vm.name
        if output is None:
            from regression_process import PipeFrameReader
            output = PipeFrameReader(sys.stdout)
        def emit(data):
            nonlocal pending
            pending += data
            while pending:
                index = pending.find(prefix)
                if index < 0:
                    count = max(0, len(pending) - len(prefix) + 1)
                    if count:
                        output(pending[:count])
                        pending = pending[count:]
                    return
                if index:
                    output(pending[:index])
                    pending = pending[index:]
                end = pending.find(b'\0', len(prefix))
                if end < 0:
                    if len(pending) > 16 * 1024 * 1024:
                        raise ValueError('remote source: oversized completion receipt')
                    return
                message = json.loads(pending[len(prefix):end])
                if message['kind'] == 'result':
                    if self.result:
                        raise ValueError('remote source: duplicate completion receipt')
                    self.result = message['value']
                elif message['kind'] == 'started':
                    if started is not None:
                        started()
                elif message['kind'] == 'stderr' and stderr_output is not None:
                    stderr_output(base64.b64decode(message['data'], validate=True))
                else:
                    raise ValueError('remote source: unexpected command event')
                pending = pending[end + 1:]
        execution = dict(timeout=timeout, kill_after=kill_after,
                         cancel_signal=int(cancel_signal), owned_group=owned_group,
                         wait_on_cancel=wait_on_cancel or (
                             command[0] == '/usr/bin/pkexec' and not cooperative
                             and timeout is None and not owned_group))
        with capsule(self.root, self.host, command, env, cooperative=cooperative, mode=mode,
                     execution=execution, cwd=cwd, stdin_file=stdin_file,
                     separate_stderr=stderr_output is not None) as (ssh, payload, request):
            prefix = b'\0' + (RESULT + request['receipt'] + ' ').encode()
            status = control.run(ssh, cwd=self.root, env=ssh_environment(env), output=emit,
                                 cooperative=True, input_stream=payload,
                                 stderr_output=stderr_output, **options)
        if pending:
            output(pending)
        if hasattr(output, 'finish'):
            output.finish()
        if status == 0 and not self.result:
            raise ValueError('remote source: missing command completion receipt')
        return status
