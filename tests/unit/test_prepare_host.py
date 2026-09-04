"""Capture acceptance with real private files and mocked VM/image operations."""

import copy
import json
import os
import stat
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/integration"))
import prepare_host as host
import prepare_vm as guest
sys.path.pop(0)

UUID = "f95890e1-88e7-4779-8ae3-53fdcc34330a"
SCRIPT_DIGEST = guest.preparation_digest(ROOT)


def xml(disk):
    return f"""<domain type='kvm'><name>ubuntu26.04</name><uuid>{UUID}</uuid><devices>
      <disk type='file' device='disk'><driver type='qcow2'/><source file='{disk}'/>
      <target dev='vda'/></disk>
      <disk type='file' device='cdrom'><target dev='sda'/><readonly/></disk>
      <filesystem type='mount'><driver type='virtiofs'/><source dir='/Data'/><target dir='Data'/></filesystem>
      </devices></domain>"""


class Source:
    def __init__(self, disk):
        self.layout = host.domain_layout(xml(disk), UUID)
        self.off = False
        self.shutdown_calls = 0
        self.timeout = False
        self.baseline_xml = None
        self.creations = []
        self.after_create = lambda: None

    def snapshot(self):
        return copy.deepcopy(self.layout), self.off

    def shutdown(self, revalidate, requested):
        revalidate()
        self.shutdown_calls += 1
        if self.timeout:
            raise host.CaptureError("shutdown:timeout")
        self.off = True

    def baseline(self):
        return self.baseline_xml

    def create_baseline(self, layout, description):
        assert self.off
        assert layout == self.layout
        assert self.baseline_xml is None
        self.creations.append(description)
        self.baseline_xml = snapshot_xml(Path(layout["disk"]), description)
        self.commands.snapshots.append({"id": "1", "name": host.SNAPSHOT, "date-sec": 100,
                                        "date-nsec": 0, "vm-state-size": 0})
        # Internal snapshot metadata changes the current image in place.
        path = Path(layout["disk"])
        path.write_bytes(path.read_bytes() + b";internal-snapshot")
        self.after_create()


def snapshot_xml(disk, description):
    root = host.ET.Element("domainsnapshot")
    host.ET.SubElement(root, "name").text = host.SNAPSHOT
    host.ET.SubElement(root, "description").text = description
    host.ET.SubElement(root, "state").text = "shutoff"
    host.ET.SubElement(root, "creationTime").text = "100"
    host.ET.SubElement(root, "memory", snapshot="no")
    disks = host.ET.SubElement(root, "disks")
    host.ET.SubElement(disks, "disk", name="vda", snapshot="internal")
    host.ET.SubElement(disks, "disk", name="sda", snapshot="no")
    root.append(host.ET.fromstring(xml(disk)))
    return host.ET.tostring(root, encoding="unicode")


class Images:
    def __init__(self, top, anchor):
        self.top, self.anchor = top, anchor
        self.lock_fd = None
        self.snapshots = []
        self.info_change = lambda path, info: info
        self.checked = []

    def info(self, path, active=False):
        data = {"format": "qcow2", "virtual-size": 4096}
        if path == self.top:
            data.update({"snapshots": copy.deepcopy(self.snapshots), "backing-filename": str(self.anchor), "backing-filename-format": "qcow2",
                         "full-backing-filename": str(self.anchor)})
        return self.info_change(path, data)

    def check(self, path):
        self.checked.append(path)


@pytest.fixture
def rig(tmp_path):
    anchor, top = tmp_path / "ubuntu26.04.qcow2", tmp_path / "ubuntu26.04.overlay"
    anchor.write_bytes(b"base data")
    top.write_bytes(b"overlay data")
    source, commands = Source(top), Images(top, anchor)
    source.commands = commands
    record = {"preparation_record_sha256": "b" * 64, "preparation_script_sha256": SCRIPT_DIGEST,
              "ubuntu_version": "26.04", "accounts": {
                  item.username: {"uid": 1000 + i, "role": item.role}
                  for i, item in enumerate(guest.IDENTITIES)}}
    inspect = Mock(return_value=record)
    directory = tmp_path / "baselines"

    def capture():
        return host.Capture(source, commands, inspect, anchor=anchor, directory=directory,
                            script_digest=SCRIPT_DIGEST)

    return SimpleNamespace(anchor=anchor, top=top, source=source, commands=commands,
                           inspect=inspect, directory=directory, capture=capture)


