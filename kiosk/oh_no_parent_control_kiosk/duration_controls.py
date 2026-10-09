"""Shared duration input and feedback; backends own duration constraints."""

from decimal import Decimal, DecimalException
import re

from gi.repository import Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control
from common.oh_no_parent_control_ui.application_ui import bind_ui
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    register_retranslation, localized, set_text, fixed_direction,
)
from .chrome import ArmoredButton


NUMBER_RE = re.compile(r'^(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)$')


def duration_number(text):
    """Accept ordinary decimal input, including an editable trailing point."""
    raw = text.strip()
    if not NUMBER_RE.fullmatch(raw):
        return None
    try:
        value = Decimal(raw)
        return value if value.is_finite() else None
    except DecimalException:
        return None


class DurationError(Gtk.Label):
    def __init__(self, namespace):
        super().__init__(visible=False, wrap=True, css_classes=['error'])
        describe_control(self, m.INVALID_NUMBER, m.INVALID_NUMBER,
                         automation_id=f'{namespace}-editor-error')

    def update(self, text, valid, backend_message):
        message = m.INVALID_NUMBER if duration_number(text) is None else backend_message
        self.show_message(None if valid else message)

    def show_message(self, message):
        if message is not None:
            set_text(self, 'label', message)
            describe_control(self, message, message)
        self.set_visible(message is not None)


class DurationEditorActions(Gtk.Box):
    def __init__(self, namespace, cancel, submit):
        super().__init__(spacing=10, homogeneous=True,
                         css_classes=['oh-no-parent-control-actions'])
        fixed_direction(self, Gtk.TextDirection.LTR)
        for identity, message, callback in (
                ('cancel', m.CANCEL, cancel), ('save', m.SAVE, submit)):
            button = localized(ArmoredButton, label=message,
                armor_kind='request',
                css_classes=['oh-no-parent-control-cancel-button' if identity == 'cancel'
                             else 'oh-no-parent-control-request-button'])
            describe_control(button, message, message, automation_id=f'{namespace}-editor-{identity}')
            button.connect('clicked', callback)
            if identity == 'save':
                self.submit = button
            self.append(button)


class DurationControls(Gtk.Box):
    def __init__(self, *, namespace, value, unit, units, label, description, step,
                 input_purpose=Gtk.InputPurpose.NUMBER, max_length=20):
        super().__init__(spacing=16, homogeneous=True, css_classes=['duration-controls'])
        self._units = [token for token, _message in units]
        number = Gtk.Box(spacing=0, css_classes=['reminder-number'])
        self.value = Gtk.Entry(input_purpose=input_purpose, width_chars=10,
                               max_width_chars=10, max_length=max_length, hexpand=True)
        self.value.set_text(str(value))
        describe_control(self.value, label, description, automation_id=f'{namespace}-value')
        number.append(self.value)
        steps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for identity, glyph, delta in (('increase', '▴', 1), ('decrease', '▾', -1)):
            button = Gtk.Button(label=glyph, css_classes=['reminder-step'])
            describe_control(button, label, description, automation_id=f'{namespace}-value-{identity}')
            button.connect('clicked', lambda _b, d=delta: step(d))
            steps.append(button)
        number.append(steps)
        self.append(number)
        self.unit = Gtk.DropDown(model=Gtk.StringList.new([''] * len(units)))
        self.unit.set_selected(self._units.index(unit))
        describe_control(self.unit, label, description, automation_id=f'{namespace}-unit')
        bind_ui(self.unit, get_value=self.unit_token, set_value=self.set_unit, choices=self._units)

        def translate(translations):
            selected = self.unit.get_selected()
            self.unit.get_model().splice(0, len(units),
                                         [message.render(translations) for _token, message in units])
            self.unit.set_selected(selected)

        register_retranslation(self, translate)
        self.append(self.unit)

    def unit_token(self):
        return self._units[self.unit.get_selected()]

    def set_unit(self, value):
        if value not in self._units:
            raise ValueError('invalid duration unit')
        self.unit.set_selected(self._units.index(value))
