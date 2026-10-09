"""Checkout identities and bounded background discovery for the desktop watcher."""

import hashlib
import os
from pathlib import Path
import queue
import subprocess
import threading

ROOT = Path(__file__).resolve().parents[1]


def identity(root):
    return hashlib.sha256(os.fsencode(root)).hexdigest()[:16]


def checkout(path):
    root = Path(path)
    if (not root.is_absolute() or root.resolve() != root or
            any(part.is_symlink() for part in (root, *root.parents)) or
            root.stat().st_uid != os.getuid() or
            not (root / 'tools/watch').is_file() or not (root / '.git').exists()):
        raise ValueError('watch: invalid checkout')
    return root


def worktrees(root):
    """Read Git metadata only; never import or execute another checkout's code."""
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
        records[path] = branch or 'detached ' + fields.get('HEAD', '')[:8]
    return records


class Discovery:
    """Git waits stay outside GTK. Registered roots survive idle periods."""

    def __init__(self, root=ROOT):
        self.roots = queue.Queue()
        self.updates = queue.Queue(maxsize=1)
        self.vm_updates = queue.Queue(maxsize=1)
        self.stop = threading.Event()
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
            for root in sorted(seeds):
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
            from vm_selection import registry
            configured = {}
            for root in known:
                try:
                    configured[root] = registry(root / 'config/test-vm.json')
                except (OSError, ValueError):
                    # An invalid registry must not keep stale VM tabs alive.
                    configured[root] = {}
            try:
                self.vm_updates.get_nowait()
            except queue.Empty:
                pass
            self.vm_updates.put_nowait(configured)
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
