"""Shared attachment declarations and independent public-list comparisons.

Recipes select batches and order; these helpers own handoff stages and immutable
preview/rejection comparisons. Invocation names may differ from operation names.
"""
from window_switch import WindowSwitchJourney
from private_artifacts import require
from copy import deepcopy
import re


def formatted_draft_expected(*, reset=False):
    return {'draft': 'initial-empty' if reset else 'formatted-file',
            'attachments': ['diagnostic-logs.zip', *([] if reset else ['Synthetic note.txt'])],
            'collection': 'ready', 'validation': 'none', 'controls': 'ready',
            'items': [] if reset else [['Synthetic note.txt', '26 bytes']],
            'formats': ({'blocks': [], 'inline': [], 'link': None,
                         'normal_comparison': True, 'text_exact': True} if reset else
                        {'blocks': [], 'inline': ['bold'], 'link': None,
                         'normal_comparison': True, 'text_exact': True})}


def compare_formatted_draft(value, *, reset=False):
    require(value == formatted_draft_expected(reset=reset), 'feedback:formatted-draft')
    return deepcopy(value)


def save_handoff(prefix):
    """FILE03 Save only; callers own preparation, readback and later Cancel."""
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'save:invocation')
    return {prefix + '-' + step: 'ui:save-chooser-' + step for step in (
        'open', 'name', 'location', 'navigated', 'destination', 'restored', 'accept', 'result')}


def save_cancellation(prefix):
    """Fresh chooser Cancel with independently unchanged saved output."""
    require(type(prefix) is str and re.fullmatch(r'[a-z][a-z0-9-]*', prefix),
            'save:invocation')
    return {prefix + '-' + step: 'ui:save-chooser-' + step for step in (
        'reopen', 'cancel-name', 'cancel', 'preserved')}


def file_handoff(prefix='chooser'):
    return {f'{prefix}-{step}': f'ui:{prefix}-{step}'
            for step in ('open', 'location', 'files', 'accept')}


def chooser_preservation(invocation=''):
    """Read accepted files, reopen/Cancel, then independently read preservation."""
    require(type(invocation) is str and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', invocation),
            'chooser:invocation')
    return {invocation + 'chooser-' + step: 'ui:chooser-' + step
            for step in ('attachments', 'reopen', 'cancel', 'preserved')}


def attachment_removal(invocation=''):
    """Remove the declared owned row and independently read the remaining list."""
    require(type(invocation) is str and re.fullmatch(r'(?:[a-z][a-z0-9-]*-)?', invocation),
            'attachment:invocation')
    return {invocation + 'attachment-' + step: 'ui:attachment-' + step
            for step in ('remove', 'remaining')}


def boundary_batch(batch):
    require(batch in ('count', 'sixth', 'maximum', 'oversized', 'total', 'overflow',
                      'name180', 'name181', 'hidden', 'mixed', 'single', 'changed'),
            'attachment:batch')
    prefix = 'boundary-' + batch
    return {prefix + '-before': 'ui:' + prefix + '-before',
            **file_handoff(prefix),
            **{prefix + '-' + step: 'ui:' + prefix + '-' + step
               for step in ('result', 'preserved')}}


def compare_file_draft(value):
    require(value == {'draft': 'attachment-file', 'attachments': ['Synthetic note.txt'],
        'collection': 'ready', 'validation': 'none', 'controls': 'ready',
        'items': [['Synthetic note.txt', '34 bytes']], 'include_logs': False},
        'attachment:preserved-draft')
    return deepcopy(value)


class AttachmentJourney(WindowSwitchJourney):
    """FEED12 unchanged preview and FEED06 rejected-file preservation checks."""
    def __init__(self, context, progress, plan, *, actions=None):
        super().__init__(context, progress, plan, actions=actions)
        self.before_preview = None
        self.boundary_before = {}
        self.source_before = None
        self.file_draft = None

    def check_settings(self, stage, observed):
        super().check_settings(stage, observed)
        operation = self.plan.screen_tags.get(stage, '').removeprefix('ui:')
        if 'file_draft' in observed.get('ui', {}):
            value = compare_file_draft(observed['ui']['file_draft'])
            if operation == 'files-feedback-draft':
                require(self.file_draft is None, 'attachment:draft-replay')
                self.file_draft = value
            else:
                require(self.file_draft is not None and value == self.file_draft,
                        'attachment:draft-changed')
        if operation in ('boundary-single-preserved', 'boundary-source-unchanged',
                         'boundary-changed-preserved'):
            current = tuple(tuple(item) for item in observed['ui']['boundary']['items'])
            if operation == 'boundary-single-preserved':
                require(self.source_before is None, 'attachment:source-replay')
                self.source_before = current
            else:
                require(self.source_before == (('Synthetic note.txt', '26 bytes'),),
                        'attachment:source-entry')
                require(current == (self.source_before if operation == 'boundary-source-unchanged'
                                    else (('Synthetic note.txt', '34 bytes'),)),
                        'attachment:source-result')
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
        elif batch in ('sixth', 'oversized', 'overflow', 'name181', 'hidden', 'mixed'):
            require(batch in self.boundary_before and current == self.boundary_before[batch],
                    'attachment:rejection-list-changed')
