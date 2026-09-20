"""Exercise the production install map without a checkout on the import path."""

import configparser
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
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
        "usr/share/oh-no-parent-control/company_icon_32.png",
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
    for unused in ("request-options.json", "app.json", "company_icon_32.png", "app_logo.png"):
        assert not (extension / unused).exists()
    for source in extension.iterdir():
        if source.suffix not in {".js", ".mjs"}:
            continue
        for target in re.findall(r"from ['\"](\./[^'\"]+)['\"]", source.read_text()):
            assert (source.parent / target).is_file(), (source.name, target)


def test_native_probe_payload_and_activation_are_complete(production_payload):
    manifest = json.loads((production_payload / (
        "usr/share/oh-no-parent-control/package-activation.json")).read_text())
    entries = {entry["path"]: entry for entry in manifest["files"]}
    for name in ("execution_probe", "probe_channel", "probe_generation"):
        path = f"usr/lib/oh-no-parent-control/broker/oh_no_parent_control/{name}.py"
        assert (production_payload / path).is_file()
        assert entries[path]["activation"] == "process-restart"
    for kind in ("gate", "witness"):
        path = f"usr/libexec/oh-no-parent-control-execution-probe-{kind}"
        binary = production_payload / path
        assert binary.read_bytes().startswith(b"\x7fELF")
        assert binary.stat().st_mode & 0o7777 == 0o755
        assert entries[path] == {
            "path": path, "activation": "process-restart",
            "sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        }
        # The actual production build must refuse an invocation without its
        # private protocol. No runtime path is relocated or accessed here.
        result = subprocess.run([str(binary)], capture_output=True, text=True,
                                timeout=5, env={})
        assert result.returncode == 70
        assert result.stdout == ""
        assert result.stderr == f"execution-probe: {kind}-refused\n"


def test_packaged_broker_preserves_private_probe_runtime(production_payload):
    path = "usr/lib/systemd/system/oh-no-parent-control-broker.service"
    unit = configparser.ConfigParser(strict=False, interpolation=None)
    unit.read(production_payload / path)
    service = unit["Service"]
    assert service["User"] == "root"
    assert service["RuntimeDirectory"] == "oh-no-parent-control/probes"
    assert service["RuntimeDirectoryMode"] == "0700"
    assert service["RuntimeDirectoryPreserve"] == "yes"
    assert service["ProtectSystem"] == "strict"
    # systemd provisions /run at service start; it is not a package directory
    # that dpkg could delete while a separately owned transient probe remains.
    assert not (production_payload / "run").exists()


def test_packaged_probe_dropin_bounds_queued_jobs(production_payload):
    path = ("usr/lib/systemd/system/onpc-execution-probe-.service.d/"
            "oh-no-parent-control-timeout.conf")
    dropin = production_payload / path
    config = configparser.ConfigParser(interpolation=None)
    config.read(dropin)
    assert config.sections() == ["Unit"]
    assert dict(config["Unit"]) == {"jobtimeoutsec": "4s"}
    assert dropin.stat().st_mode & 0o7777 == 0o644
    manifest = json.loads((production_payload / (
        "usr/share/oh-no-parent-control/package-activation.json")).read_text())
    assert next(entry for entry in manifest["files"] if entry["path"] == path) == {
        "path": path, "activation": "reboot",
        "sha256": hashlib.sha256(dropin.read_bytes()).hexdigest(),
    }


def test_final_package_hook_refreshes_stripped_binary_digests(production_payload, tmp_path):
    path = "usr/libexec/oh-no-parent-control-execution-probe-gate"
    binary = tmp_path / path
    binary.parent.mkdir(parents=True)
    shutil.copyfile(production_payload / path, binary)
    before = hashlib.sha256(binary.read_bytes()).hexdigest()
    subprocess.run(["strip", str(binary)], check=True, capture_output=True)
    after = hashlib.sha256(binary.read_bytes()).hexdigest()
    assert after != before
    result = subprocess.run(
        ["make", "--no-print-directory", "-f", "debian/rules",
         "execute_before_dh_md5sums", f"PACKAGE_STAGING_ROOT={tmp_path}"],
        cwd=ROOT, capture_output=True, text=True, timeout=10,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    manifest = json.loads((tmp_path / (
        "usr/share/oh-no-parent-control/package-activation.json")).read_text())
    assert manifest["files"] == [{
        "path": path, "sha256": after, "activation": "process-restart",
    }]
    sequence = subprocess.run(["dh", "binary", "--no-act"], cwd=ROOT,
                              capture_output=True, text=True, timeout=10)
    assert sequence.returncode == 0, sequence.stdout + sequence.stderr
    commands = [line.strip() for line in sequence.stdout.splitlines()]
    assert commands.index("dh_strip -a") < commands.index(
        "debian/rules execute_before_dh_md5sums") < commands.index("dh_md5sums")


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
