"""Exercise the production install map without a checkout on the import path."""

import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

from tests.support.paths import ROOT


@pytest.fixture(scope="module")
def production_payload(tmp_path_factory):
    destination = tmp_path_factory.mktemp("production-payload")
    result = subprocess.run(
        ["make", "--no-print-directory", "_install-product-files",
         f"DESTDIR={destination}"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return destination


def test_payload_excludes_development_files_and_keeps_runtime_assets(production_payload):
    paths = {
        path.relative_to(production_payload).as_posix()
        for path in production_payload.rglob("*") if path.is_file()
    }
    for path in paths:
        parts = Path(path).parts
        assert not {"docs", "tests", "test_user_icons", "__pycache__"}.intersection(parts), path
        assert not Path(path).name.startswith(("preview", "test_", "README")), path
        assert not path.endswith((".pyc", "thunderbird-default128.png", "THUNDERBIRD-BRANDING-LICENSE")), path
    for path in (
        "usr/share/doc/oh-no-parent-control/LICENSE",
        "usr/share/doc/oh-no-parent-control/COPYRIGHT",
        "usr/share/doc/oh-no-parent-control/NOTICE",
        "usr/share/oh-no-parent-control/package-activation.json",
        "usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/rich_editor/quill.js",
        "usr/lib/oh-no-parent-control/common/oh_no_parent_control_ui/rich_editor/LICENSE",
        "usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/fonts/Monocraft.ttf",
        "usr/lib/oh-no-parent-control/kiosk/oh_no_parent_control_kiosk/fonts/OFL.txt",
    ):
        assert path in paths


def test_packaged_extension_has_all_local_imports(production_payload):
    extension = production_payload / (
        "usr/share/gnome-shell/extensions/oh-no-parent-control@tech.puffyslippers.com"
    )
    for unused in ("request-options.json", "app.json", "company_logo.png", "app_logo.png"):
        assert not (extension / unused).exists()
    for source in extension.iterdir():
        if source.suffix not in {".js", ".mjs"}:
            continue
        for target in re.findall(r"from ['\"](\./[^'\"]+)['\"]", source.read_text()):
            assert (source.parent / target).is_file(), (source.name, target)


def test_production_modules_import_without_preview_files(production_payload, tmp_path):
    # -I and the temporary cwd prevent the checkout or PYTHONPATH from hiding
    # missing installed dependencies. -B keeps the staged payload unchanged.
    script = """
import importlib
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import pkgutil
import sys

root = Path(sys.argv[1]) / 'usr/lib/oh-no-parent-control'
sys.path[:0] = [str(root), *(str(root / name) for name in ('broker', 'parent', 'kiosk'))]
for name in ('common.oh_no_parent_control_ui', 'oh_no_parent_control',
             'oh_no_parent_control_parent', 'oh_no_parent_control_kiosk'):
    package = importlib.import_module(name)
    for info in pkgutil.walk_packages(package.__path__, name + '.'):
        module = importlib.import_module(info.name)
        assert Path(module.__file__).is_relative_to(root), info.name
assert not any('preview' in name or 'test_identities' in name for name in sys.modules)
for name in ('oh_no_parent_control_parent.main', 'oh_no_parent_control_kiosk.main'):
    module = importlib.import_module(name)
    help_output = StringIO()
    with redirect_stdout(help_output):
        try:
            module.main(['--help'])
        except SystemExit as error:
            assert error.code == 0
    assert '--preview' not in help_output.getvalue()
    try:
        module.main(['--preview'])
    except SystemExit as error:
        assert error.code == 2
    else:
        raise AssertionError('Packaged app accepted a development-only preview')
print('All production modules imported without development files')
"""
    environment = dict(os.environ)
    environment.pop("DISPLAY", None)
    environment.pop("WAYLAND_DISPLAY", None)
    result = subprocess.run(
        [sys.executable, "-I", "-B", "-c", script, str(production_payload)],
        cwd=tmp_path, env=environment, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "All production modules imported" in result.stdout
