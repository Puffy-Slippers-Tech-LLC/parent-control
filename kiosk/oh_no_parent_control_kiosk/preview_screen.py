"""Screen choices and the preview-only dialog; no host display configuration."""

from dataclasses import dataclass
import json
import os
import socket
import sys
import threading

RESOLUTIONS = (
    (1280, 720), (1366, 768), (1600, 900), (1920, 1080), (1920, 1200),
    (1920, 1280), (2240, 1400), (2256, 1504), (2560, 1440), (2560, 1600),
    (2880, 1800), (3000, 2000), (3200, 1800), (3200, 2000), (3440, 1440),
    (3840, 2160), (3840, 2400), (5120, 1440), (5120, 2160), (5120, 2880),
    (6016, 3384), (7680, 4320),
)
SCALES = tuple(range(100, 401, 25))
CONTROL_FD = "ONPC_PREVIEW_SCREEN_FD"
SCREEN = "ONPC_PREVIEW_SCREEN"
ACTUAL_SCALE = "ONPC_PREVIEW_SCREEN_SCALE"


@dataclass(frozen=True)
class Screen:
    width: int = 1920
    height: int = 1080
    percent: int = 100

    def __post_init__(self):
        if (type(self.width) is not int or type(self.height) is not int
                or not 480 <= self.width <= 7680 or not 480 <= self.height <= 7680
                or self.width * self.height > 7680 * 4320):
            raise ValueError("Enter whole pixel dimensions from 480 to 7680 (up to 8K total pixels).")
        if type(self.percent) is not int or self.percent not in SCALES:
            raise ValueError("Choose a display scale from the list.")

    def encode(self):
        return json.dumps([self.width, self.height, self.percent])

    @classmethod
    def decode(cls, value):
        return cls(*json.loads(value))


def notify_screen_ready(window):
    """Acknowledge only a compositor-configured fullscreen GTK surface."""
    from gi.repository import GLib

    screen = Screen.decode(os.environ[SCREEN])
    scale = float(os.environ[ACTUAL_SCALE])
    surface = window.get_surface()
    if (not window.is_fullscreen() or surface is None
            or window.get_width() != round(screen.width / scale)
            or window.get_height() != round(screen.height / scale)
            # The Wayland fractional-scale protocol quantizes to 1/120.
            or abs(surface.get_scale() - scale) > 1 / 120):
        return GLib.SOURCE_CONTINUE
    with socket.socket(fileno=os.dup(int(os.environ[CONTROL_FD]))) as connection:
        connection.send(b"ready")
    return GLib.SOURCE_REMOVE


