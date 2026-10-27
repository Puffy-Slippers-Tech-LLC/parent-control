"""Local COPR source recipe and clean Fedora binary/dependency validation."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

from tools import build_rpm, package_inputs, test_storage


# These are SCM source-generation inputs, not shipped product sources. Keep
# them outside PACKAGE_SOURCE_FILES, just as COPR receives them from Git.
SCM_INPUTS = tuple(map(Path, (
    '.copr/Makefile', 'tools/build_rpm.py', 'tools/package_inputs.py',
    'tools/rpm_builder.py', 'tools/test_storage.py', 'tools/test_retention.py',
    'tools/test_io.py',
)))

RECIPE = '''FROM registry.fedoraproject.org/fedora:44 AS source
RUN dnf -y install make
COPY source /source
WORKDIR /source
RUN make -f .copr/Makefile srpm outdir=/srpm spec=rpm/oh-no-parent-control.spec.in

FROM registry.fedoraproject.org/fedora:44
# Match Fedora Mock's standard build group. No development image or host RPM
# macros participate; resolve BuildRequires from the generated SRPM itself.
RUN dnf -y --setopt=install_weak_deps=False install @buildsys-build rpm-build dnf5-plugins
COPY --from=source /srpm /srpm
RUN dnf -y --setopt=install_weak_deps=False builddep /srpm/*.src.rpm && dnf clean all
RUN mkdir /build && chmod 1777 /build
WORKDIR /build
'''

BINARY = '''set -eu
rpmbuild --rebuild /srpm/*.src.rpm --define '_topdir /build' --define 'dist .fc44' --define '_smp_mflags -j2'
cp /srpm/* /output/
cp /build/RPMS/*/*.rpm /output/
rpm -qp --qf '%{NAME} %{VERSION} %{RELEASE} %{ARCH}\\n' /output/*.rpm
'''

DEPENDENCIES = '''set -eu
# Lint runs after compilation so its dependencies cannot conceal undeclared
# BuildRequires. Warnings remain visible; RPM lint errors fail validation.
dnf -y --setopt=install_weak_deps=False install rpmlint
rpmlint --config /rpmlint.toml /output/*.rpm
# Download-only resolution into an empty root checks the full runtime closure,
# without installing the product or executing its transaction scripts.
dnf -y --installroot=/runtime --use-host-config --releasever=44 --setopt=install_weak_deps=False install --downloadonly "/output/$1"
'''

# Exceptions describe the existing shared payload/lifecycle contract, not a
# general permissive lint mode. Keep exact package/path/mode/dependency matches;
# warnings (including individual duplicate paths) remain in the retained log.
LINT_FILTERS = (
    # The product supplies its own reviewed PAM account/session module.
    r'^oh-no-parent-control\.x86_64: E: pam-unauthorized-module pam_oh_no_parent_control\.so$',
    # Only administrators may read the Parent launcher (root:wheel, 0640).
    r'^oh-no-parent-control\.x86_64: E: non-readable /usr/share/applications/com\.puffyslippers\.OhNoParentControl\.Parent\.desktop 640$',
    # These are imported modules or explicitly interpreter-invoked helpers.
    r'^oh-no-parent-control\.x86_64: E: non-executable-script /usr/lib/oh-no-parent-control/lifecycle/(distro_pam|lifecycle_migration)\.py 644 /usr/bin/python3 -I$',
    r'^oh-no-parent-control\.x86_64: E: non-executable-script /usr/share/oh-no-parent-control/lifecycle/(postinst|postrm) 644 /bin/sh$',
    # Runtime trust/activation requires separate inodes; see Fedora-Packaging.
    r'^oh-no-parent-control\.x86_64: E: files-duplicated-waste [0-9]+$',
    # GI, ctypes and OS integration dependencies are not all ELF-discoverable.
    r'^oh-no-parent-control\.x86_64: E: explicit-lib-dependency (libadwaita|libselinux|lmdb-libs)$',
)


def prerequisites():
    if os.geteuid() == 0 or platform.machine() != 'x86_64':
        raise ValueError('local COPR validation requires an unprivileged x86_64 host')
    if shutil.which('podman') is None:
        raise ValueError('missing COPR validation tools; run ./setup.sh --rpm-build-tools')


def check_build(root, checkout, directory):
    """Use a private context, exact SCM recipe and fresh dependency environment."""
    prerequisites()
    attempt = directory / 'rpm'
    attempt.mkdir()
    context, output = attempt / 'context', attempt / 'output'
    context.mkdir()
    output.mkdir()
    frozen = context / 'source'
    frozen.mkdir()
    package_inputs.copy(checkout, frozen)
    before = package_inputs.digest(root, SCM_INPUTS)
    for relative in SCM_INPUTS:
        target = frozen / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(root / relative, target)
    if (package_inputs.digest(root, SCM_INPUTS) != before
            or package_inputs.digest(frozen, SCM_INPUTS) != before):
        raise ValueError('COPR source recipe changed while freezing inputs')
    (context / 'Containerfile').write_text(RECIPE)
    lint_config = attempt / 'rpmlint.toml'
    lint_config.write_text('Filters = ' + json.dumps(LINT_FILTERS, indent=2) + '\n')
    iid = attempt / 'image-id'
    report = dict(status='running', directory=str(attempt),
                  distribution='fedora-44', architecture='x86_64',
                  backend='podman-clean', build_network=False,
                  scm_sha256=before)

    def command(*arguments, stage):
        if stage != 'cleanup':
            report['stage'] = stage
        (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
        with (attempt / (stage + '.log')).open('w') as log:
            result = subprocess.run(arguments, cwd=attempt, stdin=subprocess.DEVNULL,
                                    stdout=log, stderr=subprocess.STDOUT, check=False,
                                    timeout=3600, pass_fds=test_storage.scratch_descriptors())
        if result.returncode:
            raise ValueError(f'local COPR {stage} failed; read {log.name}')

    print(f'test-publish: COPR source recipe and clean Fedora build: {attempt}', flush=True)
    try:
        command('podman', 'build', '--pull=missing', '--no-cache', '--layers=false',
                '--force-rm', '--iidfile', str(iid), str(context), stage='source-and-builddeps')
        image = iid.read_text().strip()
        if not re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', image):
            raise ValueError('invalid local COPR builder image identity')
        report['image'] = image
        epoch = build_rpm.metadata(checkout, '1')[1]
        command('podman', 'run', '--rm', '--pull=never', '--network=none',
                '--userns=keep-id', '--cap-drop=all',
                '--env', f'SOURCE_DATE_EPOCH={epoch}',
                '--volume', f'{output}:/output:rw,Z', image,
                '/bin/sh', '-ec', BINARY, stage='binary')
        product = json.loads((checkout / 'data/app.json').read_text())['version']
        # RPM generates filenames from package headers. Require this product's
        # binary and source package, not merely a successful builder exit.
        binaries = [p for p in output.glob(f'oh-no-parent-control-{product}-*.x86_64.rpm')
                    if p.is_file() and not p.is_symlink() and p.stat().st_size]
        srpms = list(output.glob(f'oh-no-parent-control-{product}-*.src.rpm'))
        if len(binaries) != 1 or len(srpms) != 1:
            raise ValueError('COPR validation produced no unique product RPM/SRPM')
        command('podman', 'run', '--rm', '--pull=never',
                '--volume', f'{output}:/output:ro,Z',
                '--volume', f'{lint_config}:/rpmlint.toml:ro,Z', image,
                '/bin/sh', '-ec', DEPENDENCIES, 'onpc-check', binaries[0].name,
                stage='lint-and-runtime-dependencies')
        report['output_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in (*srpms, *binaries)}
        report['status'] = 'passed'
    except BaseException:
        report['status'] = 'failed'
        raise
    finally:
        # Delete only the exact image created by this attempt, never shared tags,
        # caches or another build's containers. Failed cleanup also fails checks.
        try:
            if iid.is_file():
                image = iid.read_text().strip()
                if re.fullmatch(r'(?:sha256:)?[0-9a-f]{64}', image):
                    command('podman', 'image', 'rm', image, stage='cleanup')
        except BaseException:
            report['status'] = 'failed'
            raise
        finally:
            (attempt / 'result.json').write_text(json.dumps(report, indent=2) + '\n')
            print(f'test-publish: COPR validation {report["status"]}; evidence: {attempt}', flush=True)
    return report
