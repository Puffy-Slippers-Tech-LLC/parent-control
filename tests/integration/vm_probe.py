"""Root commands in an owned maintenance guest, using its saved SSH identity.

Only the guest command is arbitrary. The host controller, domain, snapshot
credentials, transport flags, locks and observation remain fixed and guarded.
"""

import re
import sys
import xml.etree.ElementTree as ET

import system_runner as system
from watch_activity import operation


def execute(lease, command, timeout):
    """Probe the present instance; never boot, restore, rekey or correct time."""
    from online_snapshot import load, connect_saved_transport, validate_saved_snapshot
    # The caller has resumed the shared maintenance lease. Existing detached
    # display observation stays attached throughout and outlives this command.
    with operation('Running a root command in the owned guest'):
        lease.guard()
        snapshot = lease.source.domain.snapshotCurrent(0)
        name, xml = snapshot.getName(), snapshot.getXMLDesc(0)
        system.require(re.fullmatch(r'onpc-v[0-9]+(?:\.[0-9]+)*', name) is not None,
                       'vm-probe:online-appsnapshot-required')
        tree = ET.fromstring(xml)
        memory, domain = tree.find('memory'), tree.find('domain')
        system.require(tree.findtext('state') == 'running' and memory is not None and
                       memory.get('snapshot') == 'internal' and domain is not None,
                       'vm-probe:online-appsnapshot-required')
        record = load(lease.source, name, xml)
        system.require(record is not None, 'vm-probe:snapshot-credentials-missing')
        validate_saved_snapshot(lease, xml, record)
        hostname = system.address(lease.source)
        transport = connect_saved_transport(lease, lease.commands.directory, record, hostname)

        def output(data, stream):
            destination = sys.stdout.buffer if stream == 'stdout' else sys.stderr.buffer
            destination.write(data)
            destination.flush()

        transport.call(command, timeout=timeout, check=False, on_stream=output)
        # Guard probes can replace Commands.last_returncode; capture it first.
        status = transport.commands.last_returncode
        lease.guard()
        system.require(type(status) is int and 0 <= status <= 255, 'vm-probe:invalid-exit-status')
        return status
