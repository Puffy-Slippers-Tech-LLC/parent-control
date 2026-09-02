#!/usr/bin/python3
"""Host controller for the guarded H-50 disposable Ubuntu VM.

This program never installs the product on the host.  ``setup`` creates one
explicitly named libvirt guest; all product and account changes are performed
over SSH only after the guest's marker has been verified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import time
import xml.etree.ElementTree as ElementTree
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
CONNECT_URI = "qemu:///system"
STATE_ROOT = Path("/var/lib/oh-no-parent-control-integration")
IMAGE_ROOT = Path("/var/lib/libvirt/images")
CACHE_ROOT = Path("/var/cache/oh-no-parent-control-integration")
ARTIFACT_ROOT = REPOSITORY / "tests/integration/artifacts"
RELEASE_URL = (
    "https://cloud-images.ubuntu.com/releases/resolute/release-20260823"
)
IMAGE_NAME = "ubuntu-26.04-server-cloudimg-amd64.img"
VM_NAME_RE = re.compile(r"onpc-h50-[a-z0-9](?:[a-z0-9-]{0,45}[a-z0-9])?")
DESCRIPTION_PREFIX = "oh-no-parent-control-h50-disposable token="
REMOTE_USER = "onpc-admin"
REMOTE_CHECKOUT = Path("/var/lib/oh-no-parent-control-integration/checkout")
MARKER_PATH = Path("/etc/oh-no-parent-control-integration-vm")


class HarnessError(RuntimeError):
    pass


def fail(message: str) -> None:
    raise HarnessError(message)


def validate_vm_name(name: str) -> str:
    if not isinstance(name, str) or VM_NAME_RE.fullmatch(name) is None:
        fail(
            "VM name must match onpc-h50-[a-z0-9-], end in an alphanumeric "
            "character, and be at most 56 characters"
        )
    return name


def state_directory(name: str) -> Path:
    return STATE_ROOT / validate_vm_name(name)


def _require_root() -> None:
    if os.geteuid() != 0:
        fail("run the VM controller through sudo; it does not install the app on the host")


def _require_commands(*commands: str) -> None:
    missing = [command for command in commands if shutil.which(command) is None]
    if missing:
        fail("missing host VM tools (not installed automatically): " + ", ".join(missing))


def _run(command: list[str], *, check: bool = True, **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=check, **kwargs)


def _virsh(*arguments: str, **kwargs) -> subprocess.CompletedProcess:
    return _run(["virsh", "--connect", CONNECT_URI, *arguments], **kwargs)


def _write_private(path: Path, contents: str) -> None:
    path.write_text(contents, encoding="utf-8")
    path.chmod(0o600)


def _load_metadata(name: str) -> dict:
    directory = state_directory(name)
    path = directory / "metadata.json"
    try:
        directory_status = directory.stat(follow_symlinks=False)
        path_status = path.stat(follow_symlinks=False)
    except OSError as error:
        fail(f"no valid H-50 state exists for {name}: {error}")
    if (not stat.S_ISDIR(directory_status.st_mode) or directory_status.st_uid != 0 or
            stat.S_IMODE(directory_status.st_mode) != 0o700):
        fail("per-VM state must be a root-owned mode-0700 directory")
    if (not stat.S_ISREG(path_status.st_mode) or path_status.st_uid != 0 or
            stat.S_IMODE(path_status.st_mode) != 0o600):
        fail("VM metadata must be a root-owned mode-0600 regular file")
    try:
        metadata = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(f"no valid H-50 state exists for {name}: {error}")
    if not isinstance(metadata, dict) or metadata.get("name") != name:
        fail("VM state does not match the explicitly selected name")
    token = metadata.get("token")
    if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
        fail("VM state has an invalid identity token")
    if metadata.get("description") != DESCRIPTION_PREFIX + token:
        fail("VM state has an invalid libvirt description")
    if metadata.get("ssh_private_key") != str(directory / "ssh_key"):
        fail("VM state has an unexpected SSH identity path")
    if metadata.get("known_hosts") != str(directory / "known_hosts"):
        fail("VM state has an unexpected SSH host-key path")
    return metadata


def _save_metadata(directory: Path, metadata: dict) -> None:
    _write_private(directory / "metadata.json", json.dumps(metadata, indent=2) + "\n")


def _domain_exists(name: str) -> bool:
    result = _virsh("dominfo", name, check=False, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)
    return result.returncode == 0


def _download_verified_image() -> Path:
    CACHE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o755)
    image = CACHE_ROOT / IMAGE_NAME
    sums = CACHE_ROOT / "SHA256SUMS.release-20260823"
    if not sums.exists():
        temporary = sums.with_suffix(".tmp")
        _run([
            "curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2",
            "--output", str(temporary), f"{RELEASE_URL}/SHA256SUMS",
        ])
        os.replace(temporary, sums)
    expected = None
    for line in sums.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) == 2 and fields[1].lstrip("*") == IMAGE_NAME:
            expected = fields[0]
            break
    if expected is None or re.fullmatch(r"[0-9a-f]{64}", expected) is None:
        fail("official SHA256SUMS does not contain the selected Ubuntu image")
    if not image.exists():
        temporary = image.with_suffix(".download")
        _run([
            "curl", "--fail", "--location", "--proto", "=https", "--tlsv1.2",
            "--output", str(temporary), f"{RELEASE_URL}/{IMAGE_NAME}",
        ])
        os.replace(temporary, image)
    digest = hashlib.sha256()
    with image.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    if not secrets.compare_digest(digest.hexdigest(), expected):
        fail("downloaded Ubuntu image does not match the official SHA-256 manifest")
    return image


def _cloud_init(name: str, token: str, public_key: str) -> tuple[str, str, str]:
    marker = json.dumps({
        "purpose": "oh-no-parent-control-integration",
        "name": name,
        "token": token,
        "ubuntu_version": "26.04",
    }, separators=(",", ":"))
    user_data = f"""#cloud-config
