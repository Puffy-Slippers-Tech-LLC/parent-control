"""Finite ambient history; the controller owns public visits and manager lifetime.

Only inert, exclusively created attempt fixtures are changed. Every operation
has an append-only intent and independently observed result in the existing
private attempt allocation. Unknown entries are preserved on recovery.
"""

import copy
import hashlib
import json
import os
from pathlib import Path
import pwd
import stat
import sys

import system_guest as guest
import system_kiosk_confinement as confinement
import system_kiosk_scope as scope
import system_native_update as checkpoints


PARENT = Path('/usr/share')
STEPS = ('initial', 'empty-added', 'empty-removed', 'replaced',
         'replacement-restored', 'writable', 'mode-restored', 'foreign-owned',
         'owner-restored', 'unlinked', 'unlinked-restored')
KINDS = {'file': 'file', 'directory': 'directory', 'link': 'link',
         'vanished': 'file', 'empty': 'directory', 'added': 'directory'}


def binding():
    marker = guest.guard()
    return {key: marker[key] for key in ('run', 'package_sha256', 'selected_inputs_sha256')}


def path(name):
    guest.require(name in KINDS or name.removesuffix('-saved') in KINDS,
                  'retained-ambient:fixture-name')
    return PARENT / ('onpc-retained-' + binding()['run'] + '-' + name)


def snapshot(target, *, pinned=False):
    if not os.path.lexists(target):
        return None
    info = target.lstat()
    value = {'identity': confinement.sibling_identity(target)}
    if stat.S_ISLNK(info.st_mode):
        value['link'] = os.readlink(target)
    elif stat.S_ISDIR(info.st_mode):
        names = sorted(item.name for item in target.iterdir())
        guest.require(names in ([], ['canary']), 'retained-ambient:unknown-child')
        value['children'] = {name: snapshot(target / name, pinned=pinned) for name in names}
    else:
        guest.require(stat.S_ISREG(info.st_mode) and info.st_nlink in ((0, 1) if pinned else (1,)) and
                      info.st_size <= 128,
                      'retained-ambient:fixture-type')
        value['sha256'] = guest.sha(target)
    return value


def host_state():
    return {name: snapshot(path(name)) for name in
            (*KINDS, 'file-saved', 'directory-saved', 'link-saved')}


def read(name):
    value = checkpoints.read_private(checkpoints.private() / ('retained-ambient-' + name + '.json'))
    guest.require(value['binding'] == binding(), 'retained-ambient:attempt-changed')
    return value


def save(name, **values):
    checkpoints.publish('retained-ambient-' + name + '.json', dict(binding=binding(), **values))


def create(name, kind=None, *, replacement=False):
    target = path(name)
    guest.require(not os.path.lexists(target), 'retained-ambient:fixture-collision')
    kind = kind or KINDS[name]
    if kind == 'link':
        target.symlink_to(path('vanished' if replacement else 'file').name)
    else:
        confinement.sibling_create(target, 0o755 if kind == 'directory' else 0o644, 0, 0,
            (('replacement-' if replacement else 'original-') + name + '\n').encode(),
            directory=kind == 'directory')
        if kind == 'directory' and name in ('empty', 'added'):
            (target / 'canary').unlink()
    return snapshot(target)


def new_fixture(value, name, kind, *, replacement=False, prior=None):
    """Check finite mutation data independently of the command's saved result."""
    guest.require(value is not None and (prior is None or
                  value['identity'][:2] != prior['identity'][:2]),
                  'retained-ambient:mutation-change')
    identity = value['identity']
    mode = {'file': stat.S_IFREG | 0o644, 'directory': stat.S_IFDIR | 0o755,
            'link': stat.S_IFLNK | 0o777}[kind]
    guest.require(identity[2:] == [mode, 0, 0], 'retained-ambient:mutation-change')
    if kind == 'link':
        expected = {'link': path('vanished' if replacement else 'file').name}
    else:
        data = (('replacement-' if replacement else 'original-') + name + '\n').encode()
        expected = {'sha256': hashlib.sha256(data).hexdigest()}
        if kind == 'directory':
            children = value.get('children', {})
            if name in ('empty', 'added'):
                expected = {'children': {}}
            else:
                child = children.get('canary')
                guest.require(child is not None and child['identity'][2:] ==
                              [stat.S_IFREG | 0o444, 0, 0], 'retained-ambient:mutation-change')
                expected = {'children': {'canary': dict(identity=child['identity'], **expected)}}
    guest.require(value == dict(identity=identity, **expected), 'retained-ambient:mutation-change')
    return value


