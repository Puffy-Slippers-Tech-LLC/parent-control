"""Finite special-path copies using the same FILE05 and Allowed-use operations."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, native_usable_app, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require
from synthetic_files import SyntheticFiles


def special_path_plan(profile):
    require(profile in ('space', 'comma'), 'files:profile')
    entries = ('first', 'independent') if profile == 'space' else ('first',)
    screens = {
        **fresh_desktop('parent'),
        'logout': 'system:parent-logout',
        **prefixed_stages('child', fresh_desktop('other-child')),
    }
    for entry in entries:
        screens.update({
            entry + '-copy': 'ui:standard-desktop',
            **prefixed_stages(entry + '-app', {
                **native_usable_app('command', role='SpaceCopy' if profile == 'space' else 'CommaCopy'),
                'close': 'ui:native-' + profile + '-copy-close',
                'closed': 'ui:native-' + profile + '-copy-closed'}),
            entry + '-cleanup': 'ui:standard-desktop',
        })
    screens['child-logout'] = 'system:standard-logout'
    return JourneyPlan(
        prefix='native-' + profile + '-path', worker_mode='native_' + profile + '_path', screen_tags=screens,
        phases={'ready': 'setup', 'setup-detached': 'setup',
                **{stage: 'step-1' for stage in screens}, 'installed-greeter': 'start'},
        stage_actions={'desktop': 'native-verify',
                       **{entry + '-copy': profile + '-copy' for entry in entries},
                       **{entry + '-cleanup': profile + '-cleanup' for entry in entries}},
        invocations=tuple(stage for stage in screens
                          if stage in fresh_desktop('parent') or stage.startswith('child-')
                          and stage != 'child-logout'),
        challenges={
            'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
            'native-child-login': ('other-child', 'child-standard-recipient-qualified',
                                   'child-standard-recipient-rechecked')},
        assertions_after={entry + '-cleanup': entry + '-identical-copy-usable-and-cleaned'
                          for entry in entries},
    )


PLAN = special_path_plan('space')
COMMA_PLAN = special_path_plan('comma')


def copy_actions(profile='space'):
    """The same finite FILE05 operation is available to the later policy case."""
    require(profile in ('space', 'comma'), 'files:profile')
    attribute = profile + '_files'
    directory, source, destination = (
        ('Whitespace', 'Path With Spaces.AppImage', 'Copied Path With Spaces.AppImage')
        if profile == 'space' else
        ('Comma', 'Path,With,Commas.AppImage', 'Copied,Path,With,Commas.AppImage'))
    def copy(journey, guard):
        guard()
        require(not hasattr(journey, attribute), 'files:copy-replay')
        files = journey.native_fixtures.receipt['files']
        prefix = 'fixtures/image-root/opt/onpc-test-fixtures/Applications/'
        controller = SyntheticFiles(journey.transport, 'native-' + profile, expected={
            'source': files[prefix + directory + '/' + source]['sha256'],
            'nonmatching': files[prefix + 'PrismLauncher.AppImage']['sha256']})
        setattr(journey, attribute, controller)
        return controller.copy_executable(source=source,
            destination='/opt/onpc-test-fixtures/Applications/' + directory + '/' + destination)

    def cleanup(journey, guard):
        guard()
        result = getattr(journey, attribute).call('cleanup')
        delattr(journey, attribute)
        return result

    return {profile + '-copy': copy, profile + '-cleanup': cleanup}


class NativeSpacePathJourney(InstalledJourney):
    def __init__(self, context, progress, *, profile='space'):
        require(profile in ('space', 'comma'), 'files:profile')
        super().__init__(context, progress, PLAN if profile == 'space' else COMMA_PLAN, actions={
            **fixture_actions(include_refusal=False), **copy_actions(profile)})