def state(rig):
    return json.loads((rig.directory / "phase.json").read_text())


def test_capture_creates_named_internal_snapshot_without_copy(rig):
    before = host.digest(rig.anchor)
    rig.capture().run()
    assert state(rig)["phase"] == "finalized"
    assert rig.source.off
    assert rig.source.shutdown_calls == 1
    assert len(rig.source.creations) == 1
    assert state(rig)["proof"]["name"] == "oh-no-parent-control-baseline"
    assert state(rig)["proof"]["storage"] == "internal"
    assert host.digest(rig.anchor) == before
    assert {path.name for path in rig.directory.iterdir()} == {".lock", "phase.json"}
    assert set(rig.commands.checked) == {rig.top}
    assert not hasattr(host.Commands, "convert")
    assert "machine_id" not in json.dumps(state(rig))
    assert "password" not in json.dumps(state(rig))


def test_capture_repairs_an_empty_misowned_or_moded_state_directory(rig):
    rig.directory.mkdir(mode=0o700)
    rig.directory.chmod(0o2700)

    rig.capture().run()

    assert stat.S_IMODE(rig.directory.stat().st_mode) == 0o700
    assert state(rig)["phase"] == "finalized"


def test_capture_preserves_nonempty_invalid_state_directory(rig):
    rig.directory.mkdir(mode=0o700)
    (rig.directory / "untrusted-state").write_text("retain")
    rig.directory.chmod(0o2700)

    with pytest.raises(host.CaptureError, match="baseline-directory"):
        rig.capture().run()

    assert (rig.directory / "untrusted-state").read_text() == "retain"
    assert rig.source.shutdown_calls == 0


@pytest.mark.parametrize("running", [False, True])
def test_repeat_preserves_baseline_after_product_testing(rig, running):
    rig.capture().run()
    original = state(rig)
    rig.top.write_bytes(b"product installed; changed current guest state")
    rig.source.off = not running
    rig.inspect.side_effect = AssertionError("must not inspect the testing guest")
    rig.capture().run()
    assert state(rig) == original
    assert len(rig.source.creations) == 1
    assert rig.source.shutdown_calls == 1
    assert rig.top.read_bytes() == b"product installed; changed current guest state"
    assert rig.source.off == (not running)


@pytest.mark.parametrize("change", [
    lambda value: value.replace("ubuntu26.04</name>", "another</name>"),
    lambda value: value.replace(UUID, "00000000-0000-0000-0000-000000000000"),
    lambda value: value.replace("device='disk'", "device='lun'"),
    lambda value: value.replace("type='file' device='disk'", "type='block' device='disk'"),
    lambda value: value.replace("type='qcow2'", "type='raw'"),
    lambda value: value.replace("<target dev='vda'/>", "<readonly/><target dev='vda'/>"),
    lambda value: value.replace("<target dev='vda'/>", "<mirror/><target dev='vda'/>"),
    lambda value: value.replace("<target dev='vda'/>", "<shareable/><target dev='vda'/>"),
    lambda value: value.replace("<target dev='sda'/>", "<source file='/tmp/media.iso'/><target dev='sda'/>"),
    lambda value: value.replace("<source dir='/Data'/>", "<source dir='/home'/>") ,
    lambda value: value.replace("</devices>", "<hostdev/></devices>"),
    lambda value: value.replace("</devices>", "<tpm/></devices>"),
    lambda value: value.replace("</domain>", "<os><nvram>/tmp/firmware</nvram></os></domain>"),
    lambda value: value.replace("</devices>", "<disk type='file' device='disk'/></devices>"),
    lambda value: "<!DOCTYPE domain>" + value,
])
def test_domain_layout_refuses_ambiguous_storage(change, rig):
    with pytest.raises(host.CaptureError):
        host.domain_layout(change(xml(rig.top)), UUID)


