"""Case 200: both grants keep their deadlines across spring-forward."""

from seasonal_paired_grants import PLAN, execute as execute_paired_grants


def execute(recorder, context):
    execute_paired_grants(recorder, context, PLAN)


E2E_CASES = {'spring-forward-paired-grants': execute}
