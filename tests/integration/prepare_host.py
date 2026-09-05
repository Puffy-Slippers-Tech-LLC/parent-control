#!/usr/bin/python3
"""Create a reusable internal baseline snapshot of the existing ubuntu26.04 VM.

Only main() selects real resources. Injectable adapters are for host-safe tests.
The journal binds the named libvirt snapshot to the inspected guest. Repeated
runs preserve that baseline, including after the VM has been used for testing.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import importlib
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import prepare_vm as guest_contract


URI = "qemu:///system"
DOMAIN = "ubuntu26.04"
ANCHOR = Path("/Data/virt-manager/ubuntu26.04.qcow2")
BASELINES = Path("/Data/virt-manager/oh-no-parent-control-baseline-state")
SNAPSHOT = "oh-no-parent-control-baseline"
PHASES = ("validation", "shutdown-requested", "source-off", "snapshot-requested", "finalized")


class CaptureError(RuntimeError):
    """Category-only errors deliberately exclude command output and guest data."""


def require(condition, category):
    if not condition:
        raise CaptureError(category)


def log(stage):
    print(f"prep-host: [{stage}]", file=sys.stderr, flush=True)


def canonical(path):
    path = Path(path)
    require(path.is_absolute() and path == path.resolve(strict=True), "guard:path")
    for part in (path, *path.parents):
        require(not part.is_symlink(), "guard:symlink")
    return path


def identity(path, *, private=False, mode=None):
    path = canonical(path)
    info = path.lstat()
    require(stat.S_ISREG(info.st_mode), "guard:file-type")
    if private:
        require(info.st_uid == os.geteuid() and info.st_gid == os.getegid(), "guard:owner")
    if mode is not None:
        require(stat.S_IMODE(info.st_mode) == mode, "guard:mode")
    return {"path": str(path), "device": info.st_dev, "inode": info.st_ino}


def digest(path):
    before = identity(path)
    with open(path, "rb") as stream:
        info = os.fstat(stream.fileno())
        require((info.st_dev, info.st_ino) == (before["device"], before["inode"]), "guard:file-changed")
        result = hashlib.file_digest(stream, "sha256").hexdigest()
        after = os.fstat(stream.fileno())
    require((info.st_size, info.st_mtime_ns, info.st_ctime_ns) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns), "guard:file-changed")
    require(identity(path) == before, "guard:file-changed")
    return result


def sync_directory(path):
    descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def encode(document):
    return (json.dumps(document, sort_keys=True, indent=2) + "\n").encode()


def parse_json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, "guard:duplicate-json-key")
            result[key] = value
        return result
    return json.loads(data, object_pairs_hook=unique)


class Commands:
    """Every signal targets a pidfd for the child just spawned by this object.

    The inherited journal lock survives controller SIGKILL until the child exits.
    A subsequent invocation refuses that lock instead of discovering/signalling
    a process from disk metadata or a /proc scan.
    """

    def __init__(self):
        self.lock_fd = None

    def run(self, arguments, *, timeout=120):
        with subprocess.Popen(arguments, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                              stderr=subprocess.DEVNULL,
                              pass_fds=(() if self.lock_fd is None else (self.lock_fd,))) as child:
            pidfd = os.pidfd_open(child.pid)
            try:
                try:
                    output, _ = child.communicate(timeout=timeout)
                except BaseException:
                    # pidfd stays bound to this child even if its PID is reused.
                    try:
                        signal.pidfd_send_signal(pidfd, signal.SIGTERM)
                    except ProcessLookupError:
                        pass
                    try:
                        child.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        signal.pidfd_send_signal(pidfd, signal.SIGKILL)
                        child.wait(timeout=10)
                    raise
            finally:
                os.close(pidfd)
        require(child.returncode == 0, "command:failed")
        return output

    def info(self, path, active=False):
        arguments = ["qemu-img", "info", "--output=json", "-f", "qcow2"]
        if active:
            arguments.append("-U")  # Public read-only information option.
        return parse_json(self.run([*arguments, str(path)]))

    def check(self, path):
        self.run(["qemu-img", "check", "-f", "qcow2", str(path)], timeout=7200)


def domain_layout(xml, expected_uuid):
    require("<!" not in xml, "guard:xml")
    root = ET.fromstring(xml)
    require(root.tag == "domain" and root.get("type") == "kvm", "guard:domain-type")
    require(len(root.findall("name")) == len(root.findall("uuid")) == 1, "guard:xml")
    require(root.findtext("name") == DOMAIN and root.findtext("uuid") == expected_uuid, "guard:domain-identity")
    require(len(root.findall("devices")) == 1, "guard:xml")
    disks = root.findall("devices/disk")
    system_disks = [disk for disk in disks if disk.get("device") == "disk"]
    require(len(system_disks) == 1, "guard:disk-count")
    optical = [disk for disk in disks if disk not in system_disks]
    require(len(optical) <= 1 and all(disk.get("type") == "file" and disk.get("device") == "cdrom" and
                                    disk.find("readonly") is not None and disk.find("source") is None
                                    for disk in optical), "guard:unexpected-device")
    disk = system_disks[0]
    require(disk.get("type") == "file" and disk.get("device") == "disk", "guard:disk-type")
    require(all(disk.find(name) is None for name in
                ("readonly", "shareable", "mirror", "auth", "encryption", "dataStore")), "guard:disk-layout")
    require(len(disk.findall("source")) == len(disk.findall("driver")) == len(disk.findall("target")) == 1,
            "guard:disk-layout")
    source = disk.find("source")
    require(set(source.attrib) <= {"file", "index"} and bool(source.get("file")), "guard:disk-source")
    require(disk.find("driver").get("type") == "qcow2", "guard:disk-format")
    target = disk.find("target").get("dev", "")
    require(re.fullmatch(r"(?:vd|sd)[a-z]+", target), "guard:disk-target")
    require(not root.findall("devices/hostdev"), "guard:host-device")
    # Offline internal disk snapshots do not capture external firmware/TPM state.
    require(root.find("os/nvram") is None and not root.findall("devices/tpm"),
            "guard:external-device-state")
    shares = []
    for share in root.findall("devices/filesystem"):
        require(share.get("type") == "mount" and share.find("driver") is not None and
                share.find("driver").get("type") == "virtiofs" and
                share.find("source") is not None and share.find("source").get("dir") == "/Data" and
                share.find("target") is not None and share.find("target").get("dir") in {"Data", "/Data"},
                "guard:filesystem-share")
        shares.append({"type": "virtiofs", "source": "/Data", "target": share.find("target").get("dir"),
                       "preparation_only": True})
    require(len(shares) <= 1, "guard:filesystem-share")
    return {"uuid": expected_uuid, "disk": source.get("file"), "target": target,
            "empty_optical_drive": bool(optical), "source_shares": shares}


class LibvirtSource:
    def __init__(self, libvirt):
        self.api = libvirt
        libvirt.virEventRegisterDefaultImpl()
        self.connection = libvirt.open(URI)
        require(self.connection is not None, "guard:connection")
        try:
            require(self.connection.getURI() == URI, "guard:connection")
            self.domain = self.connection.lookupByName(DOMAIN)
            self.uuid = self.domain.UUIDString()
            require(str(uuid.UUID(self.uuid)) == self.uuid, "guard:uuid")
        except BaseException:
            self.connection.close()
            raise

    def snapshot(self):
        require(self.connection.getURI() == URI, "guard:connection")
        domain = self.connection.lookupByName(DOMAIN)
        require(domain.UUIDString() == self.uuid and domain.isPersistent(), "guard:domain-identity")
        require(not domain.hasManagedSaveImage(0), "guard:managed-save")
        state = domain.state()[0]
        # An ACPI shutdown passes through SHUTDOWN before SHUTOFF. It is still
        # active storage and must never be mistaken for offline readiness.
        require(state in (self.api.VIR_DOMAIN_RUNNING, self.api.VIR_DOMAIN_SHUTDOWN,
                          self.api.VIR_DOMAIN_SHUTOFF), "guard:domain-state")
        layout = domain_layout(domain.XMLDesc(0), self.uuid)
        inactive = domain_layout(domain.XMLDesc(self.api.VIR_DOMAIN_XML_INACTIVE), self.uuid)
        require(inactive == layout, "guard:pending-disk-change")
        if state != self.api.VIR_DOMAIN_SHUTOFF:
            require(not domain.blockJobInfo(layout["target"], 0), "guard:block-job")
        return layout, state == self.api.VIR_DOMAIN_SHUTOFF

    def shutdown(self, revalidate, requested, timeout=180):
        expired = False
        changed = threading.Event()

        def deadline(_timer, _opaque):
            nonlocal expired
            expired = True
            changed.set()

        callback = self.connection.domainEventRegisterAny(
            self.domain, self.api.VIR_DOMAIN_EVENT_ID_LIFECYCLE, lambda *_args: changed.set(), None)
        timer = self.api.virEventAddTimeout(timeout * 1000, deadline, None)
        try:
            revalidate()
            if self.snapshot()[1]:
                return
            if not requested:
                self.domain.shutdownFlags(self.api.VIR_DOMAIN_SHUTDOWN_ACPI_POWER_BTN)
            while not self.snapshot()[1]:
                require(not expired, "shutdown:timeout")
                require(changed.wait(timeout), "shutdown:timeout")
                changed.clear()
                require(not expired, "shutdown:timeout")
            revalidate()
        finally:
            self.api.virEventRemoveTimeout(timer)
            self.connection.domainEventDeregisterAny(callback)

    def close(self):
        self.connection.close()

    def baseline(self):
        for snapshot in self.domain.listAllSnapshots(0):
            if snapshot.getName() == SNAPSHOT:
                return snapshot.getXMLDesc(0)
        return None

    def create_baseline(self, layout, description):
        current, off = self.snapshot()
        require(off and current == layout, "snapshot:source-changed")
        require(self.baseline() is None, "snapshot:already-exists")
        root = ET.Element("domainsnapshot")
        ET.SubElement(root, "name").text = SNAPSHOT
        ET.SubElement(root, "description").text = description
        ET.SubElement(root, "memory", snapshot="no")
        disks = ET.SubElement(root, "disks")
        ET.SubElement(disks, "disk", name=layout["target"], snapshot="internal")
        # Offline snapshot: libvirt records the inactive domain XML and stores
        # disk state inside the current QCOW2, with no conversion or overlay.
        self.domain.snapshotCreateXML(ET.tostring(root, encoding="unicode"),
                                      self.api.VIR_DOMAIN_SNAPSHOT_CREATE_ATOMIC)


def snapshot_proof(xml, layout, description):
    require(isinstance(xml, str) and "<!" not in xml, "snapshot:missing-or-invalid")
    root = ET.fromstring(xml)
    require(root.tag == "domainsnapshot" and root.findtext("name") == SNAPSHOT and
            root.findtext("description") == description and root.findtext("state") == "shutoff",
            "snapshot:identity")
    memory = root.find("memory")
    require(memory is not None and memory.get("snapshot") == "no", "snapshot:memory")
    domain = root.find("domain")
    require(domain is not None and domain_layout(ET.tostring(domain, encoding="unicode"), layout["uuid"]) == layout,
            "snapshot:domain")
    disks = root.findall("disks/disk")
    selected = [disk for disk in disks if disk.get("snapshot") != "no"]
    require(len(selected) == 1 and selected[0].attrib == {"name": layout["target"], "snapshot": "internal"}
            and len(selected[0]) == 0, "snapshot:disk")
    created = root.findtext("creationTime", "")
    require(created.isdigit() and int(created) > 0, "snapshot:creation-time")
    return {"name": SNAPSHOT, "creation_time": int(created), "storage": "internal", "state": "shutoff"}


def inspect_guest(guestfs, disk, script_digest):
    g = guestfs.GuestFS(python_return_dict=True)
    try:
        g.set_trace(False)
        g.set_verbose(False)
        g.set_backend("direct")
        g.set_network(False)
        g.add_drive_opts(str(disk), readonly=True, format="qcow2")
        g.launch()
        roots = g.inspect_os()
        require(len(roots) == 1 and g.inspect_get_distro(roots[0]) == "ubuntu" and
                g.inspect_get_major_version(roots[0]) == 26 and
                g.inspect_get_minor_version(roots[0]) == 4, "guest:release")
        mounts = g.inspect_get_mountpoints(roots[0])
        require("/" in mounts, "guest:mounts")
        for mount in sorted(mounts, key=lambda value: (len(value), value)):
            g.mount_ro(mounts[mount], mount)
        marker_path = str(guest_contract.MARKER)
        info = g.lstatns(marker_path)
        require(stat.S_ISREG(info["st_mode"]) and stat.S_IMODE(info["st_mode"]) == 0o600 and
                info["st_uid"] == info["st_gid"] == 0, "guest:marker-permissions")
        raw = g.read_file(marker_path)
        marker = parse_json(raw)
        require(isinstance(marker, dict) and type(marker.get("schema_version")) is int, "guest:marker-schema")
        guest_contract.validate_marker(marker)
        require(marker["preparation_script_sha256"] == script_digest, "guest:script-digest")
        require(g.read_file("/etc/hostname").decode().strip() == DOMAIN and
                g.read_file("/etc/machine-id").decode().strip() == marker["guest"]["machine_id"],
                "guest:identity")

        def text_file(path):
            return g.read_file(path).decode("utf-8", errors="strict")

        passwd = [line.split(":") for line in text_file("/etc/passwd").splitlines()]
        groups = [line.split(":") for line in text_file("/etc/group").splitlines()]
        require(all(len(row) == 7 for row in passwd) and all(len(row) == 4 for row in groups), "guest:accounts")
        require(not any(row[0] == guest_contract.KIOSK_USER for row in passwd), "guest:residue:kiosk-account")
        for account in guest_contract.IDENTITIES:
            rows = [row for row in passwd if row[0] == account.username]
            require(len(rows) == 1, "guest:account-identity")
            row = rows[0]
            uid = marker["accounts"][account.username]["uid"]
            require(int(row[2]) == uid and sum(int(p[2]) == uid for p in passwd) == 1 and
                    row[4] == account.display_name and row[5] == f"/home/{account.username}" and
                    row[6] == guest_contract.INTERACTIVE_SHELL, "guest:account-identity")
            roles = {r[0] for r in groups if account.username in r[3].split(",") or r[2] == row[3]}
            require(({"adm", "sudo"} <= roles) if account.role == "administrator" else
                    not (roles & guest_contract.FORBIDDEN_CHILD_GROUPS), "guest:account-role")
        for block in text_file("/var/lib/dpkg/status").split("\n\n"):
            fields = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line and not line.startswith(" "))
            require(fields.get("Package") not in ("oh-no-parent-control", "oh-no-parent-control-dbgsym"),
                    "guest:residue:package")
        for category, paths in guest_contract.RESIDUE_PATHS.items():
            require(not any(g.exists(path) or g.is_symlink(path) for path in paths), f"guest:residue:{category}")
        for path in guest_contract.PAM_FILES_TO_SCAN:
            if g.exists(path):
                contents = text_file(path)
                require("oh-no-parent-control" not in contents and "pam_oh_no_parent_control.so" not in contents,
                        "guest:residue:pam-polkit")
        for pattern in ("/usr/lib/*/security/pam_oh_no_parent_control.so",
                        "/etc/systemd/system/*oh-no-parent-control*",
                        "/etc/systemd/system.control/*oh-no-parent-control*",
                        "/usr/local/lib/systemd/system/*oh-no-parent-control*",
                        "/run/systemd/system/*oh-no-parent-control*"):
            require(not g.glob_expand(pattern), "guest:residue:service-session")
        return {"preparation_record_sha256": hashlib.sha256(raw).hexdigest(),
                "preparation_script_sha256": script_digest, "ubuntu_version": guest_contract.UBUNTU_VERSION,
                "accounts": marker["accounts"]}
    finally:
        g.close()


class Capture:
    def __init__(self, source, commands, inspect, *, anchor=ANCHOR, directory=BASELINES,
                 script_digest=None):
        self.source, self.commands, self.inspect = source, commands, inspect
        self.anchor, self.directory = anchor, directory
        self.script_digest = script_digest or guest_contract.preparation_digest()
        self.state = None
        self.directory_identity = None

    def inventory(self):
        layout, off = self.source.snapshot()
        path = canonical(layout["disk"])
        chain = []
        while True:
            require(len(chain) < 32 and path not in [Path(item["path"]) for item in chain], "guard:chain-cycle")
            require(path.parent == self.anchor.parent, "guard:chain-location")
            item = identity(path)
            info = self.commands.info(path, active=not off)
            require(info.get("format") == "qcow2" and type(info.get("virtual-size")) is int and
                    info["virtual-size"] > 0 and not info.get("encrypted"),
                    "guard:image-format")
            specific = info.get("format-specific", {}).get("data", {})
            require(not any(specific.get(key) for key in ("data-file", "encrypt", "corrupt")), "guard:image-features")
            item["virtual_size"] = info["virtual-size"]
            chain.append(item)
            backing = info.get("backing-filename")
            if not backing:
                require(path == self.anchor, "guard:anchor")
                break
            require(info.get("backing-filename-format") == "qcow2", "guard:backing-format")
            candidate = Path(backing)
            require(".." not in candidate.parts, "guard:backing-path")
            path = canonical(candidate if candidate.is_absolute() else path.parent / candidate)
            require(info.get("full-backing-filename", str(path)) == str(path), "guard:backing-path")
        require(len({(item["device"], item["inode"]) for item in chain}) == len(chain), "guard:chain-alias")
        return {"layout": layout, "chain": chain}, off

    def revalidate(self, *, off=False, hashes=False):
        current, is_off = self.inventory()
        require(current == self.state["source"], "guard:source-changed")
        require(not off or is_off, "guard:source-running")
        if self.directory_identity is not None:
            require(self.private_directory() == self.directory_identity, "guard:directory-changed")
        if hashes:
            require([digest(item["path"]) for item in current["chain"]] == self.state["source_digests"],
                    "guard:source-digest-changed")

    def private_directory(self):
        canonical(self.directory)
        info = self.directory.lstat()
        require(stat.S_ISDIR(info.st_mode) and info.st_uid == os.geteuid() and info.st_gid == os.getegid() and
                stat.S_IMODE(info.st_mode) == 0o700, "guard:baseline-directory")
        return {"device": info.st_dev, "inode": info.st_ino}

    def prepare_private_directory(self):
        """Create, or safely repair, the empty controller-state directory.

        A source guest can expose the host's ``/Data`` share and maps its root
        user to an unprivileged host identity.  A mistaken guest-side invocation
        can therefore leave an empty directory at the fixed state path.  It has
        no controller state to preserve, so the host controller repairs only
        that exact empty directory.  Any entry remains evidence and is refused.
        """
        canonical(self.directory.parent)
        if not os.path.lexists(self.directory):
            self.refuse_existing_snapshot()
            self.directory.mkdir(mode=0o700)
            sync_directory(self.directory.parent)

        canonical(self.directory)
        descriptor = os.open(self.directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            info = os.fstat(descriptor)
            require(stat.S_ISDIR(info.st_mode), "guard:baseline-directory")
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (os.geteuid(), os.getegid(), 0o700):
                require(not os.listdir(descriptor), "guard:baseline-directory")
                os.fchown(descriptor, os.geteuid(), os.getegid())
                os.fchmod(descriptor, 0o700)
                os.fsync(descriptor)
                log("state:repaired-empty-baseline-directory")
        finally:
            os.close(descriptor)
        sync_directory(self.directory.parent)
        return self.private_directory()

    def save(self, phase):
        require(phase in PHASES, "state:phase")
        require(self.private_directory() == self.directory_identity, "guard:directory-changed")
        self.state["phase"] = phase
        fd, name = tempfile.mkstemp(prefix=".phase-", dir=self.directory)
        with os.fdopen(fd, "wb") as stream:
            stream.write(encode(self.state))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, self.directory / "phase.json")
        sync_directory(self.directory)
        log(f"stage:{phase}")

    def read_state(self):
        path = self.directory / "phase.json"
        identity(path, private=True, mode=0o600)
        state = parse_json(path.read_bytes())
        require(isinstance(state, dict) and set(state) == {
            "schema_version", "phase", "directory", "source", "source_digests", "guest",
            "operation", "proof", "script_digest"} and state["schema_version"] == 2 and state["phase"] in PHASES,
            "state:schema")
        require(state["directory"] == self.directory_identity and
                isinstance(state["operation"], str) and re.fullmatch(r"[0-9a-f]{32}", state["operation"]) and
                isinstance(state["script_digest"], str) and re.fullmatch(r"[0-9a-f]{64}", state["script_digest"]),
                "state:identity")
        return state

    def description(self):
        return f"Prepared product-free baseline; operation={self.state['operation']}; preparation={self.state['script_digest']}"

    def disk_snapshot(self):
        layout, off = self.source.snapshot()
        records = self.commands.info(Path(layout["disk"]), active=not off).get("snapshots", [])
        require(isinstance(records, list) and all(isinstance(item, dict) for item in records),
                "snapshot:disk-metadata")
        matches = [item for item in records if item.get("name") == SNAPSHOT]
        require(len(matches) <= 1, "snapshot:duplicate-disk-record")
        return matches[0] if matches else None

    def refuse_existing_snapshot(self):
        require(self.source.baseline() is None and self.disk_snapshot() is None, "snapshot:already-exists")

    def run(self):
        # Resolve the existing disk and chain before filesystem writes/shutdown.
        inventory, _off = self.inventory()
        self.directory_identity = self.prepare_private_directory()
        fd = os.open(self.directory / ".lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
        try:
            identity(self.directory / ".lock", private=True, mode=0o600)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise CaptureError("state:busy-controller") from error
            self.commands.lock_fd = fd
            if os.path.lexists(self.directory / "phase.json"):
                self.state = self.read_state()
            else:
                self.refuse_existing_snapshot()
                self.state = {"schema_version": 2, "phase": "validation", "directory": self.directory_identity,
                              "source": inventory, "source_digests": None, "guest": None,
                              "operation": uuid.uuid4().hex, "proof": None, "script_digest": self.script_digest}
                self.save("validation")
            self.revalidate()
            self.execute()
        finally:
            self.commands.lock_fd = None
            os.close(fd)

    def verify_snapshot(self):
        self.revalidate()
        proof = snapshot_proof(self.source.baseline(), self.state["source"]["layout"], self.description())
        record = self.disk_snapshot()
        require(record is not None and isinstance(record.get("id"), str) and
                type(record.get("date-sec")) is int and record.get("vm-state-size") == 0,
                "snapshot:missing-or-invalid-disk-record")
        # These fields identify the saved disk state and remain stable while
        # normal writes/testing change the current contents of the QCOW2.
        proof["disk"] = {key: record.get(key) for key in ("id", "name", "date-sec", "date-nsec", "vm-state-size")}
        digests = self.state["source_digests"]
        require(isinstance(digests, list) and len(digests) == len(self.state["source"]["chain"]),
                "state:source-digests")
        require([digest(item["path"]) for item in self.state["source"]["chain"][1:]] == digests[1:],
                "guard:backing-digest-changed")
        return proof

    def execute(self):
        if self.state["phase"] == "finalized":
            require(self.verify_snapshot() == self.state["proof"], "snapshot:changed")
            log("outcome:baseline-snapshot-preserved")
            return
        if self.state["phase"] in ("validation", "shutdown-requested"):
            self.refuse_existing_snapshot()
            self.save("shutdown-requested")
            self.source.shutdown(self.revalidate, requested=False)
            self.revalidate(off=True)
            self.save("source-off")
        self.revalidate(off=True)
        top = Path(self.state["source"]["layout"]["disk"])
        if self.state["phase"] == "snapshot-requested" and self.source.baseline() is not None:
            # libvirt may have finished after the controller was interrupted.
            # Verify the journal-bound snapshot; never redefine or replace it.
            log("recovery:verify-created-snapshot")
        else:
            self.refuse_existing_snapshot()
            require(self.state["script_digest"] == self.script_digest, "guest:script-digest")
            if self.state["phase"] == "snapshot-requested":
                self.revalidate(off=True, hashes=True)
            log("stage:source-digests")
            self.state["source_digests"] = [digest(item["path"]) for item in self.state["source"]["chain"]]
            log("stage:offline-inspection")
            observed = self.inspect(top, self.script_digest)
            if self.state["guest"] is not None:
                require(observed == self.state["guest"], "guest:changed")
            self.state["guest"] = observed
            log("stage:disk-verification")
            self.commands.check(top)
            self.revalidate(off=True, hashes=True)
            self.save("snapshot-requested")
            self.revalidate(off=True, hashes=True)
            self.source.create_baseline(self.state["source"]["layout"], self.description())
        self.revalidate(off=True)
        self.commands.check(top)
        self.state["proof"] = self.verify_snapshot()
        self.save("finalized")
        log("outcome:baseline-snapshot-created")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check-tools", action="store_true", help="check dependencies only; no VM connection or writes")
    args = parser.parse_args(argv)
    source = None
    capture = None
    try:
        require(Path.cwd() == guest_contract.CHECKOUT and Path(__file__).resolve() ==
                guest_contract.CHECKOUT / "tests/integration/prepare_host.py", "guard:checkout")
        require(shutil.which("qemu-img") is not None and shutil.which("virsh") is not None, "tools:missing; run ./setup.sh")
        modules = {}
        for name in ("libvirt", "guestfs"):
            try:
                modules[name] = importlib.import_module(name)
            except ImportError as error:
                raise CaptureError("tools:missing; run ./setup.sh") from error
        if args.check_tools:
            log("tools:available")
            return 0
        require(os.geteuid() == os.getegid() == 0, "guard:root; enter a root shell on the development host")
        # libvirt requires continuous event dispatch to answer server keepalives,
        # including during hashing, libguestfs inspection and QEMU checks.
        # The process-lifetime daemon also drains callbacks after close().
        api = modules["libvirt"]
        api.virEventRegisterDefaultImpl()
        def dispatch_events():
            while True:
                try:
                    api.virEventRunDefaultImpl()
                except Exception:
                    log("connection:event-loop-failed")
                    return
        threading.Thread(target=dispatch_events, name="libvirt-events", daemon=True).start()
        source = LibvirtSource(modules["libvirt"])
        capture = Capture(source, Commands(), lambda disk, sha: inspect_guest(modules["guestfs"], disk, sha))
        capture.run()
        return 0
    except (Exception, KeyboardInterrupt) as error:
        category = str(error) if isinstance(error, CaptureError) else "operation:failed-or-interrupted"
        phase = capture.state["phase"] if capture and capture.state else "before-validation"
        log(f"{category}; recovery-phase:{phase}")
        print("prep-host: resolve the reported condition, then rerun make prep-host; retain snapshot and controller state",
              file=sys.stderr)
        return 1
    finally:
        if source:
            source.close()


if __name__ == "__main__":
    def interrupted(_signum, _frame):
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    sys.exit(main())
