"""Qualified product-free system preparation, after guarded SSH readiness.

The caller selects immutable inputs before VM acquisition. This adapter owns
neither a fixture producer nor VM recovery; the existing attempt owns staging.
"""

import argparse
import hashlib
import json
import os
import re
import sys

from tools import fixture_execution, fixture_provision


SUBSETS = ('trusted-hard',)


def attempt_id(directory):
    """Distinguish identical phase names in separate restored histories."""
    return directory.name[:100] + '-' + hashlib.sha256(
        os.fsencode(directory.resolve())).hexdigest()[:16]


def qualified_guest(guest):
    return (guest.get('fixture_boundary') == 'clean'
            and guest.get('ubuntu_version') == '26.04')


def selection_record(value):
    if value is None:
        raise ValueError('fixtures:execution-selection-required')
    selection = fixture_execution.Selection.from_record(
        value.record() if isinstance(value, fixture_execution.Selection) else value)
    if selection.target != 'ubuntu':
        raise ValueError('fixtures:system-product-free-target-not-qualified')
    return selection.record()


def command_selection(value=None):
    """Read the caller's fixed handoff; privileged consumers never select anew."""
    if value is None:
        parser = argparse.ArgumentParser(allow_abbrev=False)
        parser.add_argument('--fixture-selection', required=True)
        value = json.loads(parser.parse_args(sys.argv[1:]).fixture_selection)
    return selection_record(value)


def validate_input(value):
    """Authenticate frozen input without writes or poisoning a VM attempt."""
    record = selection_record(value)
    fixture_execution.verify(record)
    return record


def register_staging(directory, lease, attempt_id, path):
    if re.fullmatch(r'/run/onpc-fixture-[0-9a-f]{64}', path) is None:
        raise ValueError('fixtures:staging-path')
    # Intent precedes the provisioner's first guest write. The sole VM owner
    # restores this generation on every outcome; this is no separate journal.
    target = directory / 'fixture-staging-intent.json'
    with target.open('xb') as stream:
        stream.write(json.dumps({'run': lease.state['run'],
            'vm_uuid': lease.state['domain_uuid'], 'attempt_id': attempt_id,
            'staging': path}, sort_keys=True).encode() + b'\n')
        stream.flush()
        os.fsync(stream.fileno())


def prepare(vm, lease, directory, selection):
    if not qualified_guest(lease.capture.state['guest']):
        raise ValueError('fixtures:system-product-free-target-not-qualified')
    selection = validate_input(selection)
    identity = attempt_id(directory)
    controller = fixture_provision.Provisioner(lease, vm,
        register_staging=lambda path: register_staging(directory, lease, identity, path))
    receipt = controller.provision(selection, SUBSETS, attempt_id=identity)
    controller.require_ready(receipt)
    return {'vm': vm, 'lease': lease, 'directory': directory,
            'controller': controller, 'receipt': receipt}
