"""035d: child-owned identical executable copy and independent Allowed use."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require
from synthetic_files import SyntheticFiles


SCREENS = {
    **fresh_desktop('parent'),
    'logout': 'system:parent-logout',
    **prefixed_stages('child', fresh_desktop('other-child')),
}
for entry in ('first', 'independent'):
    SCREENS.update({
        entry + '-copy': 'ui:standard-desktop',
        **prefixed_stages(entry + '-app', {
            **native_usable_app('command', role='SpaceCopy'),
            'close': 'ui:native-space-copy-close', 'closed': 'ui:native-space-copy-closed'}),
        entry + '-cleanup': 'ui:standard-desktop',
    })
SCREENS['child-logout'] = 'system:standard-logout'
PLAN = JourneyPlan(
    prefix='native-space-path', worker_mode='native_space_path', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify',
                   **{entry + '-copy': 'space-copy' for entry in ('first', 'independent')},
                   **{entry + '-cleanup': 'space-cleanup' for entry in ('first', 'independent')}},
    invocations=tuple(stage for stage in SCREENS
                      if stage in fresh_desktop('parent') or stage.startswith('child-')
                      and stage != 'child-logout'),
    challenges={
        'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                               'child-standard-recipient-rechecked')},
    assertions_after={entry + '-cleanup': entry + '-identical-copy-usable-and-cleaned'
                      for entry in ('first', 'independent')},
)


def copy_actions():
    """The same finite FILE05 operation is available to the later policy case."""
    def copy(journey, guard):
        guard()
        require(not hasattr(journey, 'space_files'), 'files:copy-replay')
        files = journey.native_fixtures.receipt['files']
        prefix = 'fixtures/image-root/opt/onpc-test-fixtures/Applications/'
        journey.space_files = SyntheticFiles(journey.transport, 'native-space', expected={
            'source': files[prefix + 'Whitespace/Path With Spaces.AppImage']['sha256'],
            'nonmatching': files[prefix + 'PrismLauncher.AppImage']['sha256']})
        before = journey.space_files.call('stage')
        copied = journey.space_files.call('copy')
        source, destination = 'Path With Spaces.AppImage', 'Copied Path With Spaces.AppImage'
        require(set(copied['files']) == {source, destination}
                and copied['directory'] == before['directory']
                and copied['files'][source] == before['files'][source]
                and copied['files'][source]['sha256'] == copied['files'][destination]['sha256']
                and copied['files'][source]['identity'] != copied['files'][destination]['identity']
                and copied['destination'] == '/opt/onpc-test-fixtures/Applications/Whitespace/' + destination,
                'files:executable-copy-result')
        return copied

    def cleanup(journey, guard):
        guard()
        result = journey.space_files.call('cleanup')
        del journey.space_files
        return result

    return {'space-copy': copy, 'space-cleanup': cleanup}


class NativeSpacePathJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **copy_actions()})
