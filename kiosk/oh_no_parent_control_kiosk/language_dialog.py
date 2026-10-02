"""The request screens' language chooser, with their own metal-board UI."""

from common.oh_no_parent_control_ui import messages as m
from common.oh_no_parent_control_ui.translation_widgets import (
    localized, set_text, accessible_text, context_for, TranslationContext,
)

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import GLib, Gtk, Pango

from common.oh_no_parent_control_ui.accessibility import describe_control, set_automation_id
from common.oh_no_parent_control_ui.about import app_name, branding_asset_path
from common.oh_no_parent_control_ui.languages import (
    SUPPORTED_LANGUAGES, language_direction, language_matches, selected_language,
)
from common.oh_no_parent_control_ui.user_icon import apply_gtk_user_icon
from .chrome import ArmoredButton, MetalBoard


class LanguageDialog(Gtk.Window):
    def __init__(self, parent, language, save, saved, cancelled, *, account=None):
        super().__init__(application=parent.get_application(),
                         title=m.LANGUAGE, transient_for=parent, modal=True,
                         destroy_with_parent=True, deletable=False, decorated=False)
        self._selected = selected_language(language, GLib.get_language_names())
        self._translation_context = TranslationContext(self._selected)
        set_text(self, 'title', m.LANGUAGE)
        set_automation_id(self, "language-dialog")
        self.add_css_class("oh-no-parent-control-language-dialog")
        self.set_default_size(400, -1)
        self.connect("map", self._size_to_gateway)
        self._save, self._saved = save, saved
        self._cancelled = cancelled
        self._saving = False

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
        title = localized(Gtk.Label, label=m.CHOOSE_YOUR_LANGUAGE, xalign=0, wrap=True,
                          css_classes=["oh-no-parent-control-language-title"])
        set_automation_id(title, "language-title")
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
        content.append(header)

        self._search = localized(Gtk.SearchEntry, placeholder_text=m.SEARCH_LANGUAGES)
        describe_control(self._search, m.SEARCH_LANGUAGES, m.SEARCH_LANGUAGES,
                         automation_id="language-search")
        self._search.connect("changed", self._filter_languages)
        content.append(self._search)
        self._choices = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._language_rows = []
        first = None
        for identity, name in SUPPORTED_LANGUAGES:
            choice = localized(Gtk.CheckButton)
            choice.set_direction(Gtk.TextDirection.RTL)
            label = localized(Gtk.Label, label=name, xalign=0, hexpand=True)
            label.set_direction(Gtk.TextDirection.RTL if language_direction(identity) == 'rtl'
                                else Gtk.TextDirection.LTR)
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
                                      hscrollbar_policy=Gtk.PolicyType.NEVER,
                                      overlay_scrolling=False,
                                      min_content_height=1)
        self._scroller = scroller
        set_automation_id(scroller, "language-list")
        content.append(scroller)
        self._error = localized(Gtk.Label, wrap=True, visible=False, css_classes=["error"])
        set_automation_id(self._error, "language-error")
        content.append(self._error)
        actions = Gtk.Box(spacing=12, homogeneous=True)
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
        parent.connect_object("notify::is-active", LanguageDialog._parent_activated, self)
        self._size_to_gateway(self)

    def _filter_languages(self, search):
        for row, identity, name in self._language_rows:
            row.set_visible(language_matches(search.get_text(), identity, name))
        self._scroller.get_vadjustment().set_value(0)

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
        list_width = width - 48  # Content's left and right margins.
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
        if self._saving:
            return
        self._saving = True
        self._error.set_visible(False)
        self._choices.set_sensitive(False)
        self._search.set_sensitive(False)
        self._continue.set_sensitive(False)
        self._cancel.set_sensitive(False)
        self._save(self._selected, self._success, self._failure)

    def _dismiss(self, _button):
        if self._saving:
            return
        self._cancelled()
        self.destroy()

    def _success(self, language):
        self.destroy()
        self._saved(language)

    def _failure(self, _error):
        self._saving = False
        self._choices.set_sensitive(True)
        self._search.set_sensitive(True)
        self._continue.set_sensitive(True)
        self._cancel.set_sensitive(True)
        set_text(self._error, 'label', m.YOUR_LANGUAGE_COULD_NOT_BE_SAVED_PLEASE_TRY_AGAIN)
        self._error.set_visible(True)
        self._size_to_gateway(self)