def test_malformed_xml_refused():
    with pytest.raises(host.ET.ParseError):
        host.domain_layout("<domain", UUID)


@pytest.mark.parametrize("kind", ["anchor-typo", "symlink", "missing", "other-chain", "cycle", "raw",
                                  "backing-format", "external-data", "encrypted"])
def test_source_refusals_precede_shutdown_and_file_creation(rig, kind):
    if kind == "anchor-typo":
        rig.source.layout["disk"] = "/Data/virt-managewr/ubuntu26.04.qcow2"
    elif kind == "symlink":
        target = rig.top.with_suffix(".real")
        rig.top.rename(target)
        rig.top.symlink_to(target)
    elif kind == "missing":
        rig.anchor.unlink()
    else:
        def change(path, info):
            if kind == "other-chain" and path == rig.top:
                return {"format": "qcow2", "virtual-size": 4096}
            if kind == "cycle" and path == rig.top:
                return {**info, "backing-filename": str(rig.top), "full-backing-filename": str(rig.top)}
            return {**info, **{
                "raw": {"format": "raw"}, "backing-format": {"backing-filename-format": "raw"},
                "external-data": {"format-specific": {"data": {"data-file": "/tmp/unowned"}}},
                "encrypted": {"encrypted": True},
            }.get(kind, {})}
        rig.commands.info_change = change
    with pytest.raises((host.CaptureError, OSError)):
        rig.capture().run()
    assert not rig.directory.exists()
    assert rig.source.shutdown_calls == 0


@pytest.mark.parametrize("metadata", [True, False])
def test_existing_unowned_snapshot_is_never_overwritten(rig, metadata):
    if metadata:
        rig.source.baseline_xml = snapshot_xml(rig.top, "another operator")
    else:
        rig.commands.snapshots = [{"name": host.SNAPSHOT}]
    with pytest.raises(host.CaptureError, match="already-exists"):
        rig.capture().run()
    assert not rig.source.creations
    assert rig.source.shutdown_calls == 0
    assert not rig.directory.exists()


def test_unrelated_internal_snapshots_are_preserved(rig):
    rig.commands.snapshots = [{"name": "existing-unrelated-snapshot"}]
    rig.capture().run()
    assert state(rig)["phase"] == "finalized"
    assert rig.commands.snapshots[0]["name"] == "existing-unrelated-snapshot"


def test_shutdown_timeout_preserves_source_and_exact_phase(rig):
    rig.source.timeout = True
    with pytest.raises(host.CaptureError, match="shutdown:timeout"):
        rig.capture().run()
    assert not rig.source.off
    assert state(rig)["phase"] == "shutdown-requested"
    assert not rig.source.creations
    rig.source.timeout = False
    rig.capture().run()
    assert state(rig)["phase"] == "finalized"


@pytest.mark.parametrize("category", ["guest:residue:package", "guest:marker-permissions", "guest:script-digest"])
def test_inspection_refusal_creates_no_snapshot(rig, category):
    rig.inspect.side_effect = host.CaptureError(category)
    with pytest.raises(host.CaptureError, match=category):
        rig.capture().run()
    assert state(rig)["phase"] == "source-off"
    assert not rig.source.creations


def interrupt_snapshot(rig):
    def interrupt():
        raise KeyboardInterrupt
    rig.source.after_create = interrupt
    with pytest.raises(KeyboardInterrupt):
        rig.capture().run()
    rig.source.after_create = lambda: None
    assert state(rig)["phase"] == "snapshot-requested"


def test_interruption_after_libvirt_success_verifies_without_recreation(rig):
    interrupt_snapshot(rig)
    rig.inspect.side_effect = AssertionError("saved snapshot already inspected")
    rig.capture().run()
    assert len(rig.source.creations) == 1
    assert state(rig)["phase"] == "finalized"


