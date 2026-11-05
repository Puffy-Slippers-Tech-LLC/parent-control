"""FIX06: verify the captured Snap profile without installation or repair."""
import hashlib
import inspect
import json
from pathlib import Path

from private_artifacts import require
from watch_activity import operation
from installed_journey import InstalledJourney
from journey_checks import allowed_app_rows
from native_fixture_qualification import PLAN
import session_control
import prepare_vm
from tests.fixtures import snap_assets


def guest_read(action, source):
    import grp
    import os
    import pwd
    import json
    from pathlib import Path
    import session_control
    import baseline_snap_fixtures as fixtures
    require = session_control.require
    require(os.geteuid() == 0 and action in ('read', 'refuse'), 'snap-authority')
    parent = pwd.getpwnam(session_control.ACCOUNTS['parent'])
    require(parent.pw_uid >= 1000 and grp.getgrnam(session_control.administrator_group()).gr_gid
            in os.getgrouplist(parent.pw_name, parent.pw_gid), 'snap-administrator')
    sessions = session_control.sessions()
    if action == 'refuse':
        try:
            session_control.source_session(sessions, parent.pw_uid)
        except session_control.SessionError:
            return {'wrong_entry_refused': True}
        require(False, 'snap-refusal-entry')
    recipient = session_control.source_session(sessions, parent.pw_uid)
    marker = json.loads(fixtures.read(Path('/etc/oh-no-parent-control-test-baseline.json')))
    require(marker['preparation_script_sha256'] == source, 'snap-stale-baseline')
    saved = fixtures.record()
    value = fixtures.verify(saved['files'], source=source)
    require(session_control.source_session(session_control.sessions(), parent.pw_uid) == recipient,
            'snap-recipient-changed')
    return value


def guest_source():
    root = Path(__file__).resolve().parents[2]
    source = 'import sys, types, json\n'
    for package in ('tests', 'tests.fixtures'):
        source += (f'm = types.ModuleType({package!r}); m.__path__ = []; '
                   f'sys.modules[{package!r}] = m\n')
    modules = {
        'tests.fixtures.snap_assets': root / 'tests/fixtures/snap_assets.py',
        'baseline_snap_fixtures': root / 'tests/integration/baseline_snaps.py',
        'session_control': Path(session_control.__file__),
    }
    for name, path in modules.items():
        source += (f'm = types.ModuleType({name!r}); sys.modules[{name!r}] = m\n'
                   f'exec({path.read_text()!r}, m.__dict__)\n')
    return (source + inspect.getsource(guest_read) +
        '\nprint(json.dumps(guest_read(sys.argv[1], sys.argv[2]), sort_keys=True))\n').encode()


class SnapFixtures:
    def __init__(self, transport, verified):
        self.transport, self.verified = transport, verified
        self.identity = dict(transport.config)
        self.used = False

    def read(self, action):
        require(self.transport.config == self.identity, 'snap:wrong-attempt')
        self.transport.guard(self.identity)
        self.verified.recheck()
        raw = self.transport.call(['/usr/bin/python3', '-I', '-', action,
            prepare_vm.preparation_digest()], input=guest_source(), timeout=180)
        require(type(raw) is bytes and 0 < len(raw) <= 16384, 'snap:response-bound')
        value = json.loads(raw)
        require(raw == (json.dumps(value, sort_keys=True) + '\n').encode(), 'snap:response')
        self.transport.guard(self.identity)
        self.verified.recheck()
        return value

    def refuse(self):
        with operation('Checking Snap fixture refusal outside the parent desktop'):
            value = self.read('refuse')
            require(value == {'wrong_entry_refused': True}, 'snap:refusal')
            return value

    def verify(self):
        require(not self.used, 'snap:replay')
        self.used = True
        with operation('Reading the installed Snap apps, their confinement and launcher identities'):
            first = self.read('read')
            require(set(first) == {snap_assets.BASE, *(name for _, name, _ in snap_assets.ASSETS)}
                    and self.read('read') == first, 'snap:independent-readback')
            return {'installed_apps': 3, 'independent_readback': True, 'scope': 'system',
                    'confinement': 'strict', 'installed': first}


def fixture_actions(*, include_refusal=True):
    require(type(include_refusal) is bool, 'snap:action-binding')
    def controller(journey):
        if not hasattr(journey, 'snap_fixtures'):
            journey.snap_fixtures = SnapFixtures(journey.transport, journey.context.verified)
        return journey.snap_fixtures

    def refuse(journey, guard):
        guard()
        return controller(journey).refuse()

    def verify(journey, guard):
        guard()
        return controller(journey).verify()

    return ({'native-refuse': refuse, 'native-verify': verify} if include_refusal
            else {'native-verify': verify})


class SnapFixtureJourney(InstalledJourney):
    """Reuse the qualified Parent row-reading composition, with Snap assertions."""
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions=fixture_actions())
        self.initial_rows = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage not in ('app-rows', 'reopened-rows'):
            return
        rows = allowed_app_rows(self, observed)
        expected = tuple(sorted(('parent-app-' + hashlib.sha256(
            snap_assets.desktop_id(name).encode()).hexdigest()[:16], 'allowed', 'precise')
            for _, name, _ in snap_assets.ASSETS))
        actual = tuple(row for row in rows.rows if row[0] in {item[0] for item in expected})
        require(actual == expected, 'snap:catalogue-defaults')
        if stage == 'app-rows':
            self.initial_rows = rows
        else:
            require(self.initial_rows == rows, 'snap:independent-catalogue')
        observed['comparison'].update(declared_snap_launchers=3, allowed_defaults=True,
                                      default_matches=True)
