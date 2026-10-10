"""Offline baseline-only reconciliation of the finite reusable fixture set."""
import hashlib
import json
from pathlib import Path
import stat
from types import SimpleNamespace

from tests.fixtures import baseline_assets as assets

RECORD = '/var/lib/onpc-baseline-fixtures.json'
PURPOSE = 'onpc-reusable-fixtures-v1'


def require(value):
    if not value:
        raise ValueError('baseline:fixtures-unsafe-or-stale; run tools/prepare-vm')


def build_payload():
    """Compile only native inputs using the maintained builder and disk scratch."""
    import tempfile
    from tools.test_storage import scratch_directory
    from tests.fixtures.build_test_applications import _compile_native, GUI_SOURCE, GTK_AUTOMATION_SOURCE
    with tempfile.TemporaryDirectory(prefix='baseline-native-', dir=scratch_directory()) as temporary:
        root = Path(temporary)
        result = {role: _compile_native(root, identity=role).read_bytes()
                  for role, *_ in assets.ASSETS}
        result['mechanical'] = _compile_native(root, headless=True).read_bytes()
        result['onpc-test-gui.py'] = GUI_SOURCE.read_bytes()
        result['gtk_automation.py'] = GTK_AUTOMATION_SOURCE.read_bytes()
    require(len({result[role] for role, *_ in assets.ASSETS}) == 4)
    return result


def accounts(g):
    rows = [line.split(':') for line in g.read_file('/etc/passwd').decode().splitlines()]
    result = {'system': SimpleNamespace(pw_uid=0, pw_gid=0, pw_dir='/')}
    for role, name in (('child', 'onpc-child-riley'), ('other', 'onpc-child-jordan'),
                       ('parent', 'onpc-parent-jamie')):
        matches = [row for row in rows if row[0] == name]
        require(len(matches) == 1 and len(matches[0]) == 7)
        row = matches[0]
        require(int(row[2]) >= 1000 and row[5] == '/home/' + name)
        result[role] = SimpleNamespace(pw_uid=int(row[2]), pw_gid=int(row[3]), pw_dir=row[5])
    return result


def directory(g, path, uid=0, gid=0, *, create=False):
    for candidate in reversed((Path(path), *Path(path).parents)):
        name = str(candidate)
        if not g.exists(name) and not g.is_symlink(name):
            require(create)
            g.mkdir(name)
            g.chown(uid, gid, name)
            g.chmod(0o755, name)
        info = g.lstatns(name)
        require(g.realpath(name) == name and stat.S_ISDIR(info['st_mode'])
                and info['st_uid'] in (0, uid) and not info['st_mode'] & 0o022)


def regular(g, path, uid, gid, mode):
    info = g.lstatns(path)
    require(g.realpath(path) == path and stat.S_ISREG(info['st_mode'])
            and info['st_nlink'] == 1 and info['st_uid'] == uid
            and info['st_gid'] == gid and stat.S_IMODE(info['st_mode']) == mode)


def write_record(g, record):
    """The fixed root-owned transaction file is atomically replaced."""
    temporary = RECORD + '.new'
    if g.exists(temporary) or g.is_symlink(temporary):
        regular(g, temporary, 0, 0, 0o600)
    g.write(temporary, (json.dumps(record, sort_keys=True) + '\n').encode())
    g.chown(0, 0, temporary)
    g.chmod(0o600, temporary)
    g.sync()
    g.mv(temporary, RECORD)
    g.sync()


