"""Nondeleting recovery of a VM input mistakenly owned by the batch journal.

The public caller derives all paths and holds checkout/host activity. Durable
intents block ordinary retention writers until both ownership changes commit.
There is no session, rotation, adoption of an unregistered root or VM mutation.
"""
from contextlib import ExitStack
import copy
import json
import os
from pathlib import Path
import re
import uuid

if __package__:
    from . import test_retention as retention
else:
    import test_retention as retention

MARKER = 'input-transfer.json'


def read_intent(store, fd):
    try:
        source = os.open(MARKER, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=fd)
    except FileNotFoundError:
        return None
    with os.fdopen(source) as stream:
        retention.private(os.fstat(stream.fileno()), regular=True)
        value = json.load(stream)
    validate_intent(store, value)
    return value


def validate_intent(store, value):
    fields = {'transaction', 'phase', 'selector', 'vm', 'source', 'destination',
              'source_run', 'destination_run', 'live', 'stale'}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError('retention: invalid input transfer intent')
    if (not all(retention.valid_token(value[key]) for key in (
            'transaction', 'source_run', 'destination_run'))
            or value['phase'] not in ('pending', 'complete')
            or not isinstance(value['selector'], str)
            or (value['selector'] != 'prepare_appsnapshot'
                and re.fullmatch(r'check_[a-z][a-z0-9_]*', value['selector']) is None)
            or not isinstance(value['vm'], str)
            or re.fullmatch(r'[A-Za-z0-9_.-]+', value['vm']) is None
            or not all(retention.journal_path(value[key]) for key in ('source', 'destination'))):
        raise ValueError('retention: invalid input transfer intent')
    source_path, destination = Path(value['source']), Path(value['destination'])
    if (source_path.name != 'retention-batch'
            or destination != source_path.with_name('retention-' + value['vm'])
            or store.path not in (source_path, destination)):
        raise ValueError('retention: foreign input transfer intent')
    for key in ('live', 'stale'):
        record = value[key]
        if key == 'stale' and record is None and value['selector'] == 'prepare_appsnapshot':
            continue
        if (not isinstance(record, dict) or set(record) != {'path', 'device', 'inode', 'mode'}
                or not isinstance(record['path'], str)
                or not Path(record['path']).is_absolute() or '..' in Path(record['path']).parts
                or any(type(record[field]) is not int or record[field] <= 0
                       for field in ('device', 'inode')) or record['mode'] != 0o700):
            raise ValueError('retention: invalid input transfer identity')
    if value['selector'] == 'prepare_appsnapshot':
        if (value['stale'] is not None
                or re.fullmatch(r'onpc-test-artifacts-[A-Za-z0-9_-]+',
                                Path(value['live']['path']).name) is None):
            raise ValueError('retention: invalid standalone snapshot input transfer')
    elif value['live']['path'] != value['stale']['path'] or value['live'] == value['stale']:
        raise ValueError('retention: input transfer requires a stale claim')


def mutation_guard(store, fd):
    intent = read_intent(store, fd)
    if intent is None:
        # The source intent is published first while both writers are locked.
        # An interrupted first write must also guard an absent-claim recipient.
        if store.path.name.startswith('retention-') and store.path.name != 'retention-batch':
            source = retention.Store(store.path.with_name('retention-batch'))
            try:
                with source.opened() as other:
                    pending = read_intent(source, other)
            except FileNotFoundError:
                pending = None
            if (pending is not None and pending['phase'] == 'pending'
                    and pending['destination'] == str(store.path)):
                raise ValueError('retention: input ownership transfer pending; resume its guarded recovery')
        return
    if intent['phase'] == 'complete':
        peer = retention.Store(intent['destination'] if str(store.path) == intent['source'] else intent['source'])
        with peer.opened() as other:
            peer_intent = read_intent(peer, other)
        if peer_intent is None or (peer_intent['transaction'] == intent['transaction']
                                  and peer_intent['phase'] == 'complete'):
            return  # Both durable commits precede this recoverable marker cleanup.
    raise ValueError('retention: input ownership transfer pending; resume its guarded recovery')


def latest(state, path, *, required=True):
    records = [record for entry in [*state['history'], state]
               for record in entry['paths'] if record['path'] == str(path)]
    if not records:
        if not required:
            return None
        raise ValueError('retention: input transfer requires both registered owners')
    return records[-1]


def audit(state):
    size = 0
    for _, record in retention.latest_allocations([*state['history'], state]):
        retention.remove(record, validate_only=True)
        size += retention.allocation_bytes(record)
    if size > retention.MAX_RETAINED_BYTES:
        raise ValueError('retention: input transfer exceeds retention budget; evidence preserved')


