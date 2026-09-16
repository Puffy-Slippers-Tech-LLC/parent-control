"""Package inputs exclude development categories and remain buildable alone."""
import io
import os
from pathlib import Path
import subprocess
import tarfile

import pytest

from tools import package_inputs
from tools.publishing import source
from tests.support.paths import ROOT


def test_real_source_and_binary_archives_exclude_internal_files(tmp_path):
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    selected = package_inputs.copy(ROOT, checkout)
    marker = b'ONPC-INTERNAL-PACKAGING-CANARY'
    # Include a service that matches the old installation wildcard, as well as
    # development files alongside runtime modules and at the repository root.
    for name in (
        'README.md', 'AGENTS.md', '.envrc', '.codex/config.toml',
        'docs/internal.md', 'tests/test_internal.py', 'tools/internal.py',
        'parent/oh_no_parent_control_parent/preview_internal.py',
        'kiosk/oh_no_parent_control_kiosk/preview_internal.py',
        'common/oh_no_parent_control_ui/test_internal.py',
        'broker/oh_no_parent_control/test_internal.py',
        'child/preview_internal.js',
        'data/systemd/user/oh-no-parent-control-internal-canary.service',
    ):
        path = checkout / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'# ' + marker + b'\n')

    def command(*args, cwd, log, timeout=120):
        with log.open('a') as stream:
            result = subprocess.run(
                args, cwd=cwd, stdout=stream, stderr=subprocess.STDOUT,
                timeout=timeout, env=os.environ | {'DEB_BUILD_OPTIONS': 'parallel=2'})
        assert result.returncode == 0, log.read_text()

    source.build_archive(checkout, command, tmp_path / 'source-build.log')
    archive, = tmp_path.glob('oh-no-parent-control_*.tar.xz')
    with tarfile.open(archive) as contents:
        files = [entry for entry in contents if entry.isfile()]
        assert {Path(*Path(entry.name).parts[1:]) for entry in files} == set(selected)
        for entry in files:
            assert marker not in contents.extractfile(entry).read(), entry.name

    # A direct local build also has to stay clean when development files exist.
    command('dpkg-buildpackage', '--build=binary', '--no-sign',
            cwd=checkout, log=tmp_path / 'binary-build.log')
    binary, = tmp_path.glob('oh-no-parent-control_*_*.deb')
    payload = subprocess.check_output(['dpkg-deb', '--fsys-tarfile', str(binary)])
    with tarfile.open(fileobj=io.BytesIO(payload)) as contents:
        for entry in contents:
            path = Path(entry.name)
            assert not {'docs', 'tests', 'tools', '.codex', '.agents', '__pycache__'} & set(path.parts), entry.name
            assert not path.name.startswith(('preview', 'test_', 'README', 'AGENTS')), entry.name
            assert 'internal-canary' not in path.name, entry.name
            if entry.isfile():
                assert marker not in contents.extractfile(entry).read(), entry.name
        notice = contents.extractfile('./usr/share/oh-no-parent-control/NOTICE').read()
        assert b'Thunderbird' not in notice
        for required in (
            './usr/share/doc/oh-no-parent-control/copyright',
            './usr/share/man/man1/oh-no-parent-control.1.gz',
            './usr/share/man/man1/oh-no-parent-control-parent.1.gz',
            './usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/rich_editor/LICENSE',
            './usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt',
        ):
            assert contents.getmember(required).isfile()


def test_product_only_source_can_check_and_stage_the_complete_payload(tmp_path):
    selected = package_inputs.copy(ROOT, tmp_path)
    assert not {'docs', 'tests', '.agents', '.codex'} & {p.parts[0] for p in selected}
    assert Path('tools/read-only') not in selected
    assert Path('tools/run-tests') not in selected
    assert Path('tools/pam_oh_no_parent_control.c') in selected
    assert Path('tools/provision.py') in selected
    assert not any('preview' in p.name or 'test_user_icons' in p.parts for p in selected)
    for command in (
        ['/usr/bin/python3', '-B', 'debian/check_package.py'],
        ['make', '--no-print-directory', '_install-product-files', f'DESTDIR={tmp_path / "payload"}'],
    ):
        result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True)
        assert result.returncode == 0, result.stdout + result.stderr


def fixture(root):
    (root / 'Makefile').write_text('package-source-files:\n\t@printf "%s\\n" Makefile product.py\n')
    (root / 'product.py').write_text('value = 1\n')


def test_development_category_edits_do_not_change_package_identity(tmp_path):
    fixture(tmp_path)
    selected = package_inputs.paths(tmp_path)
    before = package_inputs.digest(tmp_path, selected)
    for name in ('docs/new.md', 'tests/new.py', 'tools/internal.py', 'AGENTS.md'):
        path = tmp_path / name
        path.parent.mkdir(exist_ok=True)
        path.write_text('unrelated edits\n\n')
    assert package_inputs.paths(tmp_path) == selected
    assert package_inputs.digest(tmp_path, selected) == before
    (tmp_path / 'product.py').write_text('value = 2\n')
    assert package_inputs.digest(tmp_path, selected) != before


@pytest.mark.parametrize('change', ['edit', 'remove', 'link'])
def test_copy_rejects_product_changes_during_snapshot(tmp_path, monkeypatch, change):
    fixture(tmp_path)
    destination = tmp_path / 'copy'
    original = package_inputs.shutil.copy2

    def copy(source, target):
        result = original(source, target)
        if source.name == 'product.py':
            if change == 'edit':
                source.write_text('changed\n')
            else:
                source.unlink()
                if change == 'link':
                    source.symlink_to(target)
        return result

    monkeypatch.setattr(package_inputs.shutil, 'copy2', copy)
    with pytest.raises(ValueError, match='package (source inputs changed|input must be)'):
        package_inputs.copy(tmp_path, destination)
