"""Child preferences, retaining the request screens' language chooser contract."""

import copy
import math
import uuid

import cairo

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, TranslationContext, fixed_direction,
    register_retranslation,
)

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("Graphene", "1.0")
from gi.repository import Gdk, GLib, Graphene, Gtk, Pango

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.application_ui import bind_ui
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.languages import (
    SUPPORTED_LANGUAGES, language_direction, language_matches, selected_language,
)
from common.oh_no_parent_control_ui.user_icon import apply_gtk_user_icon
from .chrome import ArmoredButton, MetalBoard


class PreferenceTab(Gtk.ToggleButton):
    """Stepped cyan/purple plates spanning the complete tab header."""

    def do_snapshot(self, snapshot):
        width, height = self.get_width(), self.get_height()
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, width, height))
        active = self.get_active()
        top = 1 if active else 3
        cr.move_to(1, height - 1)
        for x, y in ((1, height - 5), (5, height - 5), (5, height - 10),
                     (9, height - 10), (9, top + 8), (13, top + 8),
                     (13, top + 4), (19, top + 4), (19, top),
                     (width - 19, top), (width - 19, top + 4),
                     (width - 13, top + 4), (width - 13, top + 8),
                     (width - 9, top + 8), (width - 9, height - 10),
                     (width - 5, height - 10), (width - 5, height - 5),
                     (width - 1, height - 5), (width - 1, height - 1)):
            cr.line_to(x, y)
        cr.close_path()
        fill = cairo.LinearGradient(0, 0, 0, height)
        rgb = (0.04, 0.40, 0.36) if active else (0.23, 0.19, 0.36)
        fill.add_color_stop_rgba(0, *rgb, 0.95)
        fill.add_color_stop_rgba(1, *rgb, 0.65)
        cr.set_source(fill)
        cr.fill_preserve()
        cr.set_source_rgb(*((0.16, 0.91, 0.79) if active else (0.57, 0.43, 0.78)))
        cr.set_line_width(2)
        cr.stroke()
        Gtk.ToggleButton.do_snapshot(self, snapshot)


class PreferenceTabIcon(Gtk.Widget):
    """Theme-independent globe and filled bell matching the tab plates."""

    def __init__(self, name):
        super().__init__(valign=Gtk.Align.CENTER)
        self._name = name

    def do_measure(self, orientation, for_size):
        return 20, 20, -1, -1

    def do_snapshot(self, snapshot):
        cr = snapshot.append_cairo(Graphene.Rect().init(0, 0, 20, 20))
        cr.scale(20 / 26, 20 / 26)
        color = self.get_style_context().get_color()
        cr.set_source_rgba(color.red, color.green, color.blue, color.alpha)
        cr.set_line_width(2)
        if self._name == 'language':
            cr.arc(13, 13, 11, 0, math.tau)
            cr.stroke()
            cr.save()
            cr.translate(13, 13)
            cr.scale(0.45, 1)
            cr.arc(0, 0, 11, 0, math.tau)
            cr.restore()
            cr.stroke()
            for y, inset in ((7, 4), (13, 2), (19, 4)):
                cr.move_to(inset, y)
                cr.line_to(26 - inset, y)
            cr.stroke()
        else:
            cr.move_to(3, 21)
            cr.curve_to(7, 17, 6, 15, 6, 10)
            cr.curve_to(6, 2, 20, 2, 20, 10)
            cr.curve_to(20, 15, 19, 17, 23, 21)
            cr.close_path()
            cr.fill()
            cr.arc(13, 3, 2, 0, math.tau)
            cr.fill()
            cr.arc(13, 22, 3, 0, math.pi)
            cr.fill()


