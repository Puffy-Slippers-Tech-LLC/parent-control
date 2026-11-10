"""196a: Jordan and Riley independently save and reopen their own work."""
from installed_journey import InstalledJourney, JourneyPlan
from journey_blocks import fresh_desktop, prefixed_stages
from native_fixtures import fixture_actions
from private_artifacts import require
from synthetic_files import SyntheticFiles


def work_document_stages(who):
    """FILE08/09 and APP03/04 fragment; callers own entry and comparisons."""
    require(who in ('jordan', 'riley'), 'work:child')
    actions = ('open', 'opened', 'edit', 'save', 'saved', 'submit', 'submitted', 'capture',
               'reread', 'close', 'closed', 'reopen', 'reopened', 'reuse', 'reused',
               'recovered', 'finish', 'finished')
    operations = {'capture': 'activity', 'reread': 'activity', 'reopen': 'open',
                  'reopened': 'opened', 'reuse': 'submit', 'reused': 'submitted',
                  'recovered': 'activity', 'finish': 'close', 'finished': 'closed'}
    return {who + '-' + stage: 'ui:work-' + who + '-' + operations.get(stage, stage)
            for stage in actions}


SCREENS = {**fresh_desktop('parent'), 'logout': 'system:parent-logout',
           **prefixed_stages('jordan', fresh_desktop('other-child')),
           **work_document_stages('jordan'), 'jordan-logout': 'system:standard-logout',
           **prefixed_stages('riley', fresh_desktop('child')),
           **work_document_stages('riley'), 'cleanup': 'system:child-desktop-identity'}
PLAN = JourneyPlan(
    prefix='child-saved-work', worker_mode='child_saved_work', screen_tags=SCREENS,
    phases={'ready': 'setup', 'setup-detached': 'setup',
            **{stage: 'step-1' for stage in SCREENS}, 'installed-greeter': 'start'},
    stage_actions={'desktop': 'native-verify', 'logout': 'work-prepare', 'cleanup': 'work-cleanup',
                   **{who + '-saved': 'work-' + who + '-saved' for who in ('jordan', 'riley')}},
    invocations=tuple(stage for stage in SCREENS if stage in fresh_desktop('parent')
        or stage in prefixed_stages('jordan', fresh_desktop('other-child'))
        or stage in prefixed_stages('riley', fresh_desktop('child'))),
    challenges={'parent-login': ('parent', 'recipient-qualified', 'recipient-rechecked'),
        'work-jordan-login': ('other-child', 'jordan-standard-recipient-qualified',
                             'jordan-standard-recipient-rechecked'),
        'work-riley-login': ('child', 'riley-child-recipient-qualified',
                            'riley-child-recipient-rechecked')},
    activity_checks={who + '-' + stage: (who + '-capture', result)
                     for who in ('jordan', 'riley')
                     for stage, result in (('reread', 'same'), ('recovered', 'replaced'))},
)


def work_document_actions():
    def prepare(journey, guard):
        guard()
        require(not hasattr(journey, 'work_files'), 'work:replay')
        journey.work_files = {}
        for who in ('jordan', 'riley'):
            guard()
            files = SyntheticFiles(journey.transport, 'work-' + who)
            journey.work_files[who] = files
            files.call('stage')
        return {'both_documents_prepared': True}

    def saved(who):
        def read_saved(journey, guard):
            guard()
            files = journey.work_files[who]
            require(not files.failed, 'work:uncertain-files')
            files.call('saved')
            peer = journey.work_files['riley' if who == 'jordan' else 'jordan']
            require(peer._command('read', peer.previous) == peer.previous, 'work:peer-changed')
            return {'saved_bytes_matched': True, 'peer_unchanged': True}
        return read_saved

    def cleanup(journey, guard):
        for files in journey.work_files.values():
            guard()
            require(files._command('read', files.previous) == files.previous, 'work:final-content')
            files.call('cleanup')
        return {'owned_documents_removed': True}
    return {'work-prepare': prepare, 'work-cleanup': cleanup,
            **{'work-' + who + '-saved': saved(who) for who in ('jordan', 'riley')}}


class ChildSavedWorkJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, actions={
            **fixture_actions(include_refusal=False), **work_document_actions()})