def mutation_state(intent, step, actual):
    if step in ('writable', 'mode-restored', 'foreign-owned', 'owner-restored'):
        return metadata_state(intent, step)
    expected = copy.deepcopy(intent['before'])
    if step == 'empty-added':
        expected['added'] = new_fixture(actual['added'], 'added', 'directory')
    elif step == 'empty-removed':
        expected['added'] = None
    elif step == 'replaced':
        for name, kind in (('file', 'directory'), ('directory', 'file'), ('link', 'link')):
            expected[name + '-saved'] = expected[name]
            expected[name] = new_fixture(actual[name], name, kind, replacement=True,
                                         prior=expected[name])
    elif step == 'replacement-restored':
        for name in ('file', 'directory', 'link'):
            expected[name], expected[name + '-saved'] = expected[name + '-saved'], None
    elif step == 'unlinked':
        for name in ('vanished', 'empty'):
            expected[name] = None
    elif step == 'unlinked-restored':
        original = read('source')['original']
        for name in ('vanished', 'empty'):
            expected[name] = new_fixture(actual[name], name, KINDS[name], prior=original[name])
    else:
        raise guest.GuestError('retained-ambient:step')
    return expected


def remove(target, expected, *, recovering=False):
    actual = snapshot(target)
    if recovering and actual is None:
        return
    if recovering and expected is not None and 'children' in expected and actual is not None:
        guest.require(actual['identity'] == expected['identity'] and
                      set(actual['children']) <= set(expected['children']) and
                      all(value == expected['children'][name] for name, value in actual['children'].items()),
                      'retained-ambient:cleanup-identity')
    else:
        guest.require(actual == expected, 'retained-ambient:cleanup-identity')
    if expected is None:
        return
    if 'children' in expected:
        for name, child in expected['children'].items():
            remove(target / name, child, recovering=recovering)
        target.rmdir()
    else:
        target.unlink()


def prepare():
    parent = PARENT.lstat()
    guest.require(PARENT.resolve(strict=True) == PARENT and stat.S_ISDIR(parent.st_mode) and
                  parent.st_uid == parent.st_gid == 0 and not parent.st_mode & 0o022,
                  'retained-ambient:parent-trust')
    confinement.wait_kiosk_inactive(pwd.getpwnam('oh-no-parent-control'))
    guest.require(all(value is None for value in host_state().values()),
                  'retained-ambient:fixture-collision')
    save('prepare-intent', before=host_state())
    for name in KINDS:
        if name != 'added':
            value = create(name)
            save('created-' + name, fixture=name, snapshot=value)
    save('prepared', state=host_state())


def capture():
    original = read('prepared')['state']
    guest.require(host_state() == original, 'retained-ambient:fixture-changed')
    account = pwd.getpwnam('oh-no-parent-control')
    backend = json.loads(checkpoints.CONFIG.read_bytes())['backend']
    observed = scope.retained_observation(account, backend)
    source = confinement.bootstrap_view(confinement.PROC / str(observed['boundary']['pid']))
    root = confinement.PROC / str(observed['boundary']['pid']) / 'root'
    pins = {name: snapshot(root / path(name).relative_to('/'), pinned=True) for name in KINDS}
    # Native recreates ambient links in the private skeleton. Their original
    # private inode, not the host link inode, is the later invocation authority.
    for name in KINDS:
        guest.require((pins[name] is None) == (original[name] is None), 'retained-ambient:initial-absence')
        if original[name] is not None:
            guest.require({key: value for key, value in pins[name].items() if key != 'identity'} ==
                          {key: value for key, value in original[name].items() if key != 'identity'},
                          'retained-ambient:initial-source')
    save('source', original=original, pins=pins, observed=observed, source=source,
         boot=checkpoints.BOOT.read_text().strip())


