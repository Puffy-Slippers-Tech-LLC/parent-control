"""Real local pipes, fake libvirt: no VM, host console or process signals."""

import os
from pathlib import Path
import sys
from unittest.mock import Mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'integration'))
import graphical_serial as serial
sys.path.pop(0)

XML = '''<domain><devices>
<serial type="pty"><target type="isa-serial" port="0"><model name="isa-serial"/></target><alias name="serial0"/></serial>
<console type="pty"><target type="serial" port="0"/></console>
</devices></domain>'''


@pytest.fixture
def console(tmp_path):
    tmp_path.chmod(0o700)
    adapter = Mock(phase='running')
    lease = adapter.lease
    lease.source.api.VIR_STREAM_NONBLOCK = 1
    lease.source.api.VIR_DOMAIN_CONSOLE_SAFE = 2
    lease.source.uuid = 'owned-uuid'
    lease.view.domain_id = 17
    connection = lease.source.api.open.return_value
    connection.getURI.return_value = serial.URI
    domain = connection.lookupByUUIDString.return_value
    domain.UUIDString.return_value = lease.source.uuid
    domain.ID.return_value = 17
    domain.XMLDesc.return_value = lease.source.domain.XMLDesc.return_value = XML
    stream = connection.newStream.return_value
    stream.recv.return_value = -2
    stream.send.side_effect = len
    port = serial.SerialConsole(adapter, tmp_path)
    yield port, adapter, connection, domain, stream
    port.close()


def test_exclusive_public_stream_transfers_both_directions_and_closes(console):
    port, adapter, connection, domain, stream = console
    stream.recv.side_effect = [b'fixture-output', -2]
    os.write(port.fds[0], b'fixed-input')
    port.step()
    domain.openConsole.assert_called_once_with('serial0', stream, 2)
    connection.newStream.assert_called_once_with(1)
    stream.send.assert_called_once_with(b'fixed-input')
    assert os.read(port.fds[1], 128) == b'fixture-output'
    fds = list(port.fds)
    port.close()
    stream.abort.assert_called_once()
    connection.close.assert_called_once()
    for fd in fds:
        with pytest.raises(OSError):
            os.fstat(fd)
    adapter.phase = 'stopped'
    port.step()
    assert stream.send.call_count == 1
    adapter.lease.source.domain.openConsole.assert_not_called()


@pytest.mark.parametrize('fault', ['lease', 'domain', 'xml', 'busy', 'interrupt', 'pipe', 'directory'])
def test_refusal_closes_owned_resources_and_never_sends_input(console, fault):
    port, adapter, connection, domain, stream = console
    os.write(port.fds[0], b'private-canary')
    if fault == 'lease':
        adapter.revalidate.side_effect = RuntimeError('ownership-lost')
    elif fault == 'domain':
        domain.ID.return_value = 18
    elif fault == 'xml':
        domain.XMLDesc.return_value = XML.replace('pty', 'file')
    elif fault in ('busy', 'interrupt'):
        domain.openConsole.side_effect = (KeyboardInterrupt() if fault == 'interrupt'
                                         else RuntimeError('console-busy'))
    elif fault == 'pipe':
        path = port.directory / 'serial-console.in'
        path.rename(port.directory / 'preserved-pipe')
        path.write_text('unrelated')
    else:
        port.directory.chmod(0o755)
    with pytest.raises(KeyboardInterrupt if fault == 'interrupt' else RuntimeError):
        port.step()
    assert port.closed and not port.fds and not port.pending_in
    stream.send.assert_not_called()
    if fault in ('busy', 'interrupt'):
        stream.abort.assert_called_once()
    if fault in ('domain', 'xml', 'busy', 'interrupt'):
        connection.close.assert_called_once()
    if fault == 'pipe':
        assert path.read_text() == 'unrelated'


def test_identity_loss_after_attachment_revokes_without_more_input(console):
    port, adapter, connection, domain, stream = console
    port.step()
    os.write(port.fds[0], b'late-input')
    adapter.revalidate.side_effect = RuntimeError('replaced')
    with pytest.raises(RuntimeError):
        port.step()
    stream.send.assert_not_called()
    stream.abort.assert_called_once()
    assert not port.fds


def test_partial_io_and_backpressure_preserve_bytes(console):
    port, _, _, _, stream = console
    stream.send.side_effect = [-2, 2, 3]
    os.write(port.fds[0], b'hello')
    port.step()
    assert port.pending_in == b'hello'
    port.step()
    assert port.pending_in == b'llo'
    port.step()
    assert not port.pending_in
    assert [call.args[0] for call in stream.send.call_args_list] == [b'hello', b'hello', b'llo']


@pytest.mark.parametrize('chunk_size', [1, 16, 64, 4096])
def test_full_install_command_survives_partial_sends_and_backpressure(console, chunk_size):
    port, _, _, _, stream = console
    command = (b"/usr/bin/sudo -k -p $'\\nONPC-INSTALL-PASSWORD: ' -- /usr/bin/apt-get install -y "
               b"/var/lib/onpc-e2e-assets/package.deb && printf 'ONPC-INSTALL-%s\\n' 'OK'\n")
    delivered = bytearray()
    blocked = False

    def send(data):
        nonlocal blocked
        blocked = not blocked
        if blocked:
            return -2
        count = min(len(data), chunk_size)
        delivered.extend(data[:count])
        return count

    stream.send.side_effect = send
    assert os.write(port.fds[0], command) == len(command)
    for _ in range(2 * len(command)):
        port.step()
        if not port.pending_in:
            break
    assert not port.pending_in
    assert delivered == command
    assert delivered.count(b'\n') == 1 and delivered.endswith(b"'OK'\n")


def test_abort_failure_still_closes_connection_and_every_fd(console):
    port, _, connection, _, stream = console
    port.step()
    stream.abort.side_effect = RuntimeError('abort-failure')
    with pytest.raises(RuntimeError, match='abort-failure'):
        port.close()
    connection.close.assert_called_once()
    assert not port.fds


@pytest.mark.parametrize('change', [('pty', 'file'), ('serial0', 'serial1'),
                                  ('isa-serial', 'usb-serial'), ('port="0"', 'port="1"')])
def test_unexpected_device_cannot_attach(change):
    with pytest.raises(RuntimeError, match='serial:'):
        serial.serial_device(XML.replace(*change))


def test_getty_provisioning_refuses_running_or_unowned_guest():
    lease = Mock(fd=None, state={'phase': 'isolated', 'domain_id': None})
    with pytest.raises(RuntimeError, match='outside-provisioning'):
        serial.provision_getty(lease, Mock())
    lease.guard.assert_not_called()