@pytest.mark.parametrize("phase", host.PHASES)
def test_every_durable_phase_is_restartable(rig, monkeypatch, phase):
    save = host.Capture.save
    tripped = False
    def interrupt(self, value):
        nonlocal tripped
        save(self, value)
        if value == phase and not tripped:
            tripped = True
            raise KeyboardInterrupt
    with monkeypatch.context() as patch:
        patch.setattr(host.Capture, "save", interrupt)
        with pytest.raises(KeyboardInterrupt):
            rig.capture().run()
    rig.capture().run()
    assert state(rig)["phase"] == "finalized"
    assert len(rig.source.creations) == 1


@pytest.mark.parametrize("kind", ["domain", "top-inode", "anchor-inode", "backing-digest", "active",
                                  "description", "disk-record", "directory"])
def test_interrupted_snapshot_refuses_changed_identity_without_replacement(rig, kind):
    interrupt_snapshot(rig)
    if kind == "domain":
        rig.source.layout["uuid"] = "different"
    elif kind in {"top-inode", "anchor-inode"}:
        path = rig.top if kind == "top-inode" else rig.anchor
        path.rename(path.with_suffix(".old"))
        path.write_bytes(b"replacement")
    elif kind == "backing-digest":
        rig.anchor.write_bytes(b"changed")
    elif kind == "active":
        rig.source.off = False
    elif kind == "description":
        rig.source.baseline_xml = snapshot_xml(rig.top, "unrelated operation")
    elif kind == "disk-record":
        rig.commands.snapshots = []
    elif kind == "directory":
        rig.directory.chmod(0o777)
    with pytest.raises(host.CaptureError):
        rig.capture().run()
    assert len(rig.source.creations) == 1
    assert state(rig)["phase"] == "snapshot-requested"


@pytest.mark.parametrize("kind", ["missing-metadata", "missing-disk", "replaced-disk", "backing-digest", "metadata"])
def test_finalized_snapshot_reuse_detects_missing_or_changed_baseline(rig, kind):
    rig.capture().run()
    if kind == "missing-metadata":
        rig.source.baseline_xml = None
    elif kind == "missing-disk":
        rig.commands.snapshots = []
    elif kind == "replaced-disk":
        rig.commands.snapshots[0]["id"] = "new"
    elif kind == "backing-digest":
        rig.anchor.write_bytes(b"changed")
    else:
        rig.source.baseline_xml = rig.source.baseline_xml.replace("<creationTime>100", "<creationTime>200")
    with pytest.raises(host.CaptureError):
        rig.capture().run()
    assert len(rig.source.creations) == 1


def guest_fixture():
    accounts = {item.username: {"uid": 1000 + i, "role": item.role} for i, item in enumerate(guest.IDENTITIES)}
    marker = guest.marker_document(guest.GuestIdentity("ubuntu26.04", "a" * 32, "26.04", "kvm"),
                                   accounts, SCRIPT_DIGEST)
    files = {str(guest.MARKER): host.encode(marker), "/etc/hostname": b"ubuntu26.04\n",
             "/etc/machine-id": b"a" * 32, "/var/lib/dpkg/status": b"Package: bash\nStatus: install ok installed\n"}
    files["/etc/passwd"] = "\n".join(
        f"{item.username}:x:{1000+i}:{1000+i}:{item.display_name}:/home/{item.username}:/bin/bash"
        for i, item in enumerate(guest.IDENTITIES)).encode()
    files["/etc/group"] = ("adm:x:4:onpc-parent-jamie,onpc-parent-casey\n"
                           "sudo:x:27:onpc-parent-jamie,onpc-parent-casey\n").encode()
    g = Mock()
    g.inspect_os.return_value = ["/dev/sda2"]
    g.inspect_get_distro.return_value = "ubuntu"
    g.inspect_get_major_version.return_value = 26
    g.inspect_get_minor_version.return_value = 4
    g.inspect_get_mountpoints.return_value = {"/": "/dev/sda2", "/boot/efi": "/dev/sda1"}
    g.lstatns.return_value = {"st_mode": stat.S_IFREG | 0o600, "st_uid": 0, "st_gid": 0}
    g.read_file.side_effect = lambda path: files[path]
    g.exists.side_effect = lambda path: path in files
    g.is_symlink.return_value = False
    g.glob_expand.return_value = []
    return SimpleNamespace(g=g, files=files, marker=marker, module=SimpleNamespace(GuestFS=Mock(return_value=g)))