def change(step):
    guest.require(step in STEPS and step != 'initial', 'retained-ambient:step')
    index = STEPS.index(step)
    previous = read('observed-' + STEPS[index - 1])
    guest.require(host_state() == previous['host'], 'retained-ambient:host-changed')
    intent = {'before': previous['host']}
    if step == 'foreign-owned':
        child = pwd.getpwnam('onpc-child-riley')
        intent['owner'] = [child.pw_uid, child.pw_gid]
    save('intent-' + step, **intent)
    if step == 'empty-added':
        create('added')
    elif step == 'empty-removed':
        remove(path('added'), previous['host']['added'])
    elif step == 'replaced':
        for name, kind in (('file', 'directory'), ('directory', 'file'), ('link', 'link')):
            path(name).rename(path(name + '-saved'))
            save('saved-' + name, snapshot=snapshot(path(name + '-saved')))
            value = create(name, kind, replacement=True)
            save('replacement-' + name, snapshot=value)
    elif step == 'replacement-restored':
        for name in ('file', 'directory', 'link'):
            remove(path(name), previous['host'][name])
            path(name + '-saved').rename(path(name))
    elif step in ('writable', 'mode-restored'):
        original = read('source')['original']
        for name in ('file', 'directory'):
            mode = stat.S_IMODE(original[name]['identity'][2])
            path(name).chmod(mode | 0o022 if step == 'writable' else mode)
    elif step in ('foreign-owned', 'owner-restored'):
        original = read('source')['original']
        for name in ('file', 'directory'):
            uid, gid = intent['owner'] if step == 'foreign-owned' else original[name]['identity'][3:5]
            os.chown(path(name), uid, gid, follow_symlinks=False)
    elif step == 'unlinked':
        for name in ('vanished', 'empty'):
            remove(path(name), previous['host'][name])
    elif step == 'unlinked-restored':
        for name in ('vanished', 'empty'):
            create(name)
    actual = host_state()
    guest.require(actual == mutation_state(intent, step, actual),
                  'retained-ambient:' + ('metadata-change' if step in
                  ('writable', 'mode-restored', 'foreign-owned', 'owner-restored') else 'mutation-change'))
    save('changed-' + step, state=actual)


def metadata_state(intent, step):
    """Derive exact metadata changes from the independently recorded pre-state."""
    expected = copy.deepcopy(intent['before'])
    original = read('source')['original']
    for name in ('file', 'directory'):
        identity = expected[name]['identity']
        guest.require(identity[:2] == original[name]['identity'][:2],
                      'retained-ambient:metadata-original-inode')
        prior = copy.deepcopy(original[name])
        if step == 'mode-restored':
            prior['identity'][2] |= 0o022
        elif step == 'owner-restored':
            prior['identity'][3:5] = read('intent-foreign-owned')['owner']
        guest.require(intent['before'][name] == prior, 'retained-ambient:metadata-prestate')
        if step in ('writable', 'mode-restored'):
            identity[2] = original[name]['identity'][2] | (0o022 if step == 'writable' else 0)
        else:
            identity[3:5] = intent['owner'] if step == 'foreign-owned' else original[name]['identity'][3:5]
    return expected


def ordinary(state):
    scope.verify_vendor_pam(lambda *_: None)
    for account in scope.ordinary_accounts().values():
        guest.require(confinement.user_command(account, ['/bin/sh', '-c', 'printf retained-control']) ==
                      b'retained-control', 'retained-ambient:ordinary-execution')
        for name, value in state.items():
            if value is None or name.endswith('-saved') or 'link' in value:
                continue
            target = path(name)
            if 'children' in value:
                if not value['children']:
                    continue
                target = target / 'canary'
                value = value['children']['canary']
            guest.require(hashlib.sha256(confinement.user_command(account,
                          ['/usr/bin/cat', str(target)])).hexdigest() == value['sha256'],
                          'retained-ambient:ordinary-content')


