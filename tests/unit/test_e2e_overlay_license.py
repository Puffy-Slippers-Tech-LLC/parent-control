"""Overlay About isolation, read-only license and durable form comparisons.

Parallelism: process-local doubles/private tmp_path only; no live resources.
"""
from copy import deepcopy
from dataclasses import replace
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
import accessible_ui as a
import check_e2e_overlay_license as check
import check_e2e_overlay_browser_links as browser_check
from overlay_license import PLAN, BROWSER_LINKS_PLAN, OverlayLicenseJourney
from journey_blocks import overlay_license_read
from parent_setup_qualification import OverlayLicenseQualification, KioskEntryQualification
from parent_setup_qualification import OverlayBrowserLinksQualification
from private_artifacts import EvidenceError
from tests.support.accessible_ui import Node, ui_for
from ui_observations import OPERATION_LABELS, UiObservations


def about_tree(monkeypatch, opened=True):
    form = Node(identity='kiosk-request-form')
    window = Node(identity='kiosk-request-window', children=[form],
                  states=('visible', 'showing', 'sensitive', 'active'))
    link = Node(identity='about-license-value', role='link')
    about = Node(identity='about-dialog', children=[
        Node(a.PRODUCT, identity='about-product-name', role='label'),
        Node('Version 1.1', identity='about-version', role='label'), link],
        states=('visible', 'showing', 'sensitive', 'active'))
    ui = ui_for(window)
    owner = ui.api.get_desktop(0)
    owner.identity = a.CHILD_APPLICATION
    if opened:
        window.children.append(about)
        about.parent = window
    monkeypatch.setattr(ui, 'require_child_overlay_session', lambda: None)
    return ui, owner, window, about, link


@pytest.mark.parametrize('binding', ['license', 'website', 'privacy'])
@pytest.mark.parametrize('fault', ['', 'missing', 'disabled', 'hidden', 'no-action',
    'focus-only', 'ambiguous', 'duplicate', 'wrong-owner', 'inactive', 'defunct', 'clipped',
    'product', 'version'])
def test_overlay_license_reads_only_fresh_owned_public_information(monkeypatch, fault, binding):
    ui, owner, window, about, link = about_tree(monkeypatch)
    link.identity = 'about-' + binding + '-value'
    if fault == 'missing': link.identity = ''
    if fault == 'disabled': link.states.discard('sensitive')
    if fault == 'hidden': link.states.discard('visible')
    if fault == 'defunct': link.states.add('defunct')
    if fault == 'clipped': link.states.discard('showing')
    if fault == 'no-action': link.get_action_iface = lambda: None
    if fault == 'focus-only': link.action.get_action_name = lambda _: 'focus.child'
    if fault == 'ambiguous': link.action.get_n_actions = lambda: 2
    if fault == 'duplicate':
        duplicate = Node(identity=link.identity, role='link')
        duplicate.parent = about
        about.children.append(duplicate)
    if fault == 'wrong-owner': owner.identity = a.PARENT_APPLICATION
    if fault == 'inactive': about.states.discard('active')
    if fault in ('product', 'version'):
        about.children[0 if fault == 'product' else 1].name = 'wrong'
    if fault in ('', 'clipped'):
        result = ui.run('overlay-' + binding + '-read', '1.1')
        observer = UiObservations(Mock())
        observer.call = Mock(return_value=(json.dumps(result).encode(), []))
        assert observer.observe('overlay-' + binding + '-read') == result
    else:
        with pytest.raises(a.UiError): ui.run('overlay-' + binding + '-read', '1.1')
    link.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['missing-about', 'wrong-owner', 'inactive-form', 'already-open'])
@pytest.mark.parametrize('binding', ['license', 'website', 'privacy'])
def test_overlay_about_entry_refuses_before_menu_input(monkeypatch, fault, binding):
    ui, owner, window, about, _ = about_tree(monkeypatch, opened=fault == 'already-open')
    ui.activate_id = Mock()
    if fault == 'missing-about':
        assert ui.run('overlay-about-refused', '1.1')['outcome'] == 'passed'
        with pytest.raises(a.UiError): ui.read_overlay_link('1.1', binding)
    else:
        if fault == 'wrong-owner': owner.identity = a.KIOSK_APPLICATION
        if fault == 'inactive-form': window.states.discard('active')
        with pytest.raises(a.UiError): ui.open_overlay_about()
    ui.activate_id.assert_not_called()


