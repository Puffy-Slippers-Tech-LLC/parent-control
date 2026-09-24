"""Private D-Bus fixtures with short, scoped AF_UNIX runtime paths."""

from contextlib import contextmanager
import tempfile
from unittest.mock import patch

from dbusmock.testcase import PrivateDBus
from tools.test_storage import runtime_directory


@contextmanager
def private_bus(kind):
    with runtime_directory(prefix='onpc-bus-') as runtime:
        # python-dbusmock has no socket-directory argument. Change tempfile's
        # public default only while its synchronous constructor creates the
        # tiny bus config/socket directory; all test payloads keep disk TMPDIR.
        with patch.object(tempfile, 'tempdir', str(runtime)):
            bus = PrivateDBus(kind)
        try:
            bus.start()
            yield bus
        finally:
            bus.stop()
