"""Preset duration editor; backend validation owns bounds and whole seconds."""

from decimal import Decimal, DecimalException, ROUND_HALF_UP

from gi.repository import Gtk

from broker.oh_no_parent_control.preferences import (
    MIN_TIME_GRANT_SECONDS, MAX_TIME_GRANT_SECONDS, validate_time_grant_presets,
)
from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text,
)
from .chrome import ArmoredButton, MetalBoard
from .duration_controls import DurationControls, DurationError, DurationEditorActions, duration_number


def rounded_preset_value(text):
    value = duration_number(text)
    if value is None:
        return None
    try:
        return value.quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)
    except DecimalException:
        return None


def suggested_preset_seconds(presets):
    largest = max(presets, default=None)
    if largest is None:
        return 1800
    return next((largest + step for step in (3600, 60)
                 if largest + step <= MAX_TIME_GRANT_SECONDS), largest)


def preset_display_value(seconds, unit):
    scale = 60 if unit == 'minute' else 3600
    # Backend presets can contain any whole second. Show enough precision to
    # distinguish those values, retaining exact seconds until the input changes.
    return format(Decimal(seconds) / scale, '.10f').rstrip('0').rstrip('.')


class PresetDialog(Gtk.Window):
    def __init__(self, parent, seconds, presets, saved, closed):
        super().__init__(application=parent.get_application(), transient_for=parent,
                         modal=True, destroy_with_parent=True, decorated=False)
        self._saved, self._closed_callback = saved, closed
        self._closed = False
        self._others = [value for value in presets if value != seconds]
        self.add_css_class('oh-no-parent-control-language-dialog')
        self.add_css_class('preset-dialog')
        set_automation_id(self, 'preset-editor-dialog')
        title = m.ADD_PRESET_TIME if seconds is None else m.EDIT_PRESET_TIME
        set_text(self, 'title', title)
        self.set_default_size(460, -1)
        self.connect('close-request', self._cancel)
        self.connect('destroy', lambda *_: self._notify_closed())
        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                          margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        header = Gtk.Box(spacing=16)
        heading = localized(Gtk.Label, label=title, xalign=0, hexpand=True,
                            wrap=True, css_classes=['oh-no-parent-control-language-title'])
        set_automation_id(heading, 'preset-editor-title')
        header.append(heading)
        close = ArmoredButton(label='×', armor_kind='cancel', css_classes=['preferences-close'])
        describe_control(close, m.CLOSE, m.CANCEL, automation_id='preset-editor-close')
        close.connect('clicked', self._cancel)
        header.append(close)
        content.append(header)
        content.append(localized(Gtk.Label, label=m.TIME_DURATION, xalign=0))
        if seconds is None:
            seconds = suggested_preset_seconds(presets)
        unit = 'hour' if seconds % 3600 == 0 else 'minute'
        self._range_message = m.INVALID_PRESET_DURATION % {
            'minimum': MIN_TIME_GRANT_SECONDS, 'maximum': MAX_TIME_GRANT_SECONDS}
        self._units = ('minute', 'hour')
        self._initial_seconds = seconds
        timing = DurationControls(namespace='preset', value=preset_display_value(seconds, unit), unit=unit,
            units=[('minute', m.MINUTES), ('hour', m.HOURS)],
            label=m.TIME_DURATION, description=self._range_message, step=self._step,
            input_purpose=Gtk.InputPurpose.NUMBER, max_length=20)
        self._value, self._unit = timing.value, timing.unit
        content.append(timing)
        content.append(localized(Gtk.Label, label=self._range_message, xalign=0, wrap=True,
                                 css_classes=['reminder-trigger']))
        self._error = DurationError('preset')
        content.append(self._error)
        actions = DurationEditorActions('preset', self._cancel, self._submit)
        self._save_button = actions.submit
        content.append(actions)
        board.append(content)
        self.set_child(board)
        self._value.connect('changed', self._input_changed)
        self._unit.connect('notify::selected', self._input_changed)
        self._validate()

    @staticmethod
    def _scale(unit):
        return {'minute': 60, 'hour': 3600}[unit]

    def _unit_token(self):
        return self._units[self._unit.get_selected()]

    def _seconds(self):
        if self._initial_seconds is not None:
            return self._initial_seconds
        try:
            value = rounded_preset_value(self._value.get_text().strip())
            if value is None:
                return None
            seconds = value * self._scale(self._unit_token())
            if not seconds.is_finite() or seconds != seconds.to_integral_value():
                return None
            if not MIN_TIME_GRANT_SECONDS <= seconds <= MAX_TIME_GRANT_SECONDS:
                return None
            return validate_time_grant_presets([int(seconds)])[0]
        except (DecimalException, ValueError, OverflowError):
            return None

    def _step(self, delta):
        scale = self._scale(self._unit_token())
        seconds = self._seconds()
        seconds = max(MIN_TIME_GRANT_SECONDS, min(MAX_TIME_GRANT_SECONDS,
                      (seconds if seconds is not None else MIN_TIME_GRANT_SECONDS) + delta * scale))
        minimum = (Decimal(MIN_TIME_GRANT_SECONDS) / scale).quantize(Decimal('.1'), rounding='ROUND_UP')
        value = max(minimum, rounded_preset_value(str(Decimal(seconds) / scale)))
        self._value.set_text(format(value, 'f').removesuffix('.0'))

    def _validate(self, *_args):
        raw = self._value.get_text().strip()
        value = rounded_preset_value(raw)
        if (self._initial_seconds is None and value is not None and '.' in raw
                and len(raw.split('.')[1]) > 1):
            self._value.set_text(format(value, 'f'))
            return
        seconds = self._seconds()
        duplicate = seconds in self._others
        self._error.update(raw, seconds is not None and not duplicate,
                           m.DUPLICATE_PRESET if duplicate else self._range_message)
        self._save_button.set_sensitive(seconds is not None and not duplicate)

    def _input_changed(self, *_args):
        self._initial_seconds = None
        self._validate()

    def _submit(self, *_args):
        seconds = self._seconds()
        if seconds is None or seconds in self._others:
            self._validate()
            return
        self._saved(seconds)
        self._cancel()

    def _notify_closed(self):
        if not self._closed:
            self._closed = True
            self._closed_callback()

    def _cancel(self, *_args):
        self._notify_closed()
        self.destroy()
        return True
