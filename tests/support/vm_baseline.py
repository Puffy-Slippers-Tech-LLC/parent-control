"""Host-safe retained-baseline doubles: real temporary files, mocked VM APIs."""

import copy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import prepare_host as host
import prepare_vm as guest
from tests.support.paths import ROOT

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
