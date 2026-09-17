#!/usr/bin/python3
"""Bounded commands; cleanup signals only a pidfd opened for the spawned child."""

import json
from contextlib import ExitStack
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import termios
import time


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
        self.progress = None
        self.watch_command = None

    def run(self, args, *, timeout=120, check=True, input=None, merge_stderr=True,
            on_output=None, terminal=False):
        require(not terminal or input is None, 'command:terminal-input-unsupported')
        self.sequence += 1
        sequence = self.sequence
        self.last_returncode = None
        # The guest payload also uses this module without host spectator code.
        try:
            import watch_activity
        except ModuleNotFoundError:
            watch_activity = None
        watch = watch_activity.command(args, self.watch_command) if watch_activity else None
        output_failed = False

        def forward(data, stream):
            nonlocal output_failed
            if watch is not None:
                watch.output(data, stream)
            if data and on_output is not None and not output_failed:
                try:
                    on_output(data, stream)
                except BaseException:
                    output_failed = True
                    raise

        # Command diagnostics stay private; only fixed categories reach the console.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors, ExitStack() as stack:
            master = slave = None
            if terminal:
                master, slave = os.openpty()
                stack.callback(os.close, master)
                stack.callback(os.close, slave)
                os.set_blocking(master, False)
                termios.tcsetwinsize(slave, (24, 100))

            def drain_terminal():
                if master is not None:
                    # Bound each drain so a continuously writing child cannot
                    # prevent deadline/ownership processing. Retain raw bytes.
                    for _ in range(16):
                        try:
                            data = os.read(master, 65536)
                        except BlockingIOError:
                            break
                        if not data:
                            break
                        output.write(data)
                    output.flush()

            child = subprocess.Popen(args, stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
                                     stdout=slave if terminal else output,
                                     stderr=slave if terminal else subprocess.STDOUT if merge_stderr else errors,
                                     pass_fds=(() if self.lock_fd is None else (self.lock_fd,)),
                                     **({'env': {**os.environ, 'TERM': 'xterm-256color'}} if terminal else {}))
            pidfd = os.pidfd_open(child.pid)
            offset = 0
            error_offset = 0
            progress_failed = False
            try:
                try:
                    if self.progress is None and watch is None and on_output is None and not terminal:
                        child.communicate(input=input, timeout=timeout)
                    else:
                        # Keep raw command diagnostics private. The caller's
                        # narrow parser forwards only registered test events.
                        started = time.monotonic()
                        while True:
                            try:
                                child.communicate(input=input, timeout=min(0.1, max(0.001,
                                    timeout - (time.monotonic() - started))))
                                complete = True
                            except subprocess.TimeoutExpired:
                                complete = False
                            input = None
                            drain_terminal()
                            data = os.pread(output.fileno(), os.fstat(output.fileno()).st_size - offset, offset)
                            offset += len(data)
                            if watch is not None or on_output is not None:
                                forward(data, 'stdout')
                                error_data = os.pread(errors.fileno(),
                                    os.fstat(errors.fileno()).st_size - error_offset, error_offset)
                                error_offset += len(error_data)
                                forward(error_data, 'stderr')
                            if data and self.progress is not None:
                                try:
                                    self.progress(data)
                                except BaseException:
                                    progress_failed = True
                                    raise
                            if complete:
                                break
                            if time.monotonic() - started >= timeout:
                                raise subprocess.TimeoutExpired(args, timeout)
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
                drain_terminal()
                output.seek(0)
                raw = output.read()
                errors.seek(0)
                error_bytes = errors.read()
                if self.directory:
                    path = self.directory / f'command-{sequence:04d}.txt'
                    with path.open('xb') as stream:
                        stream.write(raw)
                    path.chmod(0o600)
                    if error_bytes:
                        path = self.directory / f'command-{sequence:04d}-stderr.txt'
                        with path.open('xb') as stream:
                            stream.write(error_bytes)
                        path.chmod(0o600)
                forward(raw[offset:], 'stdout')
                forward(error_bytes[error_offset:], 'stderr')
                if watch is not None:
                    watch.finish(child.returncode)
                if self.progress is not None and not progress_failed and len(raw) > offset:
                    self.progress(raw[offset:])
            self.last_returncode = child.returncode
            require(not check or child.returncode == 0, 'command:failed:' + Path(args[0]).name)
            return raw

    def info(self, path, active=False):
        return json.loads(self.run(['qemu-img', 'info', '--output=json', '-f', 'qcow2',
                                              *(['-U'] if active else []), str(path)]))