def test_offline_inspection_is_explicitly_readonly_and_preserves_only_safe_fields():
    fixture = guest_fixture()
    result = host.inspect_guest(fixture.module, Path("/tmp/top.qcow2"), SCRIPT_DIGEST)
    fixture.g.add_drive_opts.assert_called_once_with("/tmp/top.qcow2", readonly=True, format="qcow2")
    assert fixture.g.mount_ro.call_count == 2
    fixture.g.close.assert_called_once()
    assert set(result) == {"preparation_record_sha256", "preparation_script_sha256", "ubuntu_version", "accounts"}


@pytest.mark.parametrize("category,path", [(category, path) for category, paths in guest.RESIDUE_PATHS.items()
                                           for path in paths])
def test_offline_inspection_rejects_every_residue_path(category, path):
    fixture = guest_fixture()
    fixture.files[path] = b"residue"
    with pytest.raises(host.CaptureError, match=f"guest:residue:{category}"):
        host.inspect_guest(fixture.module, Path("/tmp/top.qcow2"), SCRIPT_DIGEST)
    fixture.g.close.assert_called_once()


@pytest.mark.parametrize("kind", ["schema", "owner", "symlink", "permissions", "digest", "release", "hostname",
                                  "machine-id", "uid", "role", "package", "pam", "kiosk", "duplicate-json"])
def test_offline_inspection_refusals(kind):
    fixture = guest_fixture()
    if kind in {"schema", "digest"}:
        if kind == "schema":
            fixture.marker["extra"] = True
        else:
            fixture.marker["preparation_script_sha256"] = "c" * 64
        fixture.files[str(guest.MARKER)] = host.encode(fixture.marker)
    elif kind == "owner":
        fixture.g.lstatns.return_value["st_uid"] = 1000
    elif kind in {"symlink", "permissions"}:
        fixture.g.lstatns.return_value["st_mode"] = (stat.S_IFLNK | 0o600) if kind == "symlink" else (stat.S_IFREG | 0o644)
    elif kind == "release":
        fixture.g.inspect_get_major_version.return_value = 24
    elif kind == "hostname":
        fixture.files["/etc/hostname"] = b"other"
    elif kind == "machine-id":
        fixture.files["/etc/machine-id"] = b"b" * 32
    elif kind == "uid":
        fixture.files["/etc/passwd"] = fixture.files["/etc/passwd"].replace(b":1002:", b":1001:")
    elif kind == "role":
        fixture.files["/etc/group"] += b"sudo:x:27:onpc-child-riley\n"
    elif kind == "package":
        fixture.files["/var/lib/dpkg/status"] += b"\nPackage: oh-no-parent-control\nStatus: deinstall ok config-files\n"
    elif kind == "pam":
        fixture.files[guest.PAM_FILES_TO_SCAN[0]] = b"pam_oh_no_parent_control.so"
    elif kind == "kiosk":
        fixture.files["/etc/passwd"] += b"\noh-no-parent-control:x:123:123::/home/kiosk:/bin/bash"
    else:
        fixture.files[str(guest.MARKER)] = b'{"purpose":1,"purpose":2}'
    with pytest.raises((host.CaptureError, guest.PreparationError)):
        host.inspect_guest(fixture.module, Path("/tmp/top.qcow2"), SCRIPT_DIGEST)
    fixture.g.close.assert_called_once()


