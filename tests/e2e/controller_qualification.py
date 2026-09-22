"""Case 1 composes FLOW00 and the product-free serial harness envelope."""

from serial_harness import (
    PLAN, SERIAL_STAGES, matched_screens, record_serial_journey,
    validate_completion, validate_stages,
)


def execute(recorder, context):
    record_serial_journey(recorder, context)


E2E_CASES = {'gdm-observation': execute}
