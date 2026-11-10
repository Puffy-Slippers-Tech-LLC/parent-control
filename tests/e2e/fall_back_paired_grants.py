"""Case 203: both grants keep their deadlines across the repeated local hour."""

from seasonal_paired_grants import FALL_BACK_PLAN as PLAN, execute as execute_paired_grants


def execute(recorder, context):
    execute_paired_grants(recorder, context, PLAN)


E2E_CASES = {'fall-back-paired-grants': execute}
