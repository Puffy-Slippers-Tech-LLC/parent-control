"""Read-only Chinese FIX06 on the product-free, fresh administrator envelope."""
from dataclasses import replace
from native_fixtures import fixture_actions
from product_free_entry import PLAN as ENTRY_PLAN, ProductFreeEntryJourney

PLAN = replace(ENTRY_PLAN, stage_actions={
    'wrong-entry': 'native-refuse', 'desktop': 'native-verify'})


def journey(context, progress):
    return ProductFreeEntryJourney(context, progress, PLAN,
                                   actions=fixture_actions(profile='chinese'))