def private_entries(root, original, *, narrowed=False):
    """Compare actual original pins/bytes; never accept equal marker hashes alone."""
    for name in KINDS:
        visible = root / path(name).relative_to('/')
        expected = original[name]
        if expected is None or (narrowed and name == 'file'):
            guest.require(not os.path.lexists(visible), 'retained-ambient:unexpected-entry')
        elif narrowed and name == 'directory':
            info = visible.lstat()
            guest.require(stat.S_ISDIR(info.st_mode) and not list(visible.iterdir()) and
                          confinement.sibling_identity(visible)[:2] != expected['identity'][:2],
                          'retained-ambient:unsafe-directory-not-masked')
        else:
            actual = snapshot(visible, pinned=True)
            guest.require(actual is not None and ('link' in expected or
                          actual['identity'][:2] == expected['identity'][:2]) and
                          stat.S_IFMT(actual['identity'][2]) == stat.S_IFMT(expected['identity'][2]) and
                          {key: value for key, value in actual.items() if key != 'identity'} ==
                          {key: value for key, value in expected.items() if key != 'identity'},
                          'retained-ambient:original-pin-changed')


def manager_metadata(root, pins, host):
    """Same-inode host metadata is visible in the raw retained manager view."""
    for name in ('file', 'directory'):
        actual = snapshot(root / path(name).relative_to('/'), pinned=True)
        expected = copy.deepcopy(pins[name])
        # Replacement paths have independent inodes; only original-inode
        # metadata changes can affect the already pinned manager object.
        if host[name] is not None and host[name]['identity'][:2] == pins[name]['identity'][:2]:
            expected['identity'][2:5] = host[name]['identity'][2:5]
        guest.require(actual == expected, 'retained-ambient:manager-metadata')


def observe(step):
    guest.require(step in STEPS, 'retained-ambient:step')
    source = read('source')
    expected_host = (read('prepared')['state'] if step == 'initial' else read('changed-' + step)['state'])
    if step != 'initial':
        guest.require(expected_host == mutation_state(read('intent-' + step), step, expected_host),
                      'retained-ambient:' + ('metadata-change' if step in
                      ('writable', 'mode-restored', 'foreign-owned', 'owner-restored') else 'mutation-change'))
    guest.require(host_state() == expected_host, 'retained-ambient:mutation-not-observed')
    account = pwd.getpwnam('oh-no-parent-control')
    backend = source['source']['backend']
    guest.require(scope.retained_observation(account, backend) == source['observed'],
                  'retained-ambient:manager-changed')
    census = confinement.census()
    manager = confinement.PROC / str(source['observed']['boundary']['pid'])
    private_entries(manager / 'root', source['pins'])
    manager_metadata(manager / 'root', source['pins'], expected_host)
    ordinary(expected_host)
    attribute = 'attr/apparmor/current' if backend == 'apparmor' else 'attr/current'
    label = 'onpc-kiosk-app (enforce)' if backend == 'apparmor' else 'system_u:system_r:onpc_kiosk_app_t:s0'
    views = []
    for process in confinement.PROC.iterdir():
        if not process.name.isdecimal():
            continue
        try:
            if (process / attribute).read_text().strip().rstrip('\0') != label:
                continue
            descriptor = os.pidfd_open(int(process.name))
        except (FileNotFoundError, ProcessLookupError):
            continue
        try:
            identity = confinement.process_identity(process)
            guest.require(identity[2] == (str(account.pw_uid),) * 4,
                          'retained-ambient:app-identity')
            marker = process / 'root/usr/share/oh-no-parent-control/confinement/retained-view'
            invocation = confinement.bootstrap_object(marker) + [guest.sha(marker)]
            view = confinement.bootstrap_view(process, source=source['source'], invocation_marker=invocation)
            private_entries(process / 'root', source['pins'],
                            narrowed=step in ('writable', 'foreign-owned'))
            guest.require(not confinement.exited(descriptor) and
                          confinement.process_identity(process) == identity,
                          'retained-ambient:app-changed')
            views.append(view)
        finally:
            os.close(descriptor)
    guest.require(views and host_state() == expected_host and
                  scope.retained_observation(account, backend) == source['observed'],
                  'retained-ambient:incomplete-observation')
    guest.require(b'systemd ' in confinement.user_command(account,
        ['/usr/bin/systemd-run', '--user', '--wait', '--collect', '--pipe',
         '--unit=onpc-retained-positive-' + step, '/usr/bin/systemctl', '--version']),
        'retained-ambient:positive-native-exec')
    confinement.require_service_denial(account, backend, 'onpc-retained-denied-' + step + '.service',
                                      ['/bin/sh', '-c', 'exit 0'], lambda *_: None)
    save('observed-' + step, host=expected_host, census=census, views=views,
         manager=source['observed'], boot=checkpoints.BOOT.read_text().strip())