def libvirt_fixture(rig):
    api = Mock(VIR_DOMAIN_RUNNING=1, VIR_DOMAIN_SHUTOFF=5, VIR_DOMAIN_XML_INACTIVE=2,
               VIR_DOMAIN_EVENT_ID_LIFECYCLE=0, VIR_DOMAIN_SHUTDOWN_ACPI_POWER_BTN=1,
               VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC=128, VIR_ERR_NO_DOMAIN_SNAPSHOT=72)
    class LibvirtError(Exception):
        def get_error_code(self):
            return self.args[0]
    api.libvirtError = LibvirtError
    domain = api.open.return_value.lookupByName.return_value
    api.open.return_value.getURI.return_value = host.URI
    domain.UUIDString.return_value = UUID
    domain.isPersistent.return_value = True
    domain.hasManagedSaveImage.return_value = False
    domain.state.return_value = (1, 0)
    domain.XMLDesc.return_value = xml(rig.top)
    domain.blockJobInfo.return_value = {}
    existing = Mock()
    existing.getName.return_value = host.SNAPSHOT
    domain.listAllSnapshots.return_value = [existing]
    return api, domain


def test_libvirt_creates_offline_internal_snapshot_with_metadata(rig):
    api, domain = libvirt_fixture(rig)
    domain.state.return_value = (5, 0)
    domain.listAllSnapshots.return_value = []
    source = host.LibvirtSource(api)
    source.create_baseline(rig.source.layout, "preparation record")
    document, flags = domain.snapshotCreateXML.call_args.args
    root = host.ET.fromstring(document)
    assert root.findtext("name") == host.SNAPSHOT
    assert root.findtext("description") == "preparation record"
    assert root.find("memory").attrib == {"snapshot": "no"}
    assert root.find("disks/disk").attrib == {"name": "vda", "snapshot": "internal"}
    assert not root.findall(".//source")
    assert flags == 128
    domain.revertToSnapshot.assert_not_called()
    domain.destroy.assert_not_called()


@pytest.mark.parametrize("condition", ["running", "existing", "lookup-error"])
def test_libvirt_refuses_unsafe_snapshot_creation(rig, condition):
    api, domain = libvirt_fixture(rig)
    if condition != "running":
        domain.state.return_value = (5, 0)
    if condition == "lookup-error":
        domain.listAllSnapshots.side_effect = api.libvirtError(1)
    with pytest.raises((host.CaptureError, api.libvirtError)):
        host.LibvirtSource(api).create_baseline(rig.source.layout, "record")
    domain.snapshotCreateXML.assert_not_called()


@pytest.mark.parametrize("change", [
    lambda doc: doc.replace("<state>shutoff", "<state>running"),
    lambda doc: doc.replace('snapshot="internal"', 'snapshot="external"'),
    lambda doc: doc.replace('<memory snapshot="no"', '<memory snapshot="internal"'),
    lambda doc: doc.replace('<creationTime>100', '<creationTime>invalid'),
    lambda doc: doc.replace(UUID, "00000000-0000-0000-0000-000000000000"),
    lambda doc: doc.replace('<name>oh-no-parent-control-baseline', '<name>unrelated'),
])
def test_snapshot_proof_rejects_wrong_type_or_identity(rig, change):
    with pytest.raises(host.CaptureError):
        host.snapshot_proof(change(snapshot_xml(rig.top, "record")), rig.source.layout, "record")


def test_completed_snapshot_survives_preparation_script_updates(rig):
    rig.capture().run()
    capture = rig.capture()
    capture.script_digest = "c" * 64
    capture.run()
    assert len(rig.source.creations) == 1


@pytest.mark.parametrize("kind", ["missing", "uri", "uuid", "block-job", "managed-save", "paused", "pending-disk"])
def test_libvirt_refusals(rig, kind):
    api, domain = libvirt_fixture(rig)
    if kind == "missing":
        api.open.return_value.lookupByName.side_effect = RuntimeError("not found")
    elif kind == "uri":
        api.open.return_value.getURI.return_value = "qemu:///session"
    elif kind == "uuid":
        domain.UUIDString.return_value = "not-a-uuid"
    elif kind == "block-job":
        domain.blockJobInfo.return_value = {"type": 1}
    elif kind == "managed-save":
        domain.hasManagedSaveImage.return_value = True
    elif kind == "paused":
        domain.state.return_value = (3, 0)
    else:
        domain.XMLDesc.side_effect = lambda flags: xml(rig.top if flags == 0 else rig.anchor)
    with pytest.raises((host.CaptureError, RuntimeError, ValueError)):
        host.LibvirtSource(api).snapshot()
    domain.shutdownFlags.assert_not_called()


