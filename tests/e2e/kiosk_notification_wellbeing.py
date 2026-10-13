"""Finite installed engineering check; no natural-reminder customer credit."""
from dataclasses import replace
import json

from installed_journey import InstalledJourney
from kiosk_eligible_choices import PLAN as CHOICES_PLAN
from private_artifacts import require
import system_runner as system

EXTRA = ('kiosk-reminder-preview', 'kiosk-reminder-preview-cancel')
PLAN = replace(CHOICES_PLAN, worker_mode='kiosk_notification_wellbeing',
    screen_tags={**CHOICES_PLAN.screen_tags, **{stage: 'ui:' + stage for stage in EXTRA}},
    phases={**CHOICES_PLAN.phases, **{stage: 'step-2' for stage in EXTRA}})


class KioskNotificationWellbeingJourney(InstalledJourney):
    def __init__(self, context, progress):
        super().__init__(context, progress, PLAN)

    def check_request(self, stage, observed):
        super().check_request(stage, observed)
        if stage == 'selections-read':
            self.context.lease.guard()
            result = json.loads(self.transport.call(['env',
                'ONPC_EXPECTED_RUN=' + self.context.lease.state['run'],
                'PYTHONDONTWRITEBYTECODE=1', '/usr/bin/python3', '-B',
                system.PAYLOAD + '/system_wellbeing_qualification.py', 'ordinary'], timeout=330))
            require(type(result) is dict and set(result) == {'original', 'backup_recorded',
                'suppressed', 'restored', 'ordinary_settings_environment_retained', 'owned_manager_stopped'}
                and result['original'] in ('default', 'true', 'false') and all(value is True
                for key, value in result.items() if key != 'original'), 'wellbeing-installed:response')
            observed['engineering_ordinary_wellbeing'] = result
