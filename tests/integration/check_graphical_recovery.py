#!/usr/bin/python3
"""Resume recorded cleanup, or audit an exactly restored powered-off guest."""

import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import xml.etree.ElementTree as ET

import system_runner as runner
from qualification_storage import allocate, recovery_session


def recorded_graphics_type(xml):
    displays = ET.fromstring(xml).findall('devices/graphics')
    runner.validate_observer(displays)
    runner.require(displays[0].get('type') in ('vnc', 'spice'),
                   'recovery:invalid-graphics')
    return displays[0].get('type')


def main(*, graphics_type='vnc'):
    runner.require(len(sys.argv) == 1, 'recovery:invalid-arguments')
    runner.require(graphics_type in (None, 'vnc', 'spice'), 'recovery:invalid-graphics')
    runner.require(os.geteuid() == os.getegid() == 0, 'recovery:root-required')
    runner.require(Path.cwd() == runner.ROOT == runner.baseline.guest_contract.CHECKOUT,
                   'recovery:checkout')
    with recovery_session():
        return recover(graphics_type)


def recover(graphics_type):
    os.umask(0o077)
    kind = 'graphical' if graphics_type == 'vnc' else 'system'
    directory = Path(allocate(tempfile.mkdtemp, prefix=f'onpc-{kind}-recovery-'))
    commands = runner.Commands()
    commands.directory = directory
    source = None
    result = {'scope': f'recorded-{kind}-cleanup-only', 'outcome': 'failed',
              'original_attempt_outcome': 'unchanged', 'evidence_directory': str(directory)}
    started = time.monotonic()
    try:
        api, guestfs = importlib.import_module('libvirt'), importlib.import_module('guestfs')
        api.virEventRegisterDefaultImpl()
        def events():
            while True:
                api.virEventRunDefaultImpl()
        threading.Thread(target=events, daemon=True, name='libvirt-events').start()
        source = runner.baseline.LibvirtSource(api)
        if graphics_type is None:
            graphics_type = recorded_graphics_type(source.domain.XMLDesc(0))
        lease = runner.Lease(source, commands,
                            lambda disk, digest: runner.baseline.inspect_guest(guestfs, disk, digest),
                            graphics_type=graphics_type)
        if graphics_type == 'vnc':
            lease.recover_graphical_cleanup()
        else:
            lease.recover_system_cleanup()
        result['outcome'] = 'passed'
        result['lease_phase'] = lease.state['phase']
    except (Exception, KeyboardInterrupt) as error:
        result['category'] = runner.error_category(error)
        result['exception_type'] = type(error).__name__
    finally:
        if source is not None:
            try:
                source.close()
            except BaseException:
                result['outcome'] = 'failed'
                result['connection_cleanup'] = 'failed'
        result['duration_seconds'] = round(time.monotonic() - started, 3)
        (directory / 'result.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result, sort_keys=True))
    return 0 if result['outcome'] == 'passed' else 1


if __name__ == '__main__':
    sys.exit(main())
