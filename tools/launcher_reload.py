"""Explicit reload requests and interpreter replacement for retained runs."""

import fcntl
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import uuid

BASELINE = 'ONPC_LAUNCHER_RELOAD_BASELINE'
STATUS = 75
current = None


class ReloadRequested(Exception):
    """A child-free boundary can resume this run under fresh imports."""


def generation(run):
    try:
        return json.loads((run / 'reload.json').read_text())
    except FileNotFoundError:
        return None


def request(run):
    import detached_launcher as launcher
    with launcher.lock(run / 'reload-gate') as gate:
        fcntl.flock(gate, fcntl.LOCK_EX)
        launcher.atomic(run / 'reload.json', uuid.uuid4().hex)


class ReloadRequest:
    def __init__(self, run):
        self.run = run
        self.generation = generation(run)
        inherited = json.loads(os.environ.get(BASELINE, 'null'))
        if inherited is not None and inherited['run'] == str(run):
            self.generation = inherited['generation']

    def pending(self):
        return generation(self.run) != self.generation

    def check(self):
        if self.pending():
            raise ReloadRequested()

    def inherit(self, environment):
        environment[BASELINE] = json.dumps(dict(run=str(self.run), generation=self.generation))


def watch(run=None):
    global current
    if run is None:
        inherited = json.loads(os.environ.get(BASELINE, 'null'))
        if inherited is None:
            current = None
            return None
        run = Path(inherited['run'])
    current = ReloadRequest(run)
    return current


@contextmanager
def watching(run=None):
    global current
    previous = current
    try:
        yield watch(run)
    finally:
        current = previous


def pending():
    return current is not None and current.pending()


def check():
    if current is not None:
        current.check()


def replace(command, descriptors):
    """Exec without releasing the owner's lock or its inherited leases."""
    import vm_pool
    keeper = vm_pool.reload_keeper()
    if keeper is not None:
        descriptors = (*descriptors, keeper['input'], keeper['output'])
    inherited = {fd: os.get_inheritable(fd) for fd in set(descriptors)}
    baseline = os.environ.get(BASELINE)
    previous_keeper = os.environ.get(vm_pool.RELOAD_KEEPER)
    try:
        if baseline is not None:
            # Acknowledge only requests present before fresh imports start.
            # A second request arriving during startup stays pending.
            value = json.loads(baseline)
            value['generation'] = generation(Path(value['run']))
            os.environ[BASELINE] = json.dumps(value)
        if keeper is not None:
            os.environ[vm_pool.RELOAD_KEEPER] = json.dumps(keeper)
        for fd in inherited:
            os.set_inheritable(fd, True)
        sys.stdout.flush()
        sys.stderr.flush()
        os.execv(command[0], command)
    finally:
        # Only exec failure returns here; normal failure handling still owns FDs.
        for fd, value in inherited.items():
            os.set_inheritable(fd, value)
        if baseline is not None:
            os.environ[BASELINE] = baseline
        if previous_keeper is None:
            os.environ.pop(vm_pool.RELOAD_KEEPER, None)
        else:
            os.environ[vm_pool.RELOAD_KEEPER] = previous_keeper
