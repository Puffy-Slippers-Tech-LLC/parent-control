"""Read-only verification of native fixtures prepared by prepare-baseline."""
import hashlib
import json
from pathlib import Path
import sys

from private_artifacts import require
from watch_activity import operation
from installed_journey import InstalledJourney
from journey_checks import check_balances
from ui_observations import AppRowsObservation

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


# Finite public search inputs; expected identities are independent of UI output.
CATALOGUE_QUERIES = {
    'catalogue-name': ASSETS[0][2],
    'catalogue-description': ASSETS[0][3],
    'catalogue-identifier': desktop_id('A'),
    'catalogue-absent': 'ONPC Absent Catalogue Fixture 077b',
    'catalogue-clear': '',
}


def search_rows(binding):
    require(binding in CATALOGUE_QUERIES and binding != 'catalogue-clear',
            'catalogue:binding')
    return (() if binding == 'catalogue-absent' else
            tuple(row for row in expected_rows() if row[0] == 'parent-app-' +
                  hashlib.sha256(desktop_id('A').encode()).hexdigest()[:16]))


def catalogue_rows(binding, rows, *, match_mask=3, access_mask=7):
    """Finite independent oracle shared by the host matrix and installed sample."""
    require(binding in CATALOGUE_QUERIES and type(match_mask) is int
            and 0 <= match_mask < 4 and type(access_mask) is int
            and 0 <= access_mask < 8, 'catalogue:binding')
    matches = tuple(value for index, value in enumerate(('pattern', 'precise'))
                    if match_mask & (1 << index))
    accesses = tuple(value for index, value in enumerate(('allowed', 'conditional', 'permanent'))
                     if access_mask & (1 << index))
    query_ids = {row[0] for row in search_rows(binding)} if binding != 'catalogue-clear' else None
    return tuple(row for row in rows if (query_ids is None or row[0] in query_ids)
                 and row[1] in accesses and row[2] in matches)


def check_catalogue(rows):
    """Require all declared public row identities/defaults; stock rows remain allowed."""
    expected = expected_rows()
    selected = tuple(row for row in rows.rows if row[0] in {item[0] for item in expected})
    if selected != expected:
        # The failing stage is not persisted by InstalledJourney. Retain only
        # declared fixture IDs and closed choice enums in the runner's stderr.
        actual = {row[0]: row[1:] for row in selected}
        diagnostic = {'row_count': len(rows.rows), 'fixtures': []}
        for identity, access, match in expected:
            value = actual.get(identity)
            diagnostic['fixtures'].append({
                'id': identity, 'present': value is not None,
                'expected': [access, match],
                'actual': None if value is None else [
                    value[0] if value[0] in ('allowed', 'conditional', 'permanent') else 'invalid',
                    value[1] if value[1] in ('pattern', 'precise') else 'invalid'],
            })
        print('native:catalogue-diagnostic=' + json.dumps(diagnostic, sort_keys=True),
              file=sys.stderr, flush=True)
    require(selected == expected, 'native:catalogue-defaults')
    return {'declared_launchers': 4, 'allowed_defaults': True, 'default_matches': True}


class CataloguePolicyJourney(InstalledJourney):
    """Caller-declared exact query intersections and unchanged-policy endpoints.

    JourneyPlan.catalogue_checks values are 'initial', 'unchanged', or
    (query, match mask, access mask).
    This owns comparisons only; the caller owns entry, order and fixture actions.
    """
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        row_checks = plan.catalogue_checks
        require(set(row_checks) <= set(plan.screen_tags)
                and list(row_checks.values()).count('initial') == 1,
                'catalogue:comparison-plan')
        for check in row_checks.values():
            require(check in ('initial', 'unchanged') or type(check) is tuple
                    and len(check) == 3, 'catalogue:comparison-plan')
            if type(check) is tuple:
                catalogue_rows(check[0], (), match_mask=check[1], access_mask=check[2])
        stages = list(plan.screen_tags)
        initial = next(stage for stage, check in row_checks.items() if check == 'initial')
        require(all(stage == initial or stages.index(initial) < stages.index(stage)
                    for stage in row_checks), 'catalogue:comparison-order')
        self.row_checks = dict(row_checks)
        self.initial_rows = None
        self.compared_rows = set()

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in self.plan.balance_checks:
            check_balances(self, observed, self.plan.balance_checks[stage])
        if stage not in self.row_checks:
            return
        require(stage not in self.compared_rows, 'catalogue:comparison-replay')
        rows = AppRowsObservation.from_rows(observed['ui']['apps']['rows'])
        check = self.row_checks[stage]
        if check == 'initial':
            require(self.initial_rows is None, 'catalogue:initial-replay')
            observed['comparison'] = check_catalogue(rows)
            self.initial_rows = rows
        else:
            require(self.initial_rows is not None, 'catalogue:missing-initial')
            expected = (self.initial_rows.rows if check == 'unchanged' else
                        catalogue_rows(check[0], self.initial_rows.rows,
                                       match_mask=check[1], access_mask=check[2]))
            require(rows.rows == expected, 'catalogue:unchanged-policies' if
                    check == 'unchanged' else 'catalogue:exact-results')
            observed['comparison'] = ({'unchanged_access_and_match': True} if
                check == 'unchanged' else {'exact_query_intersection': True})
        observed['comparison']['row_count'] = len(rows.rows)
        observed['comparison']['complete_catalogue_result'] = True
        self.compared_rows.add(stage)
