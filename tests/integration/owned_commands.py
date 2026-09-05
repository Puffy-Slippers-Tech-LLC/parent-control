#!/usr/bin/python3
"""Bounded commands; cleanup signals only a pidfd opened for the spawned child."""

import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile


class CommandError(RuntimeError):
    """Command failure with a redacted category only."""


def require(condition, category):
    if not condition:
        raise CommandError(category)


class Commands:
    """Keep a pidfd for each directly spawned command, including on interruption."""

    def __init__(self):
        self.lock_fd = None
        self.directory = None
        self.sequence = 0
        self.last_returncode = None

    def run(self, args, *, timeout=120, check=True, input=None, merge_stderr=True):
        self.sequence += 1
        # Command diagnostics stay private; only fixed categories reach the console.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            child = subprocess.Popen(args, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                     stdout=output, stderr=subprocess.STDOUT if merge_stderr else errors,
                                     pass_fds=(() if self.lock_fd is None else (self.lock_fd,)))
            pidfd = os.pidfd_open(child.pid)
            try:
                try:
                    child.communicate(input=input, timeout=timeout)
                except BaseException:
                    # SIGINT gives the directly spawned command a chance to close normally.
                    # Never enumerate or signal inferred descendants.
                    for sig, deadline in ((signal.SIGINT, 30), (signal.SIGTERM, 10), (signal.SIGKILL, 10)):
                        try:
                            signal.pidfd_send_signal(pidfd, sig)
                        except ProcessLookupError:
                            break
                        try:
                            child.wait(timeout=deadline)
                            break
                        except subprocess.TimeoutExpired:
                            continue
                    raise
            finally:
                os.close(pidfd)
                output.seek(0)
                raw = output.read()
                errors.seek(0)
                error_bytes = errors.read()
                if self.directory:
                    path = self.directory / f'command-{self.sequence:04d}.txt'
                    with path.open('xb') as stream:
                        stream.write(raw)
                    path.chmod(0o600)
                    if error_bytes:
                        path = self.directory / f'command-{self.sequence:04d}-stderr.txt'
                        with path.open('xb') as stream:
                            stream.write(error_bytes)
                        path.chmod(0o600)
            self.last_returncode = child.returncode
            require(not check or child.returncode == 0, 'command:failed:' + Path(args[0]).name)
            return raw

    def info(self, path, active=False):
        return json.loads(self.run(['qemu-img', 'info', '--output=json', '-f', 'qcow2',
                                              *(['-U'] if active else []), str(path)]))