def show_screen_dialog(window):
    """Keep GTK imports out of the supervisor and validation tests."""
    from gi.repository import Adw, GLib, Gtk
    from common.oh_no_parent_control_ui.accessibility import describe_control

    current = Screen.decode(os.environ[SCREEN]) if SCREEN in os.environ else Screen()
    dialog = Adw.Dialog(title="Change Screens", content_width=460, content_height=620)
    toolbar = Adw.ToolbarView()
    toolbar.add_top_bar(Adw.HeaderBar())
    body = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12,
                   margin_start=20, margin_end=20, margin_top=12, margin_bottom=20)
    body.append(Gtk.Label(label="Screen resolution", xalign=0))
    resolutions = Gtk.ListBox(selection_mode=Gtk.SelectionMode.SINGLE)
    resolutions.add_css_class("boxed-list")
    selected = None
    for width, height in RESOLUTIONS:
        row = Gtk.ListBoxRow()
        row.set_child(Gtk.Label(label=f"{width} × {height}", xalign=0,
                               margin_start=12, margin_end=12,
                               margin_top=8, margin_bottom=8))
        resolutions.append(row)
        if (width, height) == (current.width, current.height):
            selected = row
    custom = Gtk.ListBoxRow()
    custom.set_child(Gtk.Label(label="Custom resolution", xalign=0,
                              margin_start=12, margin_top=8, margin_bottom=8))
    resolutions.append(custom)
    scroll = Gtk.ScrolledWindow(vexpand=True, min_content_height=140,
                               hscrollbar_policy=Gtk.PolicyType.NEVER)
    scroll.set_child(resolutions)
    body.append(scroll)
    custom_fields = Gtk.Box(spacing=8)
    width_entry = Gtk.Entry(text=str(current.width), hexpand=True,
                            input_purpose=Gtk.InputPurpose.DIGITS, width_chars=6)
    height_entry = Gtk.Entry(text=str(current.height), hexpand=True,
                             input_purpose=Gtk.InputPurpose.DIGITS, width_chars=6)
    describe_control(width_entry, "Screen width", "Width in physical pixels.")
    describe_control(height_entry, "Screen height", "Height in physical pixels.")
    custom_fields.append(width_entry)
    custom_fields.append(Gtk.Label(label="×"))
    custom_fields.append(height_entry)
    body.append(custom_fields)
    resolutions.connect("row-selected", lambda _list, row: custom_fields.set_visible(row is custom))
    resolutions.select_row(selected or custom)
    scale_label = Gtk.Label(label="Display Scale", xalign=0)
    body.append(scale_label)
    scale = Gtk.DropDown.new_from_strings([
        "100% (default)" if percent == 100 else f"{percent}%" for percent in SCALES
    ])
    scale.set_selected(SCALES.index(current.percent))
    scale_label.set_mnemonic_widget(scale)
    describe_control(scale, "Display Scale", "Ubuntu display scale for the preview screen.")
    body.append(scale)
    body.append(Gtk.Label(
        label="Saving reopens the preview on the selected screen. The viewer can fit a large screen into your desktop.",
        wrap=True, xalign=0,
    ))
    status = Gtk.Label(wrap=True, xalign=0, visible=False)
    status.add_css_class("error")
    body.append(status)
    actions = Gtk.Box(spacing=12, halign=Gtk.Align.END)
    cancel = Gtk.Button(label="Cancel")
    cancel.connect("clicked", lambda *_: dialog.close())
    save = Gtk.Button(label="Save", css_classes=["suggested-action"])
    actions.append(cancel)
    actions.append(save)
    body.append(actions)
    dialog_scroll = Gtk.ScrolledWindow(hscrollbar_policy=Gtk.PolicyType.NEVER)
    dialog_scroll.set_child(body)
    toolbar.set_content(dialog_scroll)
    dialog.set_child(toolbar)

    def failed(message):
        status.set_text(message)
        status.set_visible(True)
        save.set_sensitive(True)
        dialog.set_can_close(True)
        cancel.set_sensitive(True)
        return GLib.SOURCE_REMOVE

    def submit(_button):
        try:
            row = resolutions.get_selected_row()
            if row is custom:
                try:
                    dimensions = (int(width_entry.get_text()), int(height_entry.get_text()))
                except ValueError:
                    raise ValueError("Enter a whole number for both width and height.") from None
            else:
                dimensions = RESOLUTIONS[row.get_index()]
            screen = Screen(*dimensions, SCALES[scale.get_selected()])
        except ValueError as error:
            failed(str(error))
            return
        if CONTROL_FD not in os.environ:
            # A plain --preview window (including the nested child launcher)
            # can enter the same supported display preview by replacing itself.
            args = [sys.executable, "-m", "oh_no_parent_control_kiosk.preview",
                    "--screen", screen.encode()]
            if window._child_overlay:
                args.append("--child-overlay")
            os.execv(sys.executable, args)
        save.set_sensitive(False)
        cancel.set_sensitive(False)
        dialog.set_can_close(False)
        status.set_text("Opening preview screen…")
        status.set_visible(True)

        def request():
            try:
                # Duplicate the inherited socket: closing the worker's handle
                # must not close the descriptor retained across live reloads.
                with socket.socket(fileno=os.dup(int(os.environ[CONTROL_FD]))) as connection:
                    connection.settimeout(90)
                    connection.sendall(screen.encode().encode())
                    reply = connection.recv(4096).decode()
                if reply != "ok":
                    GLib.idle_add(failed, reply or "The preview launcher closed.")
            except (OSError, ValueError):
                GLib.idle_add(failed, "Could not open the preview screen. Check the preview terminal.")

        threading.Thread(target=request, daemon=True).start()

    save.connect("clicked", submit)
    dialog.present(window)