def transfer(source, destination, path, *, selector, vm, verify):
    """Transfer a recorded bundle over a stale claim, or a standalone input.

    `verify` is the existing manifest/baseline verifier, not a recovery override.
    Its success supplies no customer acceptance. Retries use the pinned intent.
    Standalone snapshot inputs require an absent destination claim instead.
    """
    path = Path(path)
    if (source.path.name != 'retention-batch'
            or destination.path != source.path.with_name('retention-' + vm)):
        raise ValueError('retention: invalid input transfer journals')
    with ExitStack() as stack:
        stores = sorted((source, destination), key=lambda store: str(store.path))
        fds = {str(store.path): stack.enter_context(store.opened()) for store in stores}
        for store in stores:
            stack.enter_context(store.locked(fds[str(store.path)], 'owner.lock', blocking=False))
        for store in stores:
            stack.enter_context(store.locked(fds[str(store.path)], 'writer.lock', transfer=True))
        sf, df = fds[str(source.path)], fds[str(destination.path)]
        states = [source.read(sf), destination.read(df)]
        if any(state is None or not state['finished'] for state in states) or any(
                'recovery-required' in os.listdir(fd) for fd in (sf, df)):
            raise ValueError('retention: input transfer requires finished, unmarked owners')
        ss, ds = states
        # Capture dependency ownership cannot move through this legacy recovery
        # route. A later custody protocol must explicitly transfer or release it.
        for state in states:
            retention.require_no_captures([*state['history'], state])
        si, di = read_intent(source, sf), read_intent(destination, df)
        # Completed markers are only a receipt-cleanup tail. Their commits were
        # already durable; later ordinary rotation may legitimately change runs.
        existing = si or di
        if existing and existing['phase'] == 'complete' and (si is None or di is None
                or si == di):
            if existing['selector'] != selector or existing['vm'] != vm or existing['live']['path'] != str(path):
                raise ValueError('retention: competing input transfer')
            for store, fd, intent in ((destination, df, di), (source, sf, si)):
                if intent is not None:
                    os.unlink(MARKER, dir_fd=fd)
                    os.fsync(fd)
            return False
        live, stale = latest(ss, path), latest(ds, path, required=selector != 'prepare_appsnapshot')
        if existing is None and 'retired' in live:
            receipt = live['retired']
            retention.latest_allocations([*ss['history'], ss])  # Validate receipt.
            if (receipt['destination'] == str(destination.path) and
                    {key: value for key, value in live.items() if key != 'retired'} == stale):
                retention.remove(stale, validate_only=True)
                return False
            raise ValueError('retention: input transfer ownership changed')
        if existing:
            intent = copy.deepcopy(existing)
            if (si is None or (di is not None and {**di, 'phase': 'pending'} != {**si, 'phase': 'pending'})
                    or intent['selector'] != selector or intent['vm'] != vm
                    or intent['source'] != str(source.path) or intent['destination'] != str(destination.path)
                    or intent['source_run'] != ss['run'] or intent['destination_run'] != ds['run']
                    or intent['live']['path'] != str(path)):
                raise ValueError('retention: input transfer owner or intent changed')
            intent['phase'] = 'pending'
            original_live, original_stale = intent['live'], intent['stale']
        else:
            if set(live) != {'path', 'device', 'inode', 'mode'}:
                raise ValueError('retention: input transfer requires a registered live allocation')
            if selector == 'prepare_appsnapshot':
                if stale is not None:
                    raise ValueError('retention: standalone input already has a destination claim')
            elif stale is None or set(stale) != set(live) or live == stale:
                raise ValueError('retention: input transfer requires a stale registered claim')
            original_live, original_stale = copy.deepcopy(live), copy.deepcopy(stale)
            intent = dict(transaction=uuid.uuid4().hex, phase='pending', selector=selector, vm=vm,
                          source=str(source.path), destination=str(destination.path),
                          source_run=ss['run'], destination_run=ds['run'],
                          live=original_live, stale=original_stale)
        validate_intent(source, intent)
        retired = dict(original_live, retired=dict(transaction=intent['transaction'],
                       destination=str(destination.path), run=ds['run']))
        if live not in (original_live, retired) or stale not in (original_stale, original_live):
            raise ValueError('retention: input transfer records changed')
        # Only the destination claim may be stale or absent. Audit projected states before
        # writing anything, including the live root and all unrelated allocations.
        projected_source, projected_destination = copy.deepcopy(ss), copy.deepcopy(ds)
        for entry in reversed([*projected_source['history'], projected_source]):
            for record in reversed(entry['paths']):
                if record['path'] == str(path):
                    record.update(retired)
                    break
            else:
                continue
            break
        if stale != original_live:
            projected_destination['paths'].append(copy.deepcopy(original_live))
        retention.remove(original_live, validate_only=True)
        if verify(path) != 0:
            raise ValueError('retention: published input verification failed; owners preserved')
        audit(projected_source)
        audit(projected_destination)
        # Guard both writers before either ownership mutation. Destination's
        # journal cannot change until its durable intent is in place.
        if si is None:
            source.save(sf, intent, name=MARKER)
        if di is None:
            destination.save(df, intent, name=MARKER)
        destination.save(df, projected_destination)
        source.save(sf, projected_source)
        complete = dict(intent, phase='complete')
        source.save(sf, complete, name=MARKER)
        destination.save(df, complete, name=MARKER)
        os.unlink(MARKER, dir_fd=df)
        os.fsync(df)
        os.unlink(MARKER, dir_fd=sf)
        os.fsync(sf)
        return True
