"""Clean resolute/amd64 binary validation of this project's native source DSC."""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile


CONFIG = """# Managed per-attempt PPA validation settings.
$chroot_mode = 'unshare';
$unshare_mmdebstrap_keep_tarball = 1;
$unshare_mmdebstrap_extra_args = [ 'resolute', ['--components=main,restricted,universe,multiverse'] ];
$unshare_bind_mounts = [];
$external_commands = {};
$extra_packages = [];
$extra_repositories = [];
$build_source = 0;
$clean_source = 0;
$run_lintian = 0;
$run_autopkgtest = 0;
$run_piuparts = 0;
$enable_network = 0;
$mailto = '';
1;
"""


def source_inputs(root):
    version = subprocess.check_output(
        ['/usr/bin/dpkg-parsechangelog', '-S', 'Version'], cwd=root, text=True).strip()
    if not re.fullmatch(r'[0-9]+\.[0-9]+\+ppa[1-9][0-9]*~ubuntu26\.04\.1', version):
        raise ValueError('expected a resolute PPA version')
    prefix = f'oh-no-parent-control_{version}'
    dsc = root.parent / f'{prefix}.dsc'
    if dsc.is_symlink() or not dsc.is_file():
        raise ValueError('missing regular source DSC; build and inspect the source first')
    payload = dsc.read_bytes()
    text = payload.decode('utf-8')
    for field, value in [('Source', 'oh-no-parent-control'), ('Version', version), ('Format', '3.0 (native)')]:
        if re.findall(r'^' + field + r': (.*)$', text, re.M) != [value]:
            raise ValueError('unexpected source DSC identity or format')
    manifests = re.findall(r'^Checksums-Sha256:\n((?: .+\n)+)', text, re.M)
    if len(manifests) != 1:
        raise ValueError('source DSC must contain one SHA-256 manifest')
    entries = [line.split() for line in manifests[0].splitlines()]
    if len(entries) != 1 or len(entries[0]) != 3:
        raise ValueError('expected exactly one native source archive')
    digest, size, name = entries[0]
    if name != f'{prefix}.tar.xz' or not re.fullmatch('[0-9a-f]{64}', digest) or not size.isdigit():
        raise ValueError('unexpected native source archive manifest')
    archive = root.parent / name
    if archive.is_symlink() or not archive.is_file():
        raise ValueError('source archive must be a regular file')
    archive_bytes = archive.read_bytes()
    if len(archive_bytes) != int(size) or hashlib.sha256(archive_bytes).hexdigest() != digest:
        raise ValueError('source archive checksum mismatch')
    return version, {dsc.name: payload, name: archive_bytes}


def command(dsc, output):
    return ['/usr/bin/sbuild', '--chroot-mode=unshare', '--dist=resolute', '--arch=amd64',
            '--chroot=onpc-resolute-amd64', '--arch-all', '--arch-any', '--no-source',
            '--no-clean-source', '--no-enable-network', '--no-run-lintian',
            '--no-run-autopkgtest', '--no-run-piuparts', '--jobs=2',
            '--build-dir=' + str(output), str(dsc)]


def check_prerequisites():
    for tool in ('sbuild', 'mmdebstrap', 'newuidmap', 'newgidmap'):
        if not shutil.which(tool, path='/usr/bin:/bin'):
            raise ValueError('missing local build tools; run ./setup.sh --ppa-build-tools')
    if subprocess.check_output(['/usr/bin/dpkg', '--print-architecture'], text=True).strip() != 'amd64':
        raise ValueError('local PPA validation currently supports an amd64 host only')
    # Additional system configuration can introduce host hooks or extra packages
    # and invalidate the clean-builder claim. Do not silently override it.
    system_config = Path('/etc/sbuild/sbuild.conf')
    if system_config.exists() and any(line.strip() not in ('', '1;') and not line.lstrip().startswith('#')
                                      for line in system_config.read_text().splitlines()):
        raise ValueError('custom system sbuild configuration needs review before clean PPA validation')


def check_build(root):
    check_prerequisites()
    version, inputs = source_inputs(root)
    attempt = Path(tempfile.mkdtemp(prefix='onpc-ppa-check-', dir='/tmp'))
    source = attempt / 'input'
    output = attempt / 'output'
    config_dir = attempt / 'config/sbuild'
    source.mkdir()
    output.mkdir()
    config_dir.mkdir(parents=True)
    config = config_dir / 'config.pl'
    config.write_text(CONFIG)
    for name, payload in inputs.items():
        (source / name).write_bytes(payload)
    report = {'directory': str(attempt), 'version': version, 'distribution': 'resolute', 'architecture': 'amd64',
              'backend': 'sbuild-unshare', 'build_network': False, 'status': 'running',
              'input_sha256': {name: hashlib.sha256(payload).hexdigest() for name, payload in inputs.items()}}
    report_path = attempt / 'result.json'
    report_path.write_text(json.dumps(report, indent=2) + '\n')
    # No host build options, proxy credentials, signing secrets, injected config
    # or arbitrary command hooks pass into the builder. HOME keeps its real value.
    env = {key: os.environ[key] for key in ('HOME', 'USER', 'LOGNAME') if key in os.environ}
    env.update(PATH='/usr/sbin:/usr/bin:/sbin:/bin', LANG='C.UTF-8',
               XDG_CONFIG_HOME=str(attempt / 'config'), SBUILD_CONFIG=str(config),
               DEB_BUILD_OPTIONS='parallel=2', DEB_BUILD_PROFILES='')
    dsc = source / next(name for name in inputs if name.endswith('.dsc'))
    print(f'publish: clean binary build evidence: {attempt}', flush=True)
    print('publish: resolving dependencies, then building without network or skipped tests', flush=True)
    try:
        with (attempt / 'build.log').open('x') as log:
            result = subprocess.run(command(dsc, output), cwd=output, env=env,
                                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, check=False)
        report['exit_code'] = result.returncode
        report['status'] = 'failed'
        if result.returncode != 0:
            raise ValueError(f'clean package build failed; read {attempt}/build.log; '
                             f'detailed sbuild logs: {output}')
        binary = output / f'oh-no-parent-control_{version}_amd64.deb'
        changes = output / f'oh-no-parent-control_{version}_amd64.changes'
        if any(path.is_symlink() or not path.is_file() or path.stat().st_size == 0
               for path in (binary, changes)):
            raise ValueError('builder exited successfully without the expected binary artifacts')
        report['output_sha256'] = {path.name: hashlib.sha256(path.read_bytes()).hexdigest()
                                   for path in (binary, changes)}
        report['status'] = 'passed'
    except BaseException:
        if report['status'] == 'running':
            report['status'] = 'interrupted-or-execution-error'
        raise
    finally:
        report_path.write_text(json.dumps(report, indent=2) + '\n')
        print(f'publish: clean build {report["status"]}; evidence: {attempt}', flush=True)
    return report