class ReminderDialog(Gtk.Window):
    """A modal editor saves to the preferences draft, never directly to storage."""

    def __init__(self, parent, record, reminders, saved, closed):
        super().__init__(application=parent.get_application(), transient_for=parent,
                         modal=True, destroy_with_parent=True, decorated=False)
        self._record = copy.deepcopy(record)
        self._other_times = {
            r['value'] * (60 if r['unit'] == 'minute' else 1)
            for r in reminders if record is None or r['id'] != record['id']}
        timing_record = record
        if record is None:
            largest = max(reminders, key=lambda r: r['value'] *
                          (60 if r['unit'] == 'minute' else 1), default=None)
            timing_record = ({'value': min(largest['value'] * 2,
                                          4294967295 // (60 if largest['unit'] == 'minute' else 1)),
                              'unit': largest['unit']} if largest else
                             {'value': 1, 'unit': 'minute'})
        self._saved, self._closed_callback = saved, closed
        self._notified_closed = False
        self.add_css_class('oh-no-parent-control-language-dialog')
        self.add_css_class('reminder-dialog')
        set_automation_id(self, 'reminder-editor-dialog')
        title = m.EDIT_REMINDER if record else m.ADD_REMINDER
        set_text(self, 'title', title)
        self.set_default_size(560, -1)
        self.connect('destroy', lambda *_: self._notify_closed())
        self.connect('close-request', self._close_requested)
        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=20,
                          margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        header = Gtk.Box(spacing=20)
        icon = Gtk.Image.new_from_icon_name('preferences-system-notifications-symbolic')
        icon.set_pixel_size(48)
        icon.add_css_class('reminder-bell')
        icon.add_css_class('reminder-editor-icon')
        header.append(icon)
        header.append(localized(Gtk.Label, label=title, xalign=0, hexpand=True,
                                css_classes=['oh-no-parent-control-language-title']))
        close = ArmoredButton(label='×', armor_kind='cancel', css_classes=['preferences-close'],
                              halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        describe_control(close, m.CLOSE, m.CANCEL, automation_id='reminder-editor-close')
        close.connect('clicked', self._cancel)
        header.append(close)
        content.append(header)
        fields = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                         css_classes=['preferences-page', 'reminder-editor-fields'])
        fields.append(localized(Gtk.Label, label=m.REMINDER_TEXT, xalign=0,
                                css_classes=['preferences-section-title']))
        fields.append(localized(Gtk.Label, label=m.REMINDER_TEXT_HELP, xalign=0,
                                wrap=True, css_classes=['reminder-trigger']))
        original_text = record.get('text', '') if record else ''
        # Keep legacy text intact, but prevent input from growing beyond its
        # existing length. Normal reminders are capped by GTK for all input.
        self._text = Gtk.Entry(hexpand=True, max_length=max(50, len(original_text)))
        describe_control(self._text, m.REMINDER_TEXT, m.REMINDER_TEXT_HELP,
                         automation_id='reminder-text')
        self._text.set_text(original_text)
        fields.append(self._text)
        self._count = Gtk.Label(xalign=1, css_classes=['reminder-trigger'])
        set_automation_id(self._count, 'reminder-text-count')
        fields.append(self._count)
        fields.append(localized(Gtk.Label, label=m.WHEN_TO_SHOW, xalign=0,
                                css_classes=['preferences-section-title']))
        fields.append(localized(Gtk.Label, label=m.REMINDER_TIMING_HELP, xalign=0,
                                wrap=True, css_classes=['reminder-trigger']))
        timing = Gtk.Box(spacing=16, homogeneous=True)
        number = Gtk.Box(spacing=0, css_classes=['reminder-number'])
        self._value = Gtk.Entry(input_purpose=Gtk.InputPurpose.DIGITS, width_chars=10,
                                max_width_chars=10, max_length=10, hexpand=True)
        self._value.set_text(str(timing_record['value']))
        describe_control(self._value, m.WHEN_TO_SHOW, m.REMINDER_TIMING_HELP,
                         automation_id='reminder-value')
        number.append(self._value)
        steps = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        for identity, glyph, delta in (('increase', '▴', 1), ('decrease', '▾', -1)):
            button = Gtk.Button(label=glyph, css_classes=['reminder-step'])
            describe_control(button, m.WHEN_TO_SHOW, m.REMINDER_TIMING_HELP,
                             automation_id=f'reminder-value-{identity}')
            button.connect('clicked', lambda _b, d=delta: self._step(d))
            steps.append(button)
        number.append(steps)
        timing.append(number)
        self._unit = Gtk.DropDown(model=Gtk.StringList.new(['', '']))
        self._unit.set_selected(1 if timing_record['unit'] == 'second' else 0)
        describe_control(self._unit, m.WHEN_TO_SHOW, m.REMINDER_TIMING_HELP,
                         automation_id='reminder-unit')
        bind_ui(self._unit, get_value=lambda: self._unit_token(),
                set_value=self._set_unit, choices=['minute', 'second'])
        register_retranslation(self, self._translate_units)
        timing.append(self._unit)
        fields.append(timing)
        self._error = localized(Gtk.Label, label=m.INVALID_REMINDER, wrap=True,
                                visible=False, css_classes=['error'])
        set_automation_id(self._error, 'reminder-editor-error')
        content.append(fields)
        self._duplicate = localized(Gtk.Label, label=m.DUPLICATE_REMINDER, wrap=True,
                                    visible=False, css_classes=['error', 'reminder-duplicate-warning'])
        set_automation_id(self._duplicate, 'reminder-duplicate-warning')
        content.append(self._duplicate)
        content.append(self._error)
        actions = Gtk.Box(spacing=20, homogeneous=True)
        actions.add_css_class('reminder-editor-actions')
        fixed_direction(actions, Gtk.TextDirection.LTR)
        for identity, message, callback in (
                ('cancel', m.CANCEL, self._cancel), ('save', m.SAVE, self._submit)):
            button = localized(ArmoredButton, label=message)
            if identity == 'save':
                button.add_css_class('oh-no-parent-control-request-button')
                self._save_button = button
            describe_control(button, message, message, automation_id=f'reminder-editor-{identity}')
            button.connect('clicked', callback)
            actions.append(button)
        content.append(actions)
        board.append(content)
        self.set_child(board)
        self._text.connect('changed', self._update_validation)
        self._value.connect('changed', self._update_validation)
        self._unit.connect('notify::selected', self._update_validation)
        parent.connect_object('notify::is-active', PreferencesDialog._parent_activated, self)
        self._update_validation()

    def _unit_token(self):
        return 'second' if self._unit.get_selected() == 1 else 'minute'

    def _set_unit(self, value):
        if value not in ('minute', 'second'):
            raise ValueError('invalid reminder unit')
        self._unit.set_selected(1 if value == 'second' else 0)

    def _translate_units(self, translations):
        model = self._unit.get_model()
        selected = self._unit.get_selected()
        model.splice(0, model.get_n_items(), [m.MINUTES.render(translations), m.SECONDS.render(translations)])
        self._unit.set_selected(selected)

    def _duration(self):
        raw = self._value.get_text().strip()
        maximum = 4294967295 // (60 if self._unit_token() == 'minute' else 1)
        return int(raw) if raw.isascii() and raw.isdigit() and 1 <= int(raw) <= maximum else None

    def _step(self, delta):
        value = self._duration() or 1
        maximum = 4294967295 // (60 if self._unit_token() == 'minute' else 1)
        self._value.set_text(str(max(1, min(maximum, value + delta))))

    def _update_validation(self, *_args):
        text = self._text.get_text()
        if len(text) <= 50:
            self._text.set_max_length(50)
        self._count.set_text(f'{len(text)}/50')
        value = self._duration()
        trigger = (PreferencesDialog._trigger_message({'value': value, 'unit': self._unit_token()})
                   if value is not None else m.INVALID_REMINDER)
        set_text(self._text, 'placeholder-text', trigger)
        duplicate = (value is not None and value * (60 if self._unit_token() == 'minute' else 1)
                     in self._other_times)
        self._duplicate.set_visible(duplicate)
        if duplicate:
            self._value.add_css_class('reminder-duplicate')
        else:
            self._value.remove_css_class('reminder-duplicate')
        self._save_button.set_sensitive(not duplicate)
        self._error.set_visible(False)

    def _submit(self, *_args):
        text, value = self._text.get_text(), self._duration()
        # Existing backend text may predate this 50-character editor. Preserve
        # it without truncation when changing only its trigger time.
        original_text = self._record.get('text', '') if self._record else ''
        if self._duplicate.get_visible():
            return
        if value is None or (len(text) > 50 and text != original_text):
            self._error.set_visible(True)
            return
        record = {'id': self._record['id'] if self._record else 'reminder-' + uuid.uuid4().hex,
                  'value': value, 'unit': self._unit_token(), 'text': text if text.strip() else ''}
        self._saved(record)
        self.destroy()

    def _cancel(self, *_args):
        self.destroy()

    def _notify_closed(self):
        if not self._notified_closed:
            self._notified_closed = True
            self._closed_callback()

    def destroy(self):
        # GtkWindow.destroy can unmap before the final native destroy signal
        # while a Python owner still holds it. End the draft lifecycle now.
        self._notify_closed()
        super().destroy()

    def _close_requested(self, *_args):
        self.destroy()
        return True


class PreferencesDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved, cancelled, *, account=None,
                 load_notifications=None, save_notifications=None):
        super().__init__(application=parent.get_application(),
                         title=m.PREFERENCES, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False, decorated=False)
        self._selected = selected_language(language, GLib.get_language_names())
        self._translation_context = TranslationContext(self._selected)
        set_text(self, 'title', m.PREFERENCES)
        set_automation_id(self, "language-dialog")
        self.add_css_class("oh-no-parent-control-language-dialog")
        self.set_default_size(400, -1)
        self.connect("map", self._size_to_gateway)
        self._save, self._saved = save, saved
        self._cancelled = cancelled
        self._saving = False
        self._closed = False
        self.connect('destroy', lambda *_: setattr(self, '_closed', True))
        self._load_notifications = load_notifications
        self._save_notifications = save_notifications
        self._notifications = None
        self._original_notifications = None
        self._notifications_loading = False
        self._editing = False

        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        header = Gtk.Box(spacing=20)
        self._logo = Gtk.Image.new_from_file(str(branding_asset_path("app_logo.png")))
        self._logo.set_halign(Gtk.Align.START)
        self._logo.set_valign(Gtk.Align.START)
        accessible_text(self._logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        header.append(self._logo)
        self._heading = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                                hexpand=True)
        title = localized(Gtk.Label, label=m.PREFERENCES, xalign=0, wrap=True,
                          css_classes=["oh-no-parent-control-language-title"])
        set_automation_id(title, "preferences-title")
        self._heading.append(title)
        self._account_row = Gtk.Box(spacing=12, visible=False)
        self._account_icon = Gtk.Image()
        self._account_row.append(self._account_icon)
        self._account_label = Gtk.Label(xalign=0, use_markup=True,
                                       ellipsize=Pango.EllipsizeMode.END,
                                       max_width_chars=28,
                                       css_classes=["oh-no-parent-control-language-account"])
        set_automation_id(self._account_label, "language-account")
        self._account_row.append(self._account_label)
        self._heading.append(self._account_row)
        header.append(self._heading)
        self._close = localized(ArmoredButton, label='×', armor_kind='cancel',
                                css_classes=['preferences-close'],
                                halign=Gtk.Align.CENTER, valign=Gtk.Align.START)
        describe_control(self._close, m.CLOSE, m.CANCEL, automation_id='preferences-close')
        self._close.connect('clicked', self._dismiss)
        header.append(self._close)
        content.append(header)

        tabs = Gtk.Box(homogeneous=True, spacing=0, css_classes=['preferences-tabs'])
        fixed_direction(tabs, Gtk.TextDirection.LTR)
        self._tabs = tabs
        self._tab_choices = {}
        describe_control(tabs, m.PREFERENCES, m.PREFERENCES, automation_id='preferences-tabs')
        bind_ui(tabs, get_value=lambda: self._pages.get_visible_child_name(),
                set_value=self._ui_select_tab, choices=['language', 'reminders'])
        for name, message in (('language', m.LANGUAGE), ('reminders', m.REMINDERS)):
            tab = PreferenceTab(css_classes=['preferences-tab'], hexpand=True)
            child = Gtk.Box(spacing=10, halign=Gtk.Align.CENTER,
                            margin_start=22, margin_end=22, margin_top=7, margin_bottom=7)
            child.append(PreferenceTabIcon(name))
            child.append(localized(Gtk.Label, label=message))
            tab.set_child(child)
            describe_control(tab, message, message, automation_id=f'preferences-tab-{name}')
            self._tab_choices[name] = tab
            if name == 'language':
                self._language_tab = tab
            else:
                tab.set_group(self._language_tab)
            tab.connect('toggled', self._switch_tab, name)
            tabs.append(tab)
        content.append(tabs)
        self._pages = Gtk.Stack(vexpand=True, vhomogeneous=True, hhomogeneous=True)
        self._language_page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                                      css_classes=['preferences-page'])
        language_title = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE, xalign=0,
                                   css_classes=['preferences-section-title'])
        set_automation_id(language_title, 'language-title')
        self._language_page.append(language_title)

        self._search = localized(Gtk.SearchEntry, placeholder_text=m.SEARCH_LANGUAGES)
        describe_control(self._search, m.SEARCH_LANGUAGES, m.SEARCH_LANGUAGES,
                         automation_id="language-search")
        self._search.connect("changed", self._filter_languages)
        keys = Gtk.EventControllerKey()
        keys.set_propagation_phase(Gtk.PropagationPhase.CAPTURE)
        keys.connect("key-pressed", self._search_keys)
        self.add_controller(keys)
        self._language_page.append(self._search)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                css_classes=["oh-no-parent-control-language-choices"])
        self._language_rows = []
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            choice = localized(Gtk.CheckButton)
            fixed_direction(choice, Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            fixed_direction(label, Gtk.TextDirection.RTL if language_direction(identity) == 'rtl'
                            else Gtk.TextDirection.LTR, language=identity)
            choice.set_child(label)
            if first is None:
                first = choice
            else:
                choice.set_group(first)
            describe_control(choice, name, m.SELECT_NAME_S % {'name': name},
                             automation_id=f"language-choice-{identity.lower()}")
            choice.set_active(identity == self._selected)
            choice.connect("toggled", self._choose, identity)
            self._choices.append(choice)
            self._language_rows.append((choice, identity, name))
        scroller = Gtk.ScrolledWindow(child=self._choices, vexpand=True,
                                      css_classes=["oh-no-parent-control-language-list"],
                                      accessible_role=Gtk.AccessibleRole.GROUP,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=1)
        self._scroller = scroller
        describe_control(scroller, m.LANGUAGE, m.CHOOSE_YOUR_LANGUAGE,
                         automation_id="language-list")
        bind_ui(scroller, get_value=lambda: self._selected,
                set_value=self._ui_select_language,
                choices=lambda: [identity for _row, identity, _name in self._language_rows])
        self._language_page.append(scroller)
        self._pages.add_named(self._language_page, 'language')
        self._build_reminders_page()
        content.append(self._pages)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        # Keep Save and Cancel in place while the candidate changes direction.
        fixed_direction(actions, Gtk.TextDirection.LTR)
        self._cancel = localized(ArmoredButton, label=m.CANCEL)
        describe_control(self._cancel, m.CANCEL, m.CANCEL,
                         automation_id="language-cancel")
        self._cancel.connect("clicked", self._dismiss)
        actions.append(self._cancel)
        self._continue = localized(ArmoredButton, label=m.SAVE,
                                       css_classes=["oh-no-parent-control-request-button"])
        describe_control(self._continue, m.SAVE, m.SAVE_YOUR_LANGUAGE_PREFERENCE,
                         automation_id="language-continue")
        self._continue.connect("clicked", self._submit)
        actions.append(self._continue)
        content.append(actions)
        board.append(content)
        self.set_child(board)
        self.set_account(account)
        self.set_default_widget(self._continue)
        self.connect("close-request", lambda *_args: True)
        parent.connect_object("notify::is-active", PreferencesDialog._parent_activated, self)
        self._language_tab.set_active(True)
        self._size_to_gateway(self)

    def destroy(self):
        self._closed = True
        super().destroy()

    def _build_reminders_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                       css_classes=['preferences-page'])
        heading = Gtk.Box(spacing=12)
        heading.append(localized(Gtk.Label, label=m.REMINDERS, xalign=0, hexpand=True,
                                 css_classes=['preferences-section-title']))
        self._add = Gtk.Button(css_classes=['reminder-add'])
        add_caption = Gtk.Box(spacing=6)
        add_caption.append(Gtk.Image.new_from_icon_name('list-add-symbolic'))
        add_caption.append(localized(Gtk.Label, label=m.ADD))
        self._add.set_child(add_caption)
        describe_control(self._add, m.ADD, m.REMINDERS, automation_id='reminder-add')
        self._add.connect('clicked', lambda *_: self._edit_reminder(None))
        heading.append(self._add)
        page.append(heading)
        self._reminder_pages = Gtk.Stack(vexpand=True)
        self._reminder_choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                                        css_classes=['oh-no-parent-control-language-choices'])
        self._reminder_scroller = Gtk.ScrolledWindow(
            child=self._reminder_choices, vexpand=True, min_content_height=1,
            css_classes=['oh-no-parent-control-language-list'],
            accessible_role=Gtk.AccessibleRole.GROUP,
            hscrollbar_policy=Gtk.PolicyType.NEVER, overlay_scrolling=False)
        describe_control(self._reminder_scroller, m.REMINDERS, m.REMINDERS,
                         automation_id='reminder-list')
        bind_ui(self._reminder_scroller,
                get_value=lambda: copy.deepcopy(self._notifications['reminders']) if self._notifications else [],
                choices=lambda: [r['id'] for r in self._notifications['reminders']] if self._notifications else [])
        self._reminder_pages.add_named(self._reminder_scroller, 'list')
        self._status = localized(Gtk.Label, label=m.REMINDERS, wrap=True)
        set_automation_id(self._status, 'reminder-status')
        self._reminder_pages.add_named(self._status, 'status')
        page.append(self._reminder_pages)
        self._retry = localized(Gtk.Button, label=m.TRY_AGAIN)
        describe_control(self._retry, m.REMINDERS, m.REMINDERS, automation_id='reminder-retry')
        self._retry.connect('clicked', lambda *_: self._request_notifications())
        self._retry.set_visible(False)
        page.append(self._retry)
        self._pages.add_named(page, 'reminders')
        self._add.set_sensitive(False)

    def _switch_tab(self, tab, name):
        if not tab.get_active():
            return
        self._pages.set_visible_child_name(name)
        if name == 'reminders' and self._notifications is None:
            self._request_notifications()

    def _ui_select_tab(self, value):
        if type(value) is not str or value not in self._tab_choices:
            raise ValueError('unknown preferences page')
        tab = self._tab_choices[value]
        if not tab.get_visible() or not tab.is_sensitive():
            raise ValueError('preferences page is unavailable')
        tab.set_active(True)

    def _request_notifications(self):
        if self._notifications_loading or self._closed:
            return
        self._notifications_loading = True
        self._retry.set_visible(False)
        self._reminder_pages.set_visible_child_name('status')
        set_text(self._status, 'label', m.REMINDERS)
        if self._load_notifications is None:
            self._notifications_failed(None)
        else:
            self._load_notifications(self._notifications_loaded, self._notifications_failed)

    def _notifications_loaded(self, settings):
        if self._closed:
            return
        self._notifications_loading = False
        self._notifications = copy.deepcopy(settings)
        self._render_reminders()
        self._original_notifications = copy.deepcopy(self._notifications)

    def _notifications_failed(self, _error):
        if self._closed:
            return
        self._notifications_loading = False
        set_text(self._status, 'label', m.THE_OPERATION_COULD_NOT_BE_COMPLETED_PLEASE_TRY_AGAIN_LATER)
        self._retry.set_visible(True)

    @staticmethod
    def _trigger_message(record):
        duration = (m.minute_count(record['value']) if record['unit'] == 'minute'
                    else m.second_count(record['value']))
        return m.TIME_REMAINING_NOTIFICATION % {'time': duration}

    def _render_reminders(self):
        row = self._reminder_choices.get_first_child()
        while row is not None:
            following = row.get_next_sibling()
            self._reminder_choices.remove(row)
            row = following
        records = self._notifications['reminders']
        records.sort(key=lambda r: r['value'] * (60 if r['unit'] == 'minute' else 1))
        for record in records:
            row = Gtk.Box(spacing=12, css_classes=['reminder-row'])
            icon = Gtk.Image.new_from_icon_name('preferences-system-notifications-symbolic')
            icon.add_css_class('reminder-bell')
            row.append(icon)
            text = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4, hexpand=True)
            trigger = self._trigger_message(record)
            label = localized(Gtk.Label, label=record.get('text') or trigger, xalign=0,
                              wrap=True, wrap_mode=Pango.WrapMode.WORD_CHAR,
                              max_width_chars=28, css_classes=['reminder-text'])
            set_automation_id(label, f"reminder-{record['id']}-text")
            text.append(label)
            description = localized(Gtk.Label, label=trigger, xalign=0, wrap=True,
                                    css_classes=['reminder-trigger'])
            set_automation_id(description, f"reminder-{record['id']}-trigger")
            text.append(description)
            row.append(text)
            for action, message, icon_name, callback in (
                    ('edit', m.EDIT_REMINDER, 'document-edit-symbolic', self._edit_reminder),
                    ('delete', m.DELETE_REMINDER, 'user-trash-symbolic', self._delete_reminder)):
                button = Gtk.Button(icon_name=icon_name, css_classes=[f'reminder-{action}'])
                describe_control(button, message, message,
                                 automation_id=f"reminder-{record['id']}-{action}")
                button.connect('clicked', lambda _b, r=record, cb=callback: cb(r))
                row.append(button)
            self._reminder_choices.append(row)
        self._reminder_pages.set_visible_child_name('list')
        self._add.set_sensitive(len(records) < 64)

    def _delete_reminder(self, record):
        self._notifications['reminders'].remove(record)
        self._render_reminders()

    def _edit_reminder(self, record):
        if self._editing:
            return
        self._editing = True
        self._reminder_dialog = ReminderDialog(
            self, record, self._notifications['reminders'],
            lambda value: self._commit_reminder(record, value),
            self._reminder_editor_closed)
        self._reminder_dialog.present()

    def _reminder_editor_closed(self):
        self._editing = False
        self._reminder_dialog = None

    def _commit_reminder(self, original, record):
        if original is None:
            self._notifications['reminders'].append(record)
        else:
            original.update(record)
        self._render_reminders()

    def _filter_languages(self, search):
        has_matches = False
        for row, identity, name in self._language_rows:
            matches = language_matches(search.get_text(), identity, name)
            row.set_visible(matches)
            has_matches = has_matches or matches
        self._scroller.set_focusable(has_matches)
        self._scroller.get_vadjustment().set_value(0)

    def _ui_select_language(self, value):
        for row, identity, _name in self._language_rows:
            if value == identity:
                if not row.get_visible() or not row.is_sensitive():
                    raise ValueError("language choice is unavailable")
                row.set_active(True)
                return
        raise ValueError("unknown language code")

    def _search_keys(self, _controller, keyval, _keycode, state):
        if self._pages.get_visible_child_name() != 'language':
            return False
        if keyval == Gdk.KEY_Escape and self._search.is_sensitive() and self._search.get_text():
            self._search.set_text("")
            return True
        if keyval == Gdk.KEY_Tab and not state & Gtk.accelerator_get_default_mod_mask():
            # GTK's radio-group Tab entry can skip every match when its active
            # member is hidden. Enter a visible row without changing selection.
            matches = [(row, identity) for row, identity, _name in self._language_rows
                       if row.get_visible() and row.is_sensitive()]
            focus = self.get_focus()
            in_search = focus is not None and (focus == self._search
                                               or focus.is_ancestor(self._search))
            if not matches and (in_search or self._scroller.has_focus()):
                return self._cancel.grab_focus()
            if matches and self._scroller.has_focus():
                row = next((row for row, identity in matches if identity == self._selected),
                           matches[0][0])
                return row.grab_focus()
        return False

    def _parent_activated(self, *_args):
        # Fullscreen preview compositors may raise the parent on an outside
        # click. Restore modal focus without hiding or recreating the chooser.
        if self.get_visible() and self.get_transient_for().is_active():
            self.present()

    def set_account(self, account):
        if account is not None:
            _uid, label, icon_file = account
            apply_gtk_user_icon(self._account_icon, icon_file, pixel_size=32)
            name = GLib.markup_escape_text(label)
            set_text(self._account_label, 'label', m.LANGUAGE_FOR_NAME % {
                'name': f'<span foreground="#38a8ed" weight="bold">{name}</span>',
            })
        self._account_row.set_visible(account is not None)
        # The logo spans precisely the title and account rows, including their gap.
        self._logo.set_pixel_size(self._heading.measure(Gtk.Orientation.VERTICAL, -1)[1])
        self._size_to_gateway(self)

    def _size_to_gateway(self, _window):
        # Import after main has finished loading the dialog class.
        from .main import _gateway_inner_corners

        parent = self.get_transient_for()
        width = max(400, self.get_child().measure(Gtk.Orientation.HORIZONTAL, -1)[0])
        list_width = width - 74  # Content margins and the tab panel's padding/border.
        if not self._search.get_text():
            heights = [row.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                       for row, _identity, _name in self._language_rows]
            self._list_height = (self._choices.measure(Gtk.Orientation.VERTICAL, list_width)[1]
                                 - sum(heights[10:]))
        # Aim for ten complete rows; the gateway bounds take priority on short
        # displays. Filtering keeps this viewport stable while typing.
        natural_height = (
            self.get_child().measure(Gtk.Orientation.VERTICAL, width)[1]
            - self._scroller.measure(Gtk.Orientation.VERTICAL, list_width)[1]
            + self._list_height
        )
        height = parent.get_height()
        if height <= 0:
            self.set_default_size(width, natural_height)
            return
        corners = _gateway_inner_corners(parent.get_width(), height)
        top = max(corners[0][1], corners[1][1])
        bottom = min(corners[2][1], corners[3][1])
        # Transient windows are centered; leave clearance at both gateway rails.
        available_height = int(2 * min(height / 2 - top, bottom - height / 2) - 32)
        self.set_default_size(width, max(1, min(natural_height, available_height)))

    def _choose(self, choice, identity):
        if choice.get_active():
            # Keep the mapped window and controls; GTK paints the translated
            # text and adjusted measurements together on the next frame.
            context_for(self).apply(identity)
            self._selected = identity
            self._logo.set_pixel_size(self._heading.measure(Gtk.Orientation.VERTICAL, -1)[1])
            self._size_to_gateway(self)

    def _submit(self, _button):
        if self._saving or self._editing:
            return
        self._saving = True
        self._error.set_visible(False)
        self._choices.set_sensitive(False)
        self._search.set_sensitive(False)
        self._continue.set_sensitive(False)
        self._cancel.set_sensitive(False)
        self._close.set_sensitive(False)
        self._tabs.set_sensitive(False)
        self._reminder_pages.set_sensitive(False)
        self._add.set_sensitive(False)
        self._retry.set_sensitive(False)
        if self._notifications is not None and self._notifications != self._original_notifications:
            self._save_notifications(copy.deepcopy(self._notifications),
                                     self._notifications_saved, self._preferences_failure)
        else:
            self._save(self._selected, self._success, self._failure)

    def _notifications_saved(self, settings):
        if self._closed:
            return
        self._original_notifications = copy.deepcopy(settings)
        self._save(self._selected, self._success, self._failure)

    def _preferences_failure(self, error):
        self._failure(error)
        set_text(self._error, 'label', m.COULD_NOT_SAVE_SETTING_S_PLEASE_TRY_AGAIN_LATER % {
            'setting': m.REMINDERS})

    def _dismiss(self, _button):
        if self._saving:
            return
        self._cancelled()
        self.destroy()

    def _success(self, language):
        if self._closed:
            return
        self.destroy()
        self._saved(language)

    def _failure(self, _error):
        if self._closed:
            return
        self._saving = False
        self._choices.set_sensitive(True)
        self._search.set_sensitive(True)
        self._continue.set_sensitive(True)
        self._cancel.set_sensitive(True)
        self._close.set_sensitive(True)
        self._tabs.set_sensitive(True)
        self._reminder_pages.set_sensitive(True)
        self._add.set_sensitive(self._notifications is not None and len(self._notifications['reminders']) < 64)
        self._retry.set_sensitive(True)
        set_text(self._error, 'label', m.YOUR_LANGUAGE_COULD_NOT_BE_SAVED_PLEASE_TRY_AGAIN)
        self._error.set_visible(True)
        self._size_to_gateway(self)


# Existing consumers and the startup language-setup public IDs remain valid.
LanguageDialog = PreferencesDialog