def removal_subset(actual, expected):
    """Only the recorded directory's already removed known children may differ."""
    return (actual is None or actual == expected or
            (expected is not None and actual is not None and 'children' in expected and
             actual['identity'] == expected['identity'] and
             set(actual['children']) <= set(expected['children']) and
             all(value == expected['children'][name] for name, value in actual['children'].items())))


def interrupted_state(step):
    """Accept only finite states attributable to the newest durable intent.

    No content or identity is adopted from a pathname. A creation without its
    result checkpoint remains unknown, even when its bytes look plausible.
    """
    intent = read('intent-' + step)
    before = intent['before']
    actual = host_state()
    allowed = copy.deepcopy(before)
    directory = checkpoints.private()
    if step in ('writable', 'mode-restored', 'foreign-owned', 'owner-restored'):
        after = metadata_state(intent, step)
        for name in ('file', 'directory'):
            guest.require(actual[name] in (before[name], after[name]),
                          'retained-ambient:cleanup-identity')
            allowed[name] = actual[name]
    elif step == 'replaced':
        for name in ('file', 'directory', 'link'):
            saved = name + '-saved'
            if actual[saved] is None:
                guest.require(actual[name] == before[name], 'retained-ambient:cleanup-identity')
                continue
            guest.require(actual[saved] == before[name], 'retained-ambient:cleanup-identity')
            for prefix in ('saved-', 'replacement-'):
                if (directory / ('retained-ambient-' + prefix + name + '.json')).exists():
                    expected = read(prefix + name)['snapshot']
                    guest.require((actual[saved] if prefix == 'saved-' else actual[name]) == expected,
                                  'retained-ambient:cleanup-identity')
            if actual[name] is not None:
                guest.require((directory / ('retained-ambient-replacement-' + name + '.json')).exists(),
                              'retained-ambient:cleanup-identity')
            allowed[name], allowed[saved] = actual[name], actual[saved]
    elif step == 'replacement-restored':
        for name in ('file', 'directory', 'link'):
            saved = name + '-saved'
            original = before[saved]
            guest.require(original is not None, 'retained-ambient:cleanup-record')
            if actual[saved] is None:
                guest.require(actual[name] == original, 'retained-ambient:cleanup-identity')
            else:
                guest.require(actual[saved] == original and removal_subset(actual[name], before[name]),
                              'retained-ambient:cleanup-identity')
            allowed[name], allowed[saved] = actual[name], actual[saved]
    elif step in ('empty-removed', 'unlinked'):
        for name in (('added',) if step == 'empty-removed' else ('vanished', 'empty')):
            guest.require(removal_subset(actual[name], before[name]), 'retained-ambient:cleanup-identity')
            allowed[name] = actual[name]
    # Other interrupted creations have no independent resulting inode proof.
    guest.require(actual == allowed, 'retained-ambient:cleanup-identity')
    return actual


