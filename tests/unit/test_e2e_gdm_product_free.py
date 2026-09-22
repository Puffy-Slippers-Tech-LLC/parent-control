"""Product-free GDM qualification contracts."""

from pathlib import Path
import json

from tests.support.paths import ROOT
from tests.support.perl import run_perl


def test_product_free_worker_repeats_the_fixed_cycle_with_its_own_markers():
    from test_e2e_gdm_navigation import RUN

    source = RUN.replace('onpc_gdm::navigation_qualification',
                         'onpc_gdm::product_free_qualification')
    result = json.loads(run_perl(source).stdout)
    assert result['ok'], result['error']
    assert [event[1] for event in result['events'] if event[0] == 'exchange'] == [
        'initial-list', 'initial-focused', 'initial-prompt', 'initial-returned',
        'repeated-list', 'repeated-focused', 'repeated-prompt', 'repeated-returned',
    ]
    assert [event[1] for event in result['events'] if event[0] == 'stage'][:-1] == [
        'gdm-product-free-initial-list', 'gdm-product-free-initial-focused',
        'gdm-product-free-initial-prompt', 'gdm-product-free-initial-returned',
        'gdm-product-free-repeated-list', 'gdm-product-free-repeated-focused',
        'gdm-product-free-repeated-prompt', 'gdm-product-free-repeated-returned',
    ]


def test_product_free_gdm_uses_a_distinct_baseline_journey_binding():
    import check_e2e_gdm_product_free as check
    from parent_setup_qualification import (
        GdmProductFreeQualification, ParentJourneyQualification,
    )

    assert check.ASSETS == Path('/tmp/onpc-parent-setup-input')
    assert GdmProductFreeQualification.__bases__ == (ParentJourneyQualification,)
    assert GdmProductFreeQualification.observation_only is True
    context = type('Context', (), {})()
    journey = GdmProductFreeQualification.journey(context, lambda *_: None)
    assert context.product_free is True
    assert not hasattr(context, 'installed_snapshot')
    assert journey.plan.worker_mode == 'gdm_product_free'
    assert list(journey.plan.screen_tags.values()) == [
        'ui:gdm-product-free-list', 'ui:gdm-product-free-focused',
        'ui:gdm-product-free-select-parent', 'ui:gdm-product-free-returned',
        'ui:gdm-product-free-list', 'ui:gdm-product-free-focused',
        'ui:gdm-product-free-select-parent', 'ui:gdm-product-free-returned',
    ]


def test_product_free_gdm_is_the_fixed_argument_free_integration_selector():
    source = (ROOT / 'tests/integration/check_e2e_gdm_product_free.py').read_text()
    assert "ASSETS = Path('/tmp/onpc-parent-setup-input')" in source
    assert 'gdm_product_free=True' in source
    assert 'sys.argv' not in source
