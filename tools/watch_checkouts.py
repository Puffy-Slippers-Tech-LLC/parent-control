"""Checkout identities and bounded background discovery for watch readers."""

import hashlib
import os
from pathlib import Path
import queue
import subprocess
import threading
import json
import re
import stat
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]


def identity(root):
    return hashlib.sha256(os.fsencode(root)).hexdigest()[:16]


def registered_vms(root):
    """Observe transferred controllers without changing the host checkout's registry.

    These extra names/IDs are display metadata only. VM tools continue to use
    their authenticated source registry and the privileged backend guards.
    """
    from vm_selection import registry, vm_config
    from e2e_watch_protocol import BASE
    from test_storage import watch_root
    configured = registry(Path(root) / 'config/environment.json')
    parent = BASE / str(os.getuid())
    try:
        for path in (BASE, parent):
            info = path.lstat()
            if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0
                    or info.st_mode & 0o022 or path.resolve() != path):
                return configured
        for path in parent.iterdir():
            if re.fullmatch(r'(?:current|progress)-[0-9a-f]+\.json', path.name) is None:
                continue
            try:
                fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                with os.fdopen(fd, 'rb') as stream:
                    info = os.fstat(stream.fileno())
                    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                            or info.st_mode & 0o022 or info.st_size > 8192):
                        continue
                    data = stream.read(8193)
                    if len(data) > 8192:
                        continue
                    value = json.loads(data)
                if (not isinstance(value, dict) or value.get('checkout') != str(watch_root(root))
                        or 'vm_id' not in value):
                    continue
                name = vm_config.validate_name(value['vm'])
                identifier = value['vm_id']
                if (path.stem.split('-', 1)[1] != name.encode('ascii').hex()
                        or identifier is not None and (not isinstance(identifier, str)
                            or re.fullmatch(r'[1-9][0-9]*', identifier) is None)):
                    continue
                configured.setdefault(name, SimpleNamespace(name=name, id=identifier))
            except (OSError, ValueError, KeyError, TypeError):
                continue
    except OSError:
        pass
    return configured


def checkout(path):
    root = Path(path)
    if (not root.is_absolute() or root.resolve() != root or
            any(part.is_symlink() for part in (root, *root.parents)) or
            root.stat().st_uid != os.getuid() or
            not (root / 'tools/watch_webview.py').is_file() or not (root / '.git').exists()):
        raise ValueError('watch: invalid checkout')
    return root


def worktrees(root):
    """Discover branches and the requested root using Git metadata only."""
    result = subprocess.run(['git', '-C', str(root), 'worktree', 'list', '--porcelain', '-z'],
                            capture_output=True, timeout=2, check=True)
    records = {}
    for record in os.fsdecode(result.stdout).split('\0\0'):
        fields = dict(field.partition(' ')[::2] for field in record.split('\0') if field)
        if 'worktree' not in fields or 'bare' in fields:
            continue
        try:
            path = checkout(fields['worktree'])
        except (OSError, ValueError):
            continue
        branch = fields.get('branch', '').removeprefix('refs/heads/')
        # Detached diagnostic/build snapshots are not independent branch tabs.
        # Still observe one when the user explicitly launches watch from it.
        if not branch and path != root:
            continue
        records[path] = branch or 'detached ' + fields.get('HEAD', '')[:8]
    return records


def branch_names(root):
    """Read local and remote branch names from Git, independent of config."""
    result = subprocess.run(['git', '-C', str(root), 'for-each-ref',
                             '--format=%(refname)', 'refs/heads/', 'refs/remotes/'],
                            capture_output=True, timeout=2, check=True)
    names = set()
    for ref in os.fsdecode(result.stdout).splitlines():
        if ref.startswith('refs/heads/'):
            names.add(ref.removeprefix('refs/heads/'))
        elif ref.startswith('refs/remotes/'):
            # Remote names are prefixes, not part of the branch name.
            name = ref.removeprefix('refs/remotes/').partition('/')[2]
            if name and name != 'HEAD':
                names.add(name)
    return names


class Discovery:
    """Git waits stay outside GTK. Registered roots survive idle periods."""

    def __init__(self, root=ROOT, *, include_worktrees=True):
        self.roots = queue.Queue()
        self.updates = queue.Queue(maxsize=1)
        self.vm_updates = queue.Queue(maxsize=1)
        self.branch_updates = queue.Queue(maxsize=1)
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.include_worktrees = include_worktrees
        self.add(root)
        self.thread = threading.Thread(target=self.run, name='watch-checkouts', daemon=True)
        self.thread.start()

    def add(self, root):
        self.roots.put(checkout(root))

    def run(self):
        seeds, known = set(), {}
        while not self.stop.is_set():
            while True:
                try:
                    root = self.roots.get_nowait()
                except queue.Empty:
                    break
                seeds.add(root)
                known.setdefault(root, root.name)
            for root in sorted(seeds) if self.include_worktrees else ():
                if self.stop.is_set():
                    break
                try:
                    known.update(worktrees(root))
                except (OSError, ValueError, subprocess.SubprocessError):
                    continue
            try:
                self.updates.get_nowait()
            except queue.Empty:
                pass
            self.updates.put_nowait(dict(known))
            branches = set()
            for root in sorted(seeds):
                try:
                    branches.update(branch_names(root))
                except (OSError, subprocess.SubprocessError):
                    continue
            try:
                self.branch_updates.get_nowait()
            except queue.Empty:
                pass
            self.branch_updates.put_nowait(tuple(sorted(branches)))
            configured = {}
            for root in known:
                try:
                    configured[root] = registered_vms(root)
                except (OSError, ValueError):
                    # An invalid registry must not keep stale VM tabs alive.
                    configured[root] = {}
            try:
                self.vm_updates.get_nowait()
            except queue.Empty:
                pass
            self.vm_updates.put_nowait(configured)
            self.ready.set()
            self.stop.wait(1)

    def poll(self):
        try:
            return self.updates.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.stop.set()

    def poll_vms(self):
        try:
            return self.vm_updates.get_nowait()
        except queue.Empty:
            return None

    def poll_branches(self):
        try:
            return self.branch_updates.get_nowait()
        except queue.Empty:
            return None
