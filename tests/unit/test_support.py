"""Shared external-input recipient and uncertain-delivery guards."""

import sys
from types import ModuleType, SimpleNamespace

import pytest


@pytest.mark.parametrize('fault', ['', 'recipient', 'partial', 'uncertain', 'cancelled'])
@pytest.mark.parametrize('post_delay', [0.05])
def test_keyboard_chord_pacing_restores_defaults_and_preserves_single_use(
        monkeypatch, fault, post_delay):
    # Process-local input/config doubles; no real keyboard, display or sleep.
    from unittest.mock import Mock
    from tests.support import keyboard
    configuration = ModuleType('dogtail.config')
    configuration.config = SimpleNamespace(action_delay=1)
    monkeypatch.setitem(sys.modules, 'dogtail.config', configuration)
    deliveries = []
    def send(keys):
        deliveries.append((keys, configuration.config.action_delay))
        if fault == 'partial':
            raise RuntimeError('partial delivery')
        if fault == 'cancelled':
            raise KeyboardInterrupt()
    dogtail = ModuleType('dogtail')
    dogtail.rawinput = SimpleNamespace(keyCombo=send)
    monkeypatch.setitem(sys.modules, 'dogtail', dogtail)
    node = Mock()
    node.get_state_set.return_value.contains.return_value = fault != 'recipient'
    ui = SimpleNamespace(input_uncertain=fault == 'uncertain', id_target=Mock(return_value=node))
    def deliver():
        keyboard.key_combo(ui, 'owned-popup', 'Escape', state='active', post_delay=post_delay)
    if fault:
        with pytest.raises((AssertionError, RuntimeError, KeyboardInterrupt)):
            deliver()
    else:
        deliver()
        assert not ui.input_uncertain
    expected = [('Escape', 1 if post_delay is None else post_delay)]
    assert deliveries == ([] if fault in ('recipient', 'uncertain') else expected)
    assert configuration.config.action_delay == 1
    if fault in ('partial', 'cancelled'):
        assert ui.input_uncertain
        with pytest.raises(AssertionError, match='uncertain'):
            deliver()
        assert deliveries == expected
    if fault != 'uncertain':
        ui.id_target.assert_called_once_with('owned-popup')
    else:
        ui.id_target.assert_not_called()


def test_native_delivery_refuses_product_control_without_sending(monkeypatch):
    from unittest.mock import Mock
    from tests.support import keyboard

    node, send = Mock(), Mock()
    ui = SimpleNamespace(input_uncertain=False, id_target=Mock(return_value=node))
    monkeypatch.setattr(keyboard, 'is_product_node', lambda value: value is node)
    with pytest.raises(AssertionError, match='require Application UI'):
        keyboard.deliver(ui, 'feedback-editor-input', 'focused', send)
    ui.id_target.assert_called_once_with('feedback-editor-input')
    node.get_state_set.assert_not_called()
    send.assert_not_called()
    assert not ui.input_uncertain