hostname: {name}
manage_etc_hosts: true
users:
  - name: {REMOTE_USER}
    uid: 2000
    gecos: Oh No Parent Control Test Administrator
    groups: [adm, sudo]
    sudo: ALL=(ALL) NOPASSWD:ALL
    shell: /bin/bash
    lock_passwd: true
    ssh_authorized_keys:
      - {public_key}
ssh_pwauth: false
package_update: true
packages:
  - qemu-guest-agent
write_files:
  - path: {MARKER_PATH}
    owner: root:root
    permissions: '0600'
    content: '{marker}'
runcmd:
  - [systemctl, enable, --now, qemu-guest-agent.service]
final_message: H-50 disposable VM ready
"""
    meta_data = f"instance-id: {name}-{token}\nlocal-hostname: {name}\n"
    # Ubuntu 26.04 requires cloud-init's boot network to be non-optional when
    # first-boot provisioning depends on the network.
    network_data = """version: 2
ethernets:
  integration:
    match:
      name: "en*"
    dhcp4: true
    optional: false
"""
    return user_data, meta_data, network_data


def _ip_address(name: str, timeout: int = 600) -> str:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        for source in ("agent", "lease"):
            result = _virsh(
                "domifaddr", name, "--source", source, check=False,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            )
            for line in result.stdout.splitlines():
                match = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})/\d+\b", line)
                if match and not match.group(1).startswith("127."):
                    return match.group(1)
        time.sleep(5)
    fail(f"timed out waiting for {name} to receive an IPv4 address")


def _ssh_arguments(metadata: dict) -> list[str]:
    key = Path(metadata["ssh_private_key"])
    known_hosts = Path(metadata["known_hosts"])
    return [
        "ssh", "-i", str(key), "-o", "BatchMode=yes",
        "-o", "StrictHostKeyChecking=accept-new",
        "-o", f"UserKnownHostsFile={known_hosts}",
        "-o", "ConnectTimeout=10",
        f"{REMOTE_USER}@{metadata['ip_address']}",
    ]


def _ssh(metadata: dict, command: list[str], *, check: bool = True, **kwargs):
    return _run(
        [*_ssh_arguments(metadata), shlex.join(command)], check=check, **kwargs,
    )


def _wait_for_ssh(metadata: dict, timeout: int = 900) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = _ssh(metadata, ["true"], check=False, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return
        time.sleep(5)
    fail(f"timed out waiting for SSH on {metadata['name']}")


def _verify_remote_marker(metadata: dict) -> None:
    result = _ssh(
        metadata, ["sudo", "cat", str(MARKER_PATH)],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    try:
        marker = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        fail(f"guest marker is not valid JSON: {error}")
    expected = {
        "purpose": "oh-no-parent-control-integration",
        "name": metadata["name"],
        "token": metadata["token"],
        "ubuntu_version": "26.04",
    }
    if marker != expected:
        fail("guest marker does not match the selected disposable VM")
    checks = _ssh(
        metadata,
        ["sudo", "python3", "-c",
         "import os,stat; p='/etc/oh-no-parent-control-integration-vm'; "
         "s=os.stat(p, follow_symlinks=False); "
         "assert stat.S_ISREG(s.st_mode) and s.st_uid == 0 and "
         "stat.S_IMODE(s.st_mode) == 0o600"],
        check=False,
    )
    if checks.returncode != 0:
        fail("guest marker is not a root-owned mode-0600 regular file")
    virtual = _ssh(metadata, ["systemd-detect-virt", "--vm"], check=False,
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if virtual.returncode != 0:
        fail("selected machine does not identify itself as a virtual machine")


def _archive_checkout() -> Path:
    descriptor, temporary_name = tempfile.mkstemp(prefix="onpc-h50-source-", suffix=".tar.gz")
    os.close(descriptor)
    temporary = Path(temporary_name)

    def excluded(path: Path) -> bool:
        relative = path.relative_to(REPOSITORY)
        if not relative.parts:
            return False
        if relative.parts[0] == ".git":
            return True
        if relative.parts[:3] == ("tests", "integration", "artifacts"):
            return True
        return "__pycache__" in relative.parts or path.suffix == ".pyc"

    with tarfile.open(temporary, "w:gz") as archive:
        for path in sorted(REPOSITORY.rglob("*")):
            if not excluded(path):
                if path.is_symlink() or not (path.is_dir() or path.is_file()):
                    fail(f"checkout contains an unsupported entry: {path}")
                archive.add(path, arcname=Path("source") / path.relative_to(REPOSITORY),
                            recursive=False)
    return temporary


def _scp_to(metadata: dict, local: Path, remote: str) -> None:
    arguments = _ssh_arguments(metadata)
    # scp uses the same identity options as ssh but supplies its own source and
    # destination operands.
    destination = arguments.pop()
    scp_arguments = ["scp", *arguments[1:], str(local), f"{destination}:{remote}"]
    _run(scp_arguments)


def _sync_checkout(metadata: dict) -> None:
    _verify_remote_marker(metadata)
    archive = _archive_checkout()
    remote_archive = f"/tmp/onpc-h50-source-{metadata['token']}.tar.gz"
    try:
        _scp_to(metadata, archive, remote_archive)
        _ssh(metadata, ["sudo", "rm", "-rf", str(REMOTE_CHECKOUT)])
        _ssh(metadata, ["sudo", "install", "-d", "-o", REMOTE_USER, "-g", REMOTE_USER,
                        "-m", "0750", str(REMOTE_CHECKOUT)])
        _ssh(metadata, ["sudo", "tar", "--no-same-owner", "--no-same-permissions",
                        "-xzf", remote_archive, "-C", str(REMOTE_CHECKOUT),
                        "--strip-components=1"])
        _ssh(metadata, ["sudo", "chown", "-R", f"{REMOTE_USER}:{REMOTE_USER}",
                        str(REMOTE_CHECKOUT)])
        _ssh(metadata, ["rm", "-f", remote_archive])
    finally:
        archive.unlink(missing_ok=True)


def _reboot_and_wait(metadata: dict) -> None:
    _ssh(metadata, ["sudo", "systemctl", "reboot"], check=False,
         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(5)
    metadata["ip_address"] = _ip_address(metadata["name"])
    _wait_for_ssh(metadata, timeout=1200)
    _verify_remote_marker(metadata)
    _save_metadata(state_directory(metadata["name"]), metadata)


def setup(args) -> None:
    _require_root()
    _require_commands(
        "virsh", "virt-install", "qemu-img", "cloud-localds", "ssh-keygen",
        "ssh", "scp", "curl",
    )
    name = validate_vm_name(args.name)
    directory = state_directory(name)
    disk = IMAGE_ROOT / f"{name}.qcow2"
    seed = IMAGE_ROOT / f"{name}-seed.iso"
    if directory.exists() or disk.exists() or seed.exists() or _domain_exists(name):
        fail(f"refusing to overwrite existing VM state for {name}")

    STATE_ROOT.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_root_status = STATE_ROOT.stat(follow_symlinks=False)
    if not stat.S_ISDIR(state_root_status.st_mode) or state_root_status.st_uid != 0:
        fail("H-50 state root must be a root-owned directory")
    STATE_ROOT.chmod(0o700)
    directory.mkdir(mode=0o700)
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(16)
    private_key = directory / "ssh_key"
    known_hosts = directory / "known_hosts"
    metadata = {
        "name": name,
        "token": token,
        "description": DESCRIPTION_PREFIX + token,
        "disk": str(disk),
        "seed": str(seed),
        "ssh_private_key": str(private_key),
        "known_hosts": str(known_hosts),
        "release_url": RELEASE_URL,
        "image_name": IMAGE_NAME,
        "created": False,
    }
    _save_metadata(directory, metadata)
    _run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(private_key)])
    known_hosts.touch(mode=0o600)
    credentials = {
        "onpc-admin": secrets.token_urlsafe(24),
        "onpc-child": secrets.token_urlsafe(24),
        "onpc-unrelated": secrets.token_urlsafe(24),
    }
    _write_private(directory / "credentials.json", json.dumps(credentials, indent=2) + "\n")

    image = _download_verified_image()
    _run(["qemu-img", "create", "-q", "-f", "qcow2", "-F", "qcow2",
          "-b", str(image), str(disk), f"{args.disk_gib}G"])
    public_key = private_key.with_suffix(".pub").read_text(encoding="utf-8").strip()
    user_data, meta_data, network_data = _cloud_init(name, token, public_key)
    _write_private(directory / "user-data", user_data)
    _write_private(directory / "meta-data", meta_data)
    _write_private(directory / "network-config", network_data)
    _run(["cloud-localds", "--network-config", str(directory / "network-config"),
          str(seed), str(directory / "user-data"), str(directory / "meta-data")])
    _run([
        "virt-install", "--connect", CONNECT_URI, "--name", name,
        "--description", metadata["description"], "--memory", str(args.memory_mib),
        "--vcpus", str(args.vcpus), "--import", "--noautoconsole",
        "--osinfo", "detect=on,require=off",
        "--disk", f"path={disk},format=qcow2,bus=virtio",
        "--disk", f"path={seed},device=cdrom,readonly=on",
        "--network", "network=default,model=virtio",
        "--graphics", "spice,listen=none", "--video", "virtio",
    ])
    metadata["created"] = True
    metadata["ip_address"] = _ip_address(name)
    _save_metadata(directory, metadata)
    _wait_for_ssh(metadata)
    _ssh(metadata, ["sudo", "cloud-init", "status", "--wait"])
    _verify_remote_marker(metadata)
    _sync_checkout(metadata)
    remote_credentials = f"/tmp/onpc-h50-credentials-{token}.json"
    _scp_to(metadata, directory / "credentials.json", remote_credentials)
    _ssh(metadata, ["sudo", str(REMOTE_CHECKOUT / "tests/integration/guest/setup"),
                    name, remote_credentials])
    _reboot_and_wait(metadata)
    print(f"Disposable VM {name} is ready. No product files were installed on the host.")


def run_tests(args) -> None:
    _require_root()
    _require_commands("virsh", "ssh", "scp")
    metadata = _load_metadata(validate_vm_name(args.name))
    metadata["ip_address"] = _ip_address(metadata["name"])
    _wait_for_ssh(metadata)
    _verify_remote_marker(metadata)
    _sync_checkout(metadata)
    _ssh(metadata, ["sudo", str(REMOTE_CHECKOUT / "tests/integration/guest/run"),
                    metadata["name"]])
    _reboot_and_wait(metadata)
    _ssh(metadata, ["sudo", str(REMOTE_CHECKOUT / "tests/integration/guest/verify"),
                    metadata["name"]])
    print(f"Clean-install checks passed inside disposable VM {metadata['name']}.")


def _safe_extract(archive_path: Path, destination: Path) -> None:
    destination_resolved = destination.resolve()
    with tarfile.open(archive_path, "r:gz") as archive:
        for member in archive.getmembers():
            target = (destination / member.name).resolve()
            if destination_resolved not in target.parents and target != destination_resolved:
                fail("artifact archive contains a path outside its destination")
            if member.issym() or member.islnk() or member.isdev():
                fail("artifact archive contains an unsupported special entry")
        archive.extractall(destination, filter="data")


def collect(args) -> None:
    _require_root()
    _require_commands("virsh", "ssh", "scp")
    metadata = _load_metadata(validate_vm_name(args.name))
    metadata["ip_address"] = _ip_address(metadata["name"])
    _wait_for_ssh(metadata)
    _verify_remote_marker(metadata)
    _sync_checkout(metadata)
    result = _ssh(
        metadata,
        ["sudo", str(REMOTE_CHECKOUT / "tests/integration/guest/collect"),
         metadata["name"]],
        stdout=subprocess.PIPE, text=True,
    )
    remote_directory = result.stdout.strip().splitlines()[-1]
    if re.fullmatch(r"/var/tmp/oh-no-parent-control-artifacts/[0-9TZ-]+", remote_directory) is None:
        fail("guest collector returned an unexpected artifact path")
    run_id = Path(remote_directory).name
    destination = (Path(args.output) if args.output else ARTIFACT_ROOT) / metadata["name"] / run_id
    if destination.exists():
        fail(f"artifact destination already exists: {destination}")
    destination.mkdir(parents=True)
    archive_path = destination.parent / f".{run_id}.tar.gz"
    with archive_path.open("wb") as stream:
        _ssh(metadata, ["sudo", "tar", "-C", remote_directory, "-czf", "-", "."],
             stdout=stream)
    try:
        _safe_extract(archive_path, destination)
    finally:
        archive_path.unlink(missing_ok=True)
    sudo_uid = int(os.environ.get("SUDO_UID", "0"))
    sudo_gid = int(os.environ.get("SUDO_GID", "0"))
    if sudo_uid:
        for path in [destination, *destination.rglob("*")]:
            os.chown(path, sudo_uid, sudo_gid, follow_symlinks=False)
    print(destination)


def _validated_storage_paths(metadata: dict) -> set[Path]:
    name = metadata["name"]
    expected = {
        IMAGE_ROOT / f"{name}.qcow2",
        IMAGE_ROOT / f"{name}-seed.iso",
    }
    saved = {Path(metadata["disk"]), Path(metadata["seed"])}
    if saved != expected:
        fail("saved VM storage is outside the exact H-50 paths")
    return expected


def _validate_domain_for_destroy(metadata: dict, xml_text: str) -> set[Path]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError as error:
        fail(f"libvirt returned invalid domain XML: {error}")
    if root.findtext("name") != metadata["name"]:
        fail("libvirt domain name does not match saved H-50 state")
    if root.findtext("description") != metadata["description"]:
        fail("libvirt domain lacks the matching H-50 disposable identity token")
    sources = {
        Path(source.attrib["file"])
        for source in root.findall("./devices/disk/source")
        if "file" in source.attrib
    }
    expected = _validated_storage_paths(metadata)
    if sources != expected:
        fail("libvirt storage does not match the two saved disposable VM images")
    return sources


def destroy(args) -> None:
    _require_root()
    _require_commands("virsh")
    name = validate_vm_name(args.name)
    if args.confirm != name:
        fail("--confirm must exactly repeat the disposable VM name")
    metadata = _load_metadata(name)
    sources = _validated_storage_paths(metadata)
    directory = state_directory(name)
    if directory.parent != STATE_ROOT or directory.name != name:
        fail("refusing to remove an unexpected H-50 state directory")
    if _domain_exists(name):
        result = _virsh("dumpxml", name, stdout=subprocess.PIPE, text=True)
        sources = _validate_domain_for_destroy(metadata, result.stdout)
        state = _virsh("domstate", name, stdout=subprocess.PIPE, text=True).stdout.strip()
        if state != "shut off":
            _virsh("destroy", name)
        _virsh("undefine", name)
    for path in sources:
        path.unlink(missing_ok=True)
    shutil.rmtree(directory)
    print(f"Destroyed disposable VM {name} and its per-VM state. Shared image cache retained.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    setup_parser = subparsers.add_parser("setup", help="create and provision a clean VM")
    setup_parser.add_argument("--name", required=True)
    setup_parser.add_argument("--memory-mib", type=int, default=8192)
    setup_parser.add_argument("--vcpus", type=int, default=4)
    setup_parser.add_argument("--disk-gib", type=int, default=80)
    setup_parser.set_defaults(function=setup)
    run_parser = subparsers.add_parser("run", help="run checks and the real installer in the VM")
    run_parser.add_argument("--name", required=True)
    run_parser.set_defaults(function=run_tests)
    collect_parser = subparsers.add_parser("collect", help="retrieve redacted VM artifacts")
    collect_parser.add_argument("--name", required=True)
    collect_parser.add_argument("--output")
    collect_parser.set_defaults(function=collect)
    destroy_parser = subparsers.add_parser("destroy", help="destroy only a verified H-50 VM")
    destroy_parser.add_argument("--name", required=True)
    destroy_parser.add_argument("--confirm", required=True)
    destroy_parser.set_defaults(function=destroy)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
        if args.command == "setup":
            for value, label, minimum in (
                (args.memory_mib, "memory", 4096),
                (args.vcpus, "vCPU count", 2),
                (args.disk_gib, "disk size", 40),
            ):
                if value < minimum:
                    fail(f"{label} is below the supported integration minimum {minimum}")
        args.function(args)
    except (HarnessError, OSError, subprocess.SubprocessError) as error:
        print(f"h50-harness: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