def reconcile(g, payload):
    """Repeat without writes; atomic owned upgrades and interrupted retries."""
    # Appliance-created staging files stay private even if writing is interrupted
    # before chmod. Guest modes are set explicitly before each atomic placement.
    g.umask(0o077)
    identities = accounts(g)
    declaration = assets.files(identities)
    desired = {}
    contents = {}
    for path, (source, mode, role) in declaration.items():
        data = source if isinstance(source, bytes) else payload[source]
        account = identities[role]
        desired[path] = {'sha256': hashlib.sha256(data).hexdigest(), 'mode': mode,
                         'uid': account.pw_uid, 'gid': account.pw_gid}
        contents[path] = data
    directory(g, '/var/lib')
    previous = {'purpose': PURPOSE, 'files': {}, 'pending': None}
    if g.exists(RECORD) or g.is_symlink(RECORD):
        regular(g, RECORD, 0, 0, 0o600)
        previous = json.loads(g.read_file(RECORD))
        require(set(previous) == {'purpose', 'files', 'pending'} and previous['purpose'] == PURPOSE
                and set(previous['files']) <= set(desired)
                and (previous['pending'] is None or previous['pending'] in desired))
    # Preflight the whole finite set before any mutation, including unrelated collisions.
    for path, spec in desired.items():
        ancestor = Path(path).parent
        while not g.exists(str(ancestor)) and not g.is_symlink(str(ancestor)):
            ancestor = ancestor.parent
        directory(g, str(ancestor), spec['uid'], spec['gid'])
        if g.exists(path) or g.is_symlink(path):
            regular(g, path, spec['uid'], spec['gid'], spec['mode'])
            old = previous['files'].get(path)
            require(old is not None and set(old) == set(spec)
                    and {k: old[k] for k in ('mode', 'uid', 'gid')} ==
                        {k: spec[k] for k in ('mode', 'uid', 'gid')}
                    and g.checksum('sha256', path) in (old['sha256'], spec['sha256']))
        temporary = path + '.onpc-baseline-new'
        if g.exists(temporary) or g.is_symlink(temporary):
            require(previous['pending'] == path)
            info = g.lstatns(temporary)
            if info['st_uid'] == 0 and stat.S_IMODE(info['st_mode']) == 0o600:
                regular(g, temporary, 0, 0, 0o600)
            else:
                require(stat.S_IMODE(info['st_mode']) in (0o600, spec['mode']))
                regular(g, temporary, spec['uid'], spec['gid'], stat.S_IMODE(info['st_mode']))
                require(g.checksum('sha256', temporary) == spec['sha256'])
    record = {'purpose': PURPOSE, 'files': dict(previous['files']), 'pending': previous['pending']}
    for path, spec in desired.items():
        if g.exists(path) and g.checksum('sha256', path) == spec['sha256']:
            continue
        directory(g, str(Path(path).parent), spec['uid'], spec['gid'], create=True)
        record['pending'] = path
        # Retain the old digest until atomic replacement has completed.
        record['files'].setdefault(path, spec)
        write_record(g, record)
        temporary = path + '.onpc-baseline-new'
        g.write(temporary, contents[path])
        g.chown(0, 0, temporary)
        g.chmod(0o600, temporary)
        require(g.checksum('sha256', temporary) == spec['sha256'])
        g.chown(spec['uid'], spec['gid'], temporary)
        g.chmod(spec['mode'], temporary)
        g.sync()
        g.mv(temporary, path)
        record['files'][path] = spec
        record['pending'] = None
        write_record(g, record)
    final = {'purpose': PURPOSE, 'files': desired, 'pending': None}
    if previous != final:
        write_record(g, final)
    verify(g)
    return declaration


def verify(g):
    regular(g, RECORD, 0, 0, 0o600)
    record = json.loads(g.read_file(RECORD))
    identities = accounts(g)
    declaration = assets.files(identities)
    require(set(record) == {'purpose', 'files', 'pending'} and record['purpose'] == PURPOSE
            and record['pending'] is None and set(record['files']) == set(declaration))
    for path, (source, mode, role) in declaration.items():
        spec = record['files'][path]
        account = identities[role]
        require(set(spec) == {'sha256', 'mode', 'uid', 'gid'} and spec['mode'] == mode
                and spec['uid'] == account.pw_uid and spec['gid'] == account.pw_gid)
        directory(g, str(Path(path).parent), account.pw_uid, account.pw_gid)
        regular(g, path, account.pw_uid, account.pw_gid, mode)
        require(g.checksum('sha256', path) == spec['sha256'])
        if isinstance(source, bytes):
            require(g.read_file(path) == source)
