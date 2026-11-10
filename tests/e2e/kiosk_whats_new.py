"""Child release-note content and unchanged request qualification, not case 315.

The oracle reads the packaged source and installation range independently of
the displayed document. It never queries the broker's selected note record.
"""
from copy import deepcopy
import hashlib
import json
import re
import tomllib

import system_runner as system
from installed_journey import JourneyPlan
from journey_blocks import fresh_desktop, parent_management, prefixed_stages, station_entry
from private_artifacts import require
from request_composition import KioskRequestJourney
from request_flow import prepared_request


RETURN = prefixed_stages('verify', fresh_desktop('parent'))
SCREENS = {
    **fresh_desktop('parent'), **parent_management(),
    'wrong-owner': 'ui:parent-kiosk-whats-new-refused',
    'allowance-configured': 'ui:time-explanation-setup-zero-read',
    'policy-before': 'ui:retained-parent-read',
    'switch-user': 'system:parent-switch-user', 'gdm-switched': 'ui:gdm-returned',
    **station_entry(),
    **prepared_request(prefix='open', entry='open', initial='default',
                       child='fixture-child', approver='fixture-parent',
                       duration_seconds=75, allow_soft=True, compact=True),
    'notes-open': 'ui:kiosk-whats-new-open',
    'notes-read': 'ui:kiosk-whats-new-read',
    'notes-close': 'ui:kiosk-whats-new-close',
    'form-returned': 'ui:kiosk-valid-fraction-soft-read',
    'cancel': 'ui:kiosk-request-cancel', 'returned': 'ui:gdm-station-returned',
    **RETURN,
    'policy-after': 'ui:retained-parent-read',
    'balance-after': 'ui:time-explanation-read',
}
PLAN = JourneyPlan(
    prefix='kiosk-whats-new', worker_mode='kiosk_whats_new', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start',
            **{stage: 'step-2' for stage in tuple(SCREENS)[tuple(SCREENS).index('switch-user'):]}},
    advance_after={'policy-before': 'step-2'},
    balance_checks={'allowance-configured': 0, 'balance-after': 0},
    request_checks={'form-returned': ('open-estimate', 'kiosk-whats-new:changed-request',
                                     'unchanged_request')},
    invocations=tuple(RETURN),
    challenges={'verify': ('parent', 'verify-recipient-qualified', 'verify-recipient-rechecked')},
)


def version_key(value):
    require(type(value) is str and re.fullmatch(r'[0-9]+(?:\.[0-9]+){1,3}', value),
            'kiosk-whats-new:version')
    parts = [int(part) for part in value.split('.')]
    return tuple(parts + [0] * (4 - len(parts)))


def source_blocks(content):
    """Independent projection of the shipped English heading/bullet notes.

    Refuse other syntax rather than silently ignoring new content. This is
    finite qualification data, not a second general Markdown renderer.
    """
    blocks = []
    for line in content.splitlines():
        if not line.strip():
            continue
        require(line.startswith(('## ', '- ')), 'kiosk-whats-new:source-syntax')
        text = line[3:] if line.startswith('## ') else '•  ' + line[2:]
        blocks.append(text.replace('**', ''))
    require(blocks and sum(map(len, blocks)) > 80, 'kiosk-whats-new:empty-source')
    return blocks


class KioskWhatsNewJourney(KioskRequestJourney):
    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.policy_before = None

    def previous_version(self, current):
        """Engineering qualification independently checks installation history."""
        history = json.loads(self.transport.call(['cat',
            '/var/lib/oh-no-parent-control/whats-new-installation.json'], timeout=30))
        require(type(history) is dict and history.get('version') == 2
                and version_key(history['current_version']) == version_key(current)
                and version_key(history['first_version']) <= version_key(history['previous_version'])
                <= version_key(current), 'kiosk-whats-new:installation-range')
        return history['previous_version']

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        if stage in ('policy-before', 'policy-after'):
            key = ('language_policy' if self.plan.screen_tags[stage] == 'ui:overlay-language-policy'
                   else 'retained_parent')
            policy = observed['ui'][key]
        if stage == 'policy-before':
            self.policy_before = deepcopy(policy)
        elif stage == 'policy-after':
            require(policy == self.policy_before,
                    'kiosk-whats-new:changed-policy')
            observed.setdefault('comparison', {})['unchanged_saved_policy'] = True
        elif stage == 'notes-read':
            # Source and installed package bytes are already bound by the
            # snapshot/input guards. Check the specific content identity too.
            source = (system.ROOT / 'data/whats-new-child.toml').read_bytes()
            digest = hashlib.sha256(source).hexdigest()
            installed = self.transport.call(['sha256sum',
                '/usr/share/oh-no-parent-control/whats-new-child.toml'], timeout=30).decode()
            require(installed.split() == [digest,
                '/usr/share/oh-no-parent-control/whats-new-child.toml'],
                'kiosk-whats-new:installed-source')
            current = json.loads((system.ROOT / 'data/app.json').read_bytes())['version']
            previous_version = self.previous_version(current)
            previous = version_key(previous_version)
            require(previous == version_key('1.2') and version_key(current) == version_key('2.0'),
                    'kiosk-whats-new:qualification-upgrade-range')
            records = tomllib.loads(source.decode())['records']
            eligible = sorted((record for record in records if
                version_key(record['ProductVersion']) == version_key(current) or
                previous < version_key(record['ProductVersion']) < version_key(current)),
                key=lambda record: version_key(record['ProductVersion']))
            require(eligible, 'kiosk-whats-new:no-eligible-content')
            require([record['ProductVersion'] for record in eligible] == ['1.4'],
                    'kiosk-whats-new:qualification-release')
            combined = len(eligible) > 1 or version_key(eligible[0]['ProductVersion']) != version_key(current)
            expected = []
            for record in eligible:
                if combined:
                    if expected:
                        expected.append('')
                    expected.append('v' + record['ProductVersion'])
                expected.extend(source_blocks(record['Content']))
            value = observed['ui']['whats_new']
            require(value == {'title': "What's New in v" + current, 'blocks': expected},
                    'kiosk-whats-new:displayed-child-content')
            observed['comparison'] = {'audience': 'Child', 'product_version': current,
                'previous_version': previous_version, 'source_sha256': digest,
                'releases': [record['ProductVersion'] for record in eligible],
                'installed_content_matches': True}
