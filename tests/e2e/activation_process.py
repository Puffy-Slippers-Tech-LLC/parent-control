"""LIFE04/05: automatic broker activation preserves the parent's open settings."""
from dataclasses import replace

from update_no_action import PLAN as AUTOMATIC_PLAN, UpdateNoActionJourney

PLAN = replace(AUTOMATIC_PLAN, prefix='activation-process', worker_mode='activation_process',
    assertions_after={**AUTOMATIC_PLAN.assertions_after,
        'upgrade-result': 'real-process-update-completed-automatically'})


class ActivationProcessJourney(UpdateNoActionJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN, activation='process-restart')
