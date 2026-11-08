"""Finite FILE05 copies and Allowed use needed by the later pattern-rule case."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require
from synthetic_files import SyntheticFiles
from tests.fixtures.native_assets import NEXT_VERSION


def versioned_copy_actions(*, administrative=False):
    """Separate additions let case 189 own their policy/refresh ordering."""
    def copy(journey, guard, binding):
        guard()
        attribute = 'version_' + binding + '_files'
        require(not hasattr(journey, attribute), 'files:copy-replay')
        prefix = 'fixtures/image-root/opt/onpc-test-fixtures/Applications/'
        source, destination, other = (
            (NEXT_VERSION, 'Lunar Client-3.8.0.AppImage', 'Versioned/PrismLauncher.AppImage')
            if binding == 'next' else
            ('Versioned/PrismLauncher.AppImage', 'NewPrismLauncher.AppImage', NEXT_VERSION))
        hashes = journey.native_fixtures.receipt['files']
        controller = SyntheticFiles(journey.transport, 'native-version-' + binding,
            administrative=administrative, expected={
            'source': hashes[prefix + source]['sha256'],
            'nonmatching': hashes[prefix + other]['sha256']})
        setattr(journey, attribute, controller)
        source_key = '../' + source if binding == 'next' else 'PrismLauncher.AppImage'
        return controller.copy_executable(source=source_key,
            destination='/opt/onpc-test-fixtures/Applications/Versioned/' + destination)

    def cleanup(journey, guard):
        guard()
        results = {}
        for binding in ('next', 'nonmatch'):
            attribute = 'version_' + binding + '_files'
            results[binding] = getattr(journey, attribute).call('cleanup')
            delattr(journey, attribute)
        return results

    return {'version-next-copy': lambda journey, guard: copy(journey, guard, 'next'),
            'version-nonmatch-copy': lambda journey, guard: copy(journey, guard, 'nonmatch'),
            'version-cleanup': cleanup}


SCREENS = {**fresh_desktop('parent'), 'logout': 'system:parent-logout',
           **prefixed_stages('child', fresh_desktop('other-child'))}
for entry in ('first', 'independent'):
    SCREENS.update({entry + '-next-copy': 'ui:standard-desktop',
                    entry + '-nonmatch-copy': 'ui:standard-desktop'})
    for name, role in (('next', 'VersionNext'), ('existing', 'VersionExisting'), ('nonmatch', 'VersionNonmatch')):
        SCREENS.update(prefixed_stages(entry + '-' + name, {
            **native_usable_app('command', role=role),
            'close': 'ui:native-version-' + name + '-close',
            'closed': 'ui:native-version-' + name + '-closed'}))
    SCREENS[entry + '-cleanup'] = 'ui:standard-desktop'
SCREENS['child-logout'] = 'system:standard-logout'

PLAN = JourneyPlan(
    prefix='versioned-appimage-assets', worker_mode='versioned_appimage_assets', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify',
                   **{entry + '-' + name + '-copy': ('admin-' if entry == 'independent' else '') + 'version-' + name + '-copy'
                      for entry in ('first', 'independent') for name in ('next', 'nonmatch')},
                   **{entry + '-cleanup': 'version-cleanup' for entry in ('first', 'independent')}},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
                      or stage.startswith('child-') and stage != 'child-logout'),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
                'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                                       'child-standard-recipient-rechecked')},
    assertions_after={entry + '-cleanup': entry + '-copies-usable-and-cleaned'
                      for entry in ('first', 'independent')})


class VersionedAppImageAssetsJourney(InstalledJourney):
    def __init__(self, context, progress, plan=PLAN):
        require(plan is PLAN, 'versioned-appimage-assets:plan-binding')
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **versioned_copy_actions(),
            **{'admin-' + name: action for name, action in
               versioned_copy_actions(administrative=True).items() if name != 'version-cleanup'}})
