"""Dependencies local to the private-D-Bus component suite."""

import pytest
from dbusmock.testcase import BusType
from tests.support.private_dbus import private_bus


@pytest.fixture(scope='session')
def dbusmock_system():
    with private_bus(BusType.SYSTEM) as bus:
        yield bus


@pytest.fixture(scope='session')
def dbusmock_session():
    with private_bus(BusType.SESSION) as bus:
        yield bus
