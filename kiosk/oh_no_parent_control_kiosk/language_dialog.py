"""The request screens' language chooser, with their own metal-board UI."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for,
)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.languages import SUPPORTED_LANGUAGES, selected_language
from .chrome import ArmoredButton, MetalBoard


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved, cancelled):
        super().__init__(title=m.LANGUAGE, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False, decorated=False)
        set_text(self, 'title', m.LANGUAGE)
        set_automation_id(self, "language-dialog")
        self.add_css_class("oh-no-parent-control-language-dialog")
        self.set_default_size(400, -1)
        self.connect("map", self._size_to_gateway)
        self._save, self._saved = save, saved
        self._cancelled = cancelled
        self._can_cancel = bool(language)
        self._selected = selected_language(language, GLib.get_language_names())
        self._saving = False

        board = MetalBoard(orientation=Gtk.Orientation.VERTICAL)
        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                          margin_start=24, margin_end=24, margin_top=24, margin_bottom=24)
        logo = Gtk.Image.new_from_file(str(branding_asset_path("app_logo.png")))
        logo.set_pixel_size(64)
        accessible_text(logo, [Gtk.AccessibleProperty.LABEL],
                        [m.APP_NAME_S_LOGO % {'app_name': app_name()}])
        content.append(logo)
        title = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE, css_classes=["title-1"])
        set_automation_id(title, "language-title")
        content.append(title)
        description = localized(Gtk.Label, label=m.YOU_CAN_CHANGE_IT_IN_PREFERENCES,
                                wrap=True, justify=Gtk.Justification.CENTER)
        set_automation_id(description, "language-description")
        content.append(description)

        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            choice = localized(Gtk.CheckButton)
            choice.set_direction(Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            label.set_direction(Gtk.TextDirection.LTR)
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
        scroller = Gtk.ScrolledWindow(child=self._choices, vexpand=True,
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=150)
        self._scroller = scroller
        set_automation_id(scroller, "language-list")
        content.append(scroller)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        actions = Gtk.Box(spacing=12, homogeneous=True)
        self._cancel = localized(ArmoredButton, label=m.CANCEL, visible=self._can_cancel)
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
        self.set_default_widget(self._continue)
        self.connect("close-request", lambda *_args: True)
        self._size_to_gateway(self)

    def _size_to_gateway(self, _window):
        # Import after main has finished loading the dialog class.
        from .main import _gateway_inner_corners

        parent = self.get_transient_for()
        width = max(400, self.get_child().measure(Gtk.Orientation.HORIZONTAL, -1)[0])
        list_width = width - 48  # Content's left and right margins.
        # ScrolledWindow's natural height omits the full list. Replace that
        # contribution with the language rows' measured height, not spare space.
        natural_height = (
            self.get_child().measure(Gtk.Orientation.VERTICAL, width)[1]
            - self._scroller.measure(Gtk.Orientation.VERTICAL, list_width)[1]
            + self._choices.measure(Gtk.Orientation.VERTICAL, list_width)[1]
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
            self._selected = identity

    def _submit(self, _button):
        if self._saving:
            return
        self._saving = True
        self._error.set_visible(False)
        self._choices.set_sensitive(False)
        self._continue.set_sensitive(False)
        self._cancel.set_sensitive(False)
        self._save(self._selected, self._success, self._failure)

    def _dismiss(self, _button):
        if self._saving or not self._can_cancel:
            return
        self._cancelled()
        self.destroy()

    def _success(self, language):
        self._saved(language)
        self.destroy()

    def _failure(self, _error):
        self._saving = False
        self._choices.set_sensitive(True)
        self._continue.set_sensitive(True)
        self._cancel.set_sensitive(True)
        set_text(self._error, 'label', m.YOUR_LANGUAGE_COULD_NOT_BE_SAVED_PLEASE_TRY_AGAIN)
        self._error.set_visible(True)