@pytest.mark.parametrize("timeout", [False, True])
def test_shutdown_uses_bounded_libvirt_event_loop(rig, timeout, monkeypatch):
    api, domain = libvirt_fixture(rig)
    source = host.LibvirtSource(api)
    timer_callback = None

    def add_timer(milliseconds, callback, opaque):
        nonlocal timer_callback
        assert milliseconds == 180000
        timer_callback = callback
        return 11

    def dispatch(_timeout):
        if timeout:
            timer_callback(11, None)
        else:
            domain.state.return_value = (5, 0)
        return True

    api.virEventAddTimeout.side_effect = add_timer
    event = Mock()
    event.wait.side_effect = dispatch
    monkeypatch.setattr(host.threading, "Event", Mock(return_value=event))
    if timeout:
        with pytest.raises(host.CaptureError, match="shutdown:timeout"):
            source.shutdown(Mock(), requested=False)
    else:
        source.shutdown(Mock(), requested=False)
    domain.shutdownFlags.assert_called_once_with(1)
    api.virEventRemoveTimeout.assert_called_once_with(11)
    api.open.return_value.domainEventDeregisterAny.assert_called_once()
    domain.destroy.assert_not_called()


def test_command_adapter_only_inspects_and_checks_explicit_qcow2():
    commands = host.Commands()
    commands.run = Mock(return_value=b'{"format":"qcow2"}')
    commands.info(Path("/tmp/source"), active=True)
    assert "-U" in commands.run.call_args.args[0]
    commands.check(Path("/tmp/output"))
    assert "-r" not in commands.run.call_args.args[0]


def test_missing_tool_diagnostic_has_no_vm_connection_or_writes(monkeypatch, capsys):
    monkeypatch.setattr(host.shutil, "which", lambda _name: None)
    connect = Mock()
    monkeypatch.setattr(host, "LibvirtSource", connect)
    assert host.main(["--check-tools"]) == 1
    assert "run ./setup.sh" in capsys.readouterr().err
    connect.assert_not_called()