def test_overlay_link_rechecks_current_owner_and_state_without_input(monkeypatch):
    ui, owner, _, _, link = about_tree(monkeypatch)
    link.identity = 'about-website-value'
    ui.read_overlay_link('1.1', 'website')
    link.states.discard('sensitive')
    with pytest.raises(a.UiError): ui.read_overlay_link('1.1', 'website')
    link.states.add('sensitive')
    owner.identity = a.KIOSK_APPLICATION
    with pytest.raises(a.UiError): ui.read_overlay_link('1.1', 'website')
    link.action.do_action.assert_not_called()


@pytest.mark.parametrize('fault', ['', 'still-open', 'wrong-owner', 'missing-form', 'inactive-form'])
def test_overlay_close_requires_complete_absence_and_active_same_owner(monkeypatch, fault):
    ui, owner, window, about, _ = about_tree(monkeypatch, opened=fault == 'still-open')
    if fault == 'wrong-owner': owner.identity = a.KIOSK_APPLICATION
    if fault == 'missing-form': window.children.clear()
    if fault == 'inactive-form': window.states.discard('active')
    if fault:
        with pytest.raises(a.UiError): ui.overlay_about_closed()
    else: ui.overlay_about_closed()


@pytest.mark.parametrize('selector,qualification,plan', [
    (check, OverlayLicenseQualification, PLAN),
    (browser_check, OverlayBrowserLinksQualification, BROWSER_LINKS_PLAN)])
def test_registration_and_independent_fragment(monkeypatch, selector, qualification, plan):
    calls = []
    monkeypatch.setattr(selector, 'smoke', lambda **kw: calls.append(kw) or 0)
    assert selector.main() == 0 and calls[0]['challenge_profile'] == plan.prefix
    context = SimpleNamespace()
    journey = qualification.journey(context, Mock())
    assert journey.plan is plan and context.installed_snapshot.startswith('onpc-v')
    assert qualification.attach_installed_snapshot is KioskEntryQualification.attach_installed_snapshot
    operations = {tag[3:] for tag in plan.screen_tags.values() if tag.startswith('ui:')}
    assert operations <= a.OPERATIONS and operations <= OPERATION_LABELS.keys()
    assert a.OVERLAY_ABOUT_OPERATIONS <= a.CHILD_DESKTOP_OPERATIONS
    assert not (a.OVERLAY_ABOUT_OPERATIONS & a.KIOSK_SESSION_OPERATIONS)
    assert overlay_license_read('other-')['other-license-read'] == 'ui:overlay-license-read'
    assert overlay_license_read('other-', links='browser-links')['other-privacy-read'] == 'ui:overlay-privacy-read'
    with pytest.raises(EvidenceError): overlay_license_read(links='unknown')


@pytest.mark.parametrize('fault', ['', 'changed', 'mutated', 'missing', 'replay'])
def test_real_recorder_compares_renamed_form_before_durable_reply(tmp_path, fault):
    plan = replace(PLAN, screen_tags={'capture': 'ui:overlay-valid-fraction-soft-read',
        'compare': 'ui:overlay-valid-fraction-soft-read'},
        request_checks={'compare': ('capture', 'overlay-about:changed-form', 'unchanged_form')},
        invocations=(), challenges={}, assertions_after={}, phases={}, advance_after={}, balance_checks={})
    journey = OverlayLicenseJourney(SimpleNamespace(directory=tmp_path), Mock(), plan)
    value = {'surface': 'child-overlay', 'child': 'fixture-child', 'approver': 'fixture-parent',
        'duration_seconds': 75, 'custom_text': '1.25', 'allow_soft': True}
    if fault != 'missing': journey.check_preserved_request('capture', {'ui': {'valid_choice': {'request': value}}})
    returned = deepcopy(value)
    if fault == 'mutated': value['allow_soft'] = False; returned = deepcopy(value)
    if fault == 'changed': returned['approver'] = 'other-fixture-parent'
    if fault == 'replay': journey.check_preserved_request('compare', {'ui': {'valid_choice': {'request': returned}}})
    journey.steps = [{'stage': 'ready'}, {'stage': 'setup-detached'}, {'stage': 'capture'}]
    journey.boot = 'a' * 64
    journey.check_estimate = Mock()
    journey.ui = SimpleNamespace(boot_proof=journey.boot, observe=Mock(return_value={
        'operation': 'overlay-valid-fraction-soft-read', 'outcome': 'passed', 'interface': 'AT-SPI',
        'valid_choice': {'request': returned}}))
    (tmp_path / 'compare.request.json').write_text(json.dumps({'stage': 'compare', 'screenshot': None}))
    if fault:
        with pytest.raises(EvidenceError): journey.step(Mock())
        assert not (tmp_path / 'compare.reply.json').exists()
    else:
        journey.step(Mock())
        assert (tmp_path / 'compare.reply.json').exists()
        assert journey.steps[-1]['comparison']['unchanged_form'] is True