def cleanup():
    """Recover only independently recorded fixture identities; unknown files refuse."""
    directory = checkpoints.private()
    if (directory / 'retained-ambient-cleanup.json').exists():
        guest.require(all(value is None for value in host_state().values()),
                      'retained-ambient:cleanup-replacement')
        return
    # Successful calls record complete state; interrupted calls admit only the
    # finite states attributable to their prior intent and original inode proof.
    if (directory / 'retained-ambient-cleanup-intent.json').exists():
        expected = read('cleanup-intent')['state']
        for name, value in expected.items():
            actual = snapshot(path(name))
            if actual != value:
                guest.require((directory / ('retained-ambient-removing-' + name + '.json')).exists(),
                              'retained-ambient:cleanup-identity')
                guest.require(read('removing-' + name)['snapshot'] == value and
                              removal_subset(actual, value), 'retained-ambient:cleanup-identity')
    else:
        expected = None
        for step in reversed(STEPS[1:]):
            if (directory / ('retained-ambient-changed-' + step + '.json')).exists():
                expected = read('changed-' + step)['state']
                break
            if (directory / ('retained-ambient-intent-' + step + '.json')).exists():
                expected = interrupted_state(step)
                break
        if expected is None:
            if (directory / 'retained-ambient-prepared.json').exists():
                expected = read('prepared')['state']
            else:
                # A cut during preparation can recover every recorded exclusive
                # creation. An unrecorded entry is unknown and stays untouched.
                expected = read('prepare-intent')['before']
                for name in KINDS:
                    if (directory / ('retained-ambient-created-' + name + '.json')).exists():
                        expected[name] = read('created-' + name)['snapshot']
        guest.require(host_state() == expected, 'retained-ambient:cleanup-identity')
        save('cleanup-intent', state=expected)
    for name, value in reversed(tuple(expected.items())):
        if value is not None:
            removing = directory / ('retained-ambient-removing-' + name + '.json')
            if not removing.exists():
                save('removing-' + name, snapshot=value)
            guest.require(read('removing-' + name)['snapshot'] == value, 'retained-ambient:cleanup-record')
            remove(path(name), value, recovering=True)
    guest.require(all(value is None for value in host_state().values()), 'retained-ambient:cleanup-incomplete')
    save('cleanup', outcome='passed')


def verify_history(record):
    source = read('source')
    for step in STEPS:
        result = read('observed-' + step)
        guest.require(result['manager'] == source['observed'] and result['boot'] == source['boot'] and
                      result['views'], 'retained-ambient:history-incomplete')
        record('onpc.kiosk.retained-ambient.' + step, json.dumps(result, sort_keys=True))
    guest.require(read('cleanup')['outcome'] == 'passed' and
                  all(value is None for value in host_state().values()),
                  'retained-ambient:cleanup-incomplete')


def checkpoint_names():
    fixed = ['prepare-intent', 'prepared', 'source', 'cleanup-intent', 'cleanup']
    fixed += ['created-' + name for name in KINDS if name != 'added']
    fixed += ['observed-' + step for step in STEPS]
    fixed += [prefix + step for step in STEPS[1:] for prefix in ('intent-', 'changed-')]
    fixed += [prefix + name for name in ('file', 'directory', 'link')
              for prefix in ('saved-', 'replacement-')]
    fixed += ['removing-' + name for name in (*KINDS, 'file-saved', 'directory-saved', 'link-saved')]
    return ['retained-ambient-' + name + '.json' for name in fixed]


def command(action, step=None):
    guest.guard()
    if action in ('change', 'observe'):
        guest.require(step in STEPS and (action == 'observe' or step != 'initial'),
                      'retained-ambient:step')
        guest.enable_diagnostics()
        return {'change': change, 'observe': observe}[action](step)
    guest.require(step is None and action in ('prepare', 'capture', 'cleanup'), 'retained-ambient:action')
    guest.enable_diagnostics()
    return {'prepare': prepare, 'capture': capture, 'cleanup': cleanup}[action]()


if __name__ == '__main__':
    guest.require(len(sys.argv) in (2, 3), 'retained-ambient:arguments')
    command(*sys.argv[1:])
