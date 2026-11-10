"""FLOW19: explicit finite policy preparation, saved rows and retained entry."""
from accessible_ui import MATCH_APPS, MATCH_RULES, NAMED_CHILD_OPERATIONS
from feedback_composition import text_fragment
from installed_journey import JourneyPlan
from journey_blocks import (desktop_entry, fresh_desktop, parent_management,
                            prefixed_stages, retained_parent_entry)
from journey_checks import RetainedDesktopJourney
from native_fixtures import fixture_actions
from policy_edits import AppPolicyJourney, policy_edit
from private_artifacts import require


def saved_rows(apps, prefix):
    """Read every declared match and access after the final save, without edits."""
    screens = {}
    for app, _draft, _access in apps:
        role = next(role for role, identity in MATCH_APPS.items() if identity == app)
        name = {'A': '', 'H': 'hard-', 'S': 'soft-', 'Alias': 'alias-', 'Game': 'game-'}[role]
        screens[prefix + '-' + role.lower() + '-match'] = 'ui:match-' + name + 'row'
        screens[prefix + '-' + role.lower() + '-access'] = 'ui:access-' + name + 'row'
    return screens


def named_app_set(*, source, entry, window, child, apps, prefix):
    """FLOW01 → App Limits → finite setup edits → full saved set → DESK03.

    The caller supplies its current session/window ledger and compares retained
    entry before input. No allowance, approval, app launch or hidden child entry.
    """
    require(child in ('child', 'existing') and type(apps) is tuple and 0 < len(apps) <= 4
            and all(type(app) is tuple and len(app) == 3 for app in apps)
            and len({app[0] for app in apps}) == len(apps), 'app-set:apps')
    require((source, entry, window) in (
        ('gdm', 'fresh', 'new'), ('desktop', 'same-user', 'retained')), 'app-set:entry')
    # Validate all finite edits before returning an executable composition.
    edits = {}
    for index, (app, draft, access) in enumerate(apps):
        edits.update(policy_edit(app, draft, access, 'edit-' + str(index), setup=True))
    initial = ({**fresh_desktop('parent'), **parent_management(child=child)}
               if entry == 'fresh' else {})
    retained = (prefixed_stages('entry', retained_parent_entry(source='same-user'))
                if entry == 'same-user' else {})
    return {**initial, **prefixed_stages(prefix, {
        **retained, 'apps-page': 'ui:parent-apps-page' if child == 'child' else 'ui:existing-apps', **edits,
        **text_fragment('catalogue-clear', 'clear'),
        **saved_rows(apps, 'saved'),
        'before': 'ui:retained-parent-leave',
        'session': 'system:parent-desktop-identity',
        'repeat-desktop': 'ui:desktop', 'switch-user': 'system:parent-switch-user',
        'gdm-switched': 'ui:gdm-returned',
    })}


APPS = ((MATCH_APPS['A'], 'match-precise', 'allowed'),
        (MATCH_APPS['H'], 'match-hard-precise', 'permanent'),
        (MATCH_APPS['S'], 'match-soft-wildcard', 'conditional'))
SMALLER = ((MATCH_APPS['A'], 'match-precise', 'conditional'),
           (MATCH_APPS['S'], 'match-soft-precise', 'allowed'))
FIRST = named_app_set(source='gdm', entry='fresh', window='new', child='child',
                      apps=APPS, prefix='first')
RETURN = prefixed_stages('return', desktop_entry('parent', source='gdm', entry='retained'))
FINAL_RETURN = prefixed_stages('final-return', desktop_entry('parent', source='gdm', entry='retained'))
SCREENS = {
    **FIRST, **RETURN,
    'returned-session': 'system:parent-desktop-identity',
    **prefixed_stages('returned', retained_parent_entry(source='same-user')),
    'returned-apps': 'ui:parent-apps-page', **saved_rows(APPS, 'returned'),
    **named_app_set(source='desktop', entry='same-user', window='retained', child='child',
                    apps=SMALLER, prefix='smaller'),
    **FINAL_RETURN,
    'final-session': 'system:parent-desktop-identity',
    **prefixed_stages('final', retained_parent_entry(source='same-user')),
    'final-apps': 'ui:parent-apps-page', **saved_rows(SMALLER, 'final'),
}
_logins = set(RETURN) | set(FINAL_RETURN)
_matches, _accesses = {}, {}
_rules = {'match-precise': MATCH_RULES[0], 'match-hard-precise': MATCH_RULES[3],
          'match-soft-wildcard': MATCH_RULES[4], 'match-soft-precise': MATCH_RULES[5]}
for prefix, apps in (('first-saved', APPS), ('returned', APPS),
                     ('smaller-saved', SMALLER), ('final', SMALLER)):
    for app, draft, access in apps:
        role = next(role for role, identity in MATCH_APPS.items() if identity == app).lower()
        _matches[prefix + '-' + role + '-match'] = (app, _rules[draft])
        _accesses[prefix + '-' + role + '-access'] = (app, access)
PLAN = JourneyPlan(
    prefix='named-app-set', worker_mode='named_app_set', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'installed-greeter': 'native-refuse', 'desktop': 'native-verify'},
    child_bindings={stage: 'child' for stage, tag in SCREENS.items()
                    if tag.startswith('ui:') and tag[3:] in NAMED_CHILD_OPERATIONS},
    match_checks=_matches, access_checks=_accesses,
    invocations=tuple(stage for stage in SCREENS if stage in _logins and SCREENS[stage].startswith('ui:')),
    challenges={prefix: ('parent', prefix + '-recipient-qualified', prefix + '-recipient-rechecked')
                for prefix in ('return', 'final-return')},
    assertions_after={'first-saved-s-access': 'complete-named-set-saved',
        'returned-s-access': 'every-rule-preserved-on-return',
        'smaller-saved-s-access': 'independent-smaller-set-saved',
        'final-s-access': 'smaller-set-preserved-on-return'},
)


class NamedAppSetJourney(RetainedDesktopJourney, AppPolicyJourney):
    """Reuse the existing saved-rule and retained-window/session comparisons."""

    def __init__(self, context, progress, plan=PLAN, *, actions=None):
        super().__init__(context, progress, plan,
            actions=fixture_actions() if actions is None else actions,
            parent_expected={stage: {'page': 'app-limits', 'settings': {
                'child': 'fixture-child', 'limit_enabled': False, 'allowance': ['0 minutes']}}
                for stage in ('first-before', 'smaller-before')},
            parent_checks={'returned-parent-retained': 'first-before',
                           'smaller-entry-parent-retained': 'first-before',
                           'final-parent-retained': 'smaller-before'},
            window_checks={}, session_checks={stage: 'first-session' for stage in
                ('returned-session', 'smaller-session', 'final-session')})
