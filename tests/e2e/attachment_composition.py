"""Shared attachment declarations and independent public-list comparisons.

Recipes select batches and order; these helpers own handoff stages and immutable
preview/rejection comparisons. Invocation names may differ from operation names.
"""
from installed_journey import InstalledJourney
from private_artifacts import require


def formatted_draft_expected(*, reset=False):
    from feedback_formats import expected
    return {'draft': 'initial-empty' if reset else 'formatted-file',
            'attachments': ['diagnostic-logs.zip', *([] if reset else ['Synthetic note.txt'])],
            'collection': 'ready', 'validation': 'none', 'controls': 'ready',
            'items': [] if reset else [['Synthetic note.txt', '26 bytes']],
            'formats': ({'blocks': [], 'inline': [], 'link': None,
                         'normal_comparison': True, 'text_exact': True} if reset else
                        expected('formats-kept-reopen'))}


def compare_formatted_draft(value, *, reset=False):
    require(value == formatted_draft_expected(reset=reset), 'feedback:formatted-draft')
    return value


def file_handoff(prefix='chooser'):
    return {f'{prefix}-{step}': f'ui:{prefix}-{step}'
            for step in ('open', 'location', 'files', 'accept')}


def boundary_batch(batch):
    require(batch in ('count', 'sixth', 'maximum', 'oversized', 'total', 'overflow'),
            'attachment:batch')
    prefix = 'boundary-' + batch
    return {prefix + '-before': 'ui:' + prefix + '-before',
            **file_handoff(prefix),
            **{prefix + '-' + step: 'ui:' + prefix + '-' + step
               for step in ('result', 'preserved')}}


class AttachmentJourney(InstalledJourney):
    """FEED12 unchanged preview and FEED06 rejected-file preservation checks."""
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.before_preview = None
        self.boundary_before = {}

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        if operation in ('attachment-details', 'attachment-preview', 'attachment-preview-return'):
            current = tuple(tuple(item) for item in observed['ui']['attachment']['items'])
            if operation == 'attachment-details':
                require(self.before_preview is None, 'attachment:preview-replay')
                self.before_preview = current
            else:
                require(self.before_preview is not None and current == self.before_preview,
                        'attachment:preview-list-changed')
        if not operation.startswith('boundary-') or not operation.endswith(('-before', '-result', '-preserved')):
            return
        _, batch, step = operation.split('-')
        value = observed['ui']['boundary']
        current = (tuple(tuple(item) for item in value['items']), value['include_logs'])
        if step == 'before':
            require(batch not in self.boundary_before, 'attachment:boundary-replay')
            self.boundary_before[batch] = current
        elif batch in ('sixth', 'oversized', 'overflow'):
            require(batch in self.boundary_before and current == self.boundary_before[batch],
                    'attachment:rejection-list-changed')
