"""Read-only verification of native fixtures prepared by prepare-baseline."""
import hashlib
import json
from pathlib import Path
import sys

from private_artifacts import require
from watch_activity import operation

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from tests.fixtures.native_assets import ASSETS, desktop_id, sources


def guest_source():
    modules = {
        'guest_files': Path(__file__).with_name('guest_files.py'),
        'native_assets': ROOT / 'tests/fixtures/native_assets.py',
        'session_control': Path(__file__).with_name('session_control.py'),
    }
    source = 'import sys, types\n'
    for name, path in modules.items():
        source += (f'{name} = types.ModuleType({name!r})\nsys.modules[{name!r}] = {name}\n'
                   f'exec({path.read_text()!r}, {name}.__dict__)\n')
    # Program comes over stdin; request is a finite argument decoded into a BytesIO.
    source += ('import io\nrequest = sys.argv.pop()\n'
               'sys.stdin = io.TextIOWrapper(io.BytesIO(request.encode()))\n')
    return source.encode() + Path(__file__).with_name('native_fixtures_guest.py').read_bytes()


class NativeFixtures:
    def __init__(self, transport, verified):
        self.transport, self.verified = transport, verified
        self.attempt = dict(transport.config)
        self.attempted = False
        self.failed = False
        self.receipt = None

    def command(self, action):
        require(self.transport.config == self.attempt, 'native:wrong-attempt')
        self.transport.guard(self.attempt)
        self.verified.recheck()
        expected = {name: self.verified.asset_files[name] for name in sources()}
        require(len({expected[name] for name in sources()[:4]}) == 4, 'native:identical-roles')
        raw = self.transport.call(['/usr/bin/python3', '-I', '-', action,
                                   json.dumps(expected, sort_keys=True)],
                                  input=guest_source(), timeout=90)
        require(type(raw) is bytes and 0 < len(raw) <= 8192, 'native:response-bound')
        value = json.loads(raw)
        require(type(value) is dict and raw == (json.dumps(value, sort_keys=True) + '\n').encode(),
                'native:response-schema')
        self.verified.recheck()
        return value

    def refuse(self):
        require(not self.attempted and not self.failed, 'native:refusal-entry')
        with operation('Checking native fixture refusal outside the administrator desktop'):
            require(self.command('refuse') == {'wrong_entry_refused': True}, 'native:wrong-refusal')
        return {'wrong_entry_refused': True}

    def verify(self):
        require(not self.attempted and not self.failed, 'native:replay')
        self.attempted = self.failed = True
        with operation('Verifying four baseline native launchers for [Child user]'):
            value = self.command('read')
            require(set(value) == {'files', 'launchers'} and set(value['files']) == set(sources())
                    and value['launchers'] == [desktop_id(asset[0]) for asset in ASSETS],
                    'native:receipt')
            require(self.command('read') == value, 'native:independent-readback')
            self.receipt = value
        self.failed = False
        return {'verified': 4, 'verified_files': len(value['files']), 'independent_readback': True}


def fixture_actions():
    """Fresh lifetime owner for an independent caller's guarded attempt."""
    def controller(journey):
        if not hasattr(journey, 'native_fixtures'):
            journey.native_fixtures = NativeFixtures(journey.transport, journey.context.verified)
        return journey.native_fixtures

    def refuse(journey, guard):
        guard()
        return controller(journey).refuse()

    def verify(journey, guard):
        guard()
        return controller(journey).verify()

    return {'native-refuse': refuse, 'native-verify': verify}


def expected_rows():
    return tuple(sorted(('parent-app-' + hashlib.sha256(desktop_id(asset[0]).encode()).hexdigest()[:16],
                         'allowed', asset[4]) for asset in ASSETS))


def check_catalogue(rows):
    """Require all declared public row identities/defaults; stock rows remain allowed."""
    expected = expected_rows()
    selected = tuple(row for row in rows.rows if row[0] in {item[0] for item in expected})
    require(selected == expected, 'native:catalogue-defaults')
    return {'declared_launchers': 4, 'allowed_defaults': True, 'default_matches': True}
