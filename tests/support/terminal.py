"""Bounded pipe/PTY capture for unprivileged package notice tests."""

import errno
import os
import pty
import select
import subprocess
import time


def capture(command, env, terminal, *, timeout=10):
    """Run one owned child while draining output, including when it exceeds a PTY buffer."""
    environment = {**env, "TERM": terminal or "xterm"}
    if not terminal:
        result = subprocess.run(
            command, env=environment, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, timeout=timeout,
        )
        return result, result.stdout

    master, slave = pty.openpty()
    process = None
    deadline = time.monotonic() + timeout
    chunks = []
    try:
        process = subprocess.Popen(command, env=environment, stdout=slave, stderr=slave)
        os.close(slave)
        slave = None
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout)
            ready, _, _ = select.select([master], [], [], remaining)
            if not ready:
                raise subprocess.TimeoutExpired(command, timeout)
            try:
                chunk = os.read(master, 65536)
            except OSError as error:
                if error.errno != errno.EIO:
                    raise
                break
            if not chunk:
                break
            chunks.append(chunk)
        returncode = process.wait(timeout=max(0, deadline - time.monotonic()))
        output = b"".join(chunks).decode()
        return subprocess.CompletedProcess(command, returncode, stdout=output), output
    except BaseException:
        if process is not None and process.poll() is None:
            process.kill()
            process.wait(timeout=5)
        raise
    finally:
        if slave is not None:
            os.close(slave)
        os.close(master)