def test_capture_accepts_installed_product_on_host(monkeypatch):
    worker = Mock()
    monkeypatch.setattr(host.threading, "Thread", Mock(return_value=worker))
    monkeypatch.setattr(host.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(host.importlib, "import_module", Mock())
    monkeypatch.setattr(host.os, "geteuid", lambda: 0)
    monkeypatch.setattr(host.os, "getegid", lambda: 0)
    residue = Mock(return_value="package")
    monkeypatch.setattr(guest, "find_residue", residue)
    source = Mock()
    monkeypatch.setattr(host, "LibvirtSource", Mock(return_value=source))
    capture = Mock()
    capture.run.side_effect = lambda: worker.start.assert_called_once_with()
    monkeypatch.setattr(host, "Capture", Mock(return_value=capture))

    assert host.main([]) == 0
    residue.assert_not_called()
    capture.run.assert_called_once_with()
    source.close.assert_called_once_with()


def test_absent_baseline_is_listed_without_error_lookup(rig):
    api, domain = libvirt_fixture(rig)
    domain.listAllSnapshots.return_value = []
    assert host.LibvirtSource(api).baseline() is None
    domain.snapshotLookupByName.assert_not_called()


def test_event_dispatch_continues_while_capture_blocks(monkeypatch):
    api = Mock()
    request = host.threading.Event()
    answered = host.threading.Event()
    finished = host.threading.Event()
    def dispatch():
        if not request.wait(5):
            raise RuntimeError("test deadline")
        answered.set()
        finished.wait(5)
        raise RuntimeError("test loop finished")
    api.virEventRunDefaultImpl.side_effect = dispatch
    monkeypatch.setattr(host.importlib, "import_module", lambda _name: api)
    monkeypatch.setattr(host.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(host.os, "geteuid", lambda: 0)
    monkeypatch.setattr(host.os, "getegid", lambda: 0)
    monkeypatch.setattr(host, "LibvirtSource", Mock())
    capture = Mock()
    def blocked_capture():
        request.set()
        assert answered.wait(5), "libvirt dispatch stopped during capture"
    capture.run.side_effect = blocked_capture
    monkeypatch.setattr(host, "Capture", Mock(return_value=capture))
    try:
        assert host.main([]) == 0
    finally:
        finished.set()


def test_resource_arguments_are_not_operator_overrides():
    with pytest.raises(SystemExit):
        host.main(["--anchor", "/tmp/another"])


def test_disk_integrity_failure_prevents_snapshot_creation(rig):
    rig.commands.check = Mock(side_effect=host.CaptureError("command:failed"))
    with pytest.raises(host.CaptureError, match="command:failed"):
        rig.capture().run()
    assert state(rig)["phase"] == "source-off"
    assert not rig.source.creations


def test_source_change_during_inspection_prevents_snapshot_creation(rig):
    def change(_disk, _sha):
        rig.top.write_bytes(b"changed while inspecting")
        return rig.inspect.return_value
    rig.inspect.side_effect = change
    with pytest.raises(host.CaptureError, match="source-digest-changed"):
        rig.capture().run()
    assert not rig.source.creations


def test_partial_internal_snapshot_without_libvirt_metadata_is_preserved(rig):
    interrupt_snapshot(rig)
    rig.source.baseline_xml = None
    records = copy.deepcopy(rig.commands.snapshots)
    with pytest.raises(host.CaptureError, match="already-exists"):
        rig.capture().run()
    assert rig.commands.snapshots == records
    assert len(rig.source.creations) == 1


@pytest.mark.parametrize("kind", ["schema", "mode", "operation", "directory", "phase"])
def test_invalid_phase_record_refuses_recovery(rig, kind):
    interrupt_snapshot(rig)
    path = rig.directory / "phase.json"
    doc = state(rig)
    if kind == "schema":
        doc["schema_version"] = 1
    elif kind == "mode":
        path.chmod(0o644)
    elif kind == "operation":
        doc["operation"] = "bad"
    elif kind == "directory":
        doc["directory"]["inode"] += 1
    else:
        doc["phase"] = "conversion-in-progress"
    path.write_bytes(host.encode(doc))
    with pytest.raises(host.CaptureError):
        rig.capture().run()
    assert len(rig.source.creations) == 1


def test_lock_refuses_a_second_controller_without_signalling_or_deleting(rig):
    interrupt_snapshot(rig)
    with open(rig.directory / ".lock", "rb") as lock:
        host.fcntl.flock(lock.fileno(), host.fcntl.LOCK_EX | host.fcntl.LOCK_NB)
        with pytest.raises(host.CaptureError, match="busy-controller"):
            rig.capture().run()
    assert len(rig.source.creations) == 1


def test_symlink_baseline_directory_is_refused(rig):
    target = rig.directory.with_name("other")
    target.mkdir(mode=0o700)
    rig.directory.symlink_to(target, target_is_directory=True)
    with pytest.raises(host.CaptureError):
        rig.capture().run()
    assert not list(target.iterdir())
    assert rig.source.shutdown_calls == 0


def test_offline_inspection_detects_service_in_local_unit_search_directory():
    fixture = guest_fixture()
    fixture.g.glob_expand.side_effect = lambda pattern: (
        ["/usr/local/lib/systemd/system/oh-no-parent-control-broker.service"]
        if pattern.startswith("/usr/local/lib/systemd") else [])
    with pytest.raises(host.CaptureError, match="guest:residue:service-session"):
        host.inspect_guest(fixture.module, Path("/tmp/top.qcow2"), SCRIPT_DIGEST)
