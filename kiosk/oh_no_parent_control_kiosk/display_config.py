"""Show the kiosk with the selected child's saved desktop resolution and scale.

Mutter keeps each account's layout in ``monitors.xml``; the station account has
its own. The broker returns the selected child's file. The configuration whose
monitors match the connected ones is applied persistently: GNOME Kiosk confirms
it at once and Mutter saves it as the station's layout, so the next station
session starts with it. A layout that already matches the screen is not applied
again, which avoids a mode set and its visible flicker. Mutter
validates every applied value; an unusable saved layout leaves the screen as is.
"""

from __future__ import annotations

import xml.etree.ElementTree as ElementTree

from gi.repository import Gio, GLib

from common.oh_no_parent_control_ui.diagnostic_events import error_code, get_logger

LOG = get_logger('kiosk')
DISPLAY_NAME = 'org.gnome.Mutter.DisplayConfig'
DISPLAY_PATH = '/org/gnome/Mutter/DisplayConfig'
PERSISTENT_METHOD = 2
LAYOUT_MODES = {'logical': 1, 'physical': 2}
ROTATIONS = {'normal': 0, 'left': 1, 'upside_down': 2, 'right': 3}
STATE_SIGNATURE = '(ua((ssss)a(siiddada{sv})a{sv})a(iiduba(ssss)a{sv})a{sv})'
TIMEOUT_MS = 10000


def _text(element, name, default=None, strip=True):
    child = element.find(name)
    if child is None or child.text is None:
        if default is None:
            raise ValueError(f'missing {name}')
        return default
    return child.text.strip() if strip else child.text


def _spec(element):
    # Mutter compares monitor identities exactly.
    return tuple(_text(element, name, '', strip=False)
                 for name in ('connector', 'vendor', 'product', 'serial'))


def _configuration(element):
    layout = element.find('layoutmode')
    layout_mode = None if layout is None else LAYOUT_MODES[(layout.text or '').strip()]
    logical_monitors = []
    specs = [_spec(spec) for spec in element.findall('disabled/monitorspec')]
    for logical in element.findall('logicalmonitor'):
        transform = logical.find('transform')
        rotation = 0 if transform is None else ROTATIONS[_text(transform, 'rotation', 'normal')]
        flipped = transform is not None and _text(transform, 'flipped', 'no') == 'yes'
        monitors = []
        for monitor in logical.findall('monitor'):
            spec, mode = _spec(monitor.find('monitorspec')), monitor.find('mode')
            specs.append(spec)
            monitors.append((spec[0], int(_text(mode, 'width')), int(_text(mode, 'height')),
                             float(_text(mode, 'rate')),
                             _text(mode, 'ratemode', 'fixed') == 'variable',
                             _text(mode, 'flag', '') == 'interlace',
                             _text(monitor, 'underscanning', 'no') == 'yes'))
        if not monitors:
            raise ValueError('empty logical monitor')
        logical_monitors.append((int(_text(logical, 'x')), int(_text(logical, 'y')),
                                 float(_text(logical, 'scale', '1')), rotation + 4 * flipped,
                                 _text(logical, 'primary', 'no') == 'yes', tuple(monitors)))
    if not logical_monitors or len(specs) != len(set(specs)):
        raise ValueError('incomplete configuration')
    return frozenset(specs), layout_mode, tuple(logical_monitors)


def saved_configurations(text):
    """Return each valid saved version-2 configuration; skip unusable ones."""
    root = ElementTree.fromstring(text)
    if root.tag != 'monitors' or root.get('version') != '2':
        return ()
    configurations = []
    for element in root.findall('configuration'):
        try:
            configurations.append(_configuration(element))
        except (AttributeError, KeyError, TypeError, ValueError):
            continue
    return tuple(configurations)


def _mode_id(modes, width, height, rate, variable, interlaced):
    for mode_id, mode_width, mode_height, mode_rate, _preferred, _scales, properties in modes:
        if ((mode_width, mode_height) == (width, height) and abs(mode_rate - rate) < 0.001 and
                (properties.get('refresh-rate-mode') == 'variable') == variable and
                bool(properties.get('is-interlaced', False)) == interlaced):
            return mode_id
    return None


def plan(text, state):
    """Return ``(outcome, arguments)``; arguments are set only for ``applied``.

    ``unchanged`` means the screen already shows the saved layout and must not be
    reconfigured. ``unmatched`` means no saved layout fits the connected monitors.
    """
    serial, monitors, current_logical, properties = state
    modes = {spec[0]: modes for spec, modes, _properties in monitors}
    connected = frozenset(tuple(spec) for spec, _modes, _properties in monitors)
    current_layout = properties.get('layout-mode')
    # Mutter may save one copy per layout mode; prefer the screen's current mode.
    saved = min((item for item in saved_configurations(text) if item[0] == connected),
                key=lambda item: item[1] not in (None, current_layout), default=None)
    if saved is None:
        return 'unmatched', None
    _specs, layout_mode, logical_monitors = saved
    layout_changed = layout_mode is not None and layout_mode != current_layout
    apply_properties = {}
    if properties.get('supports-changing-layout-mode', False):
        # Without this property Mutter uses its default mode, not the current one.
        if layout_mode is not None:
            apply_properties['layout-mode'] = GLib.Variant('u', layout_mode)
    elif layout_changed:
        return 'unmatched', None
    current_modes = {
        spec[0]: next((mode[0] for mode in modes_ if mode[6].get('is-current')), None)
        for spec, modes_, _properties in monitors}
    desired, arguments = set(), []
    for x, y, scale, transform, primary, logical_members in logical_monitors:
        members = []
        for connector, width, height, rate, variable, interlaced, underscanning in logical_members:
            mode_id = _mode_id(modes[connector], width, height, rate, variable, interlaced)
            if mode_id is None:
                return 'unmatched', None
            members.append((connector, mode_id,
                            {'underscanning': GLib.Variant('b', True)} if underscanning else {}))
        arguments.append((x, y, scale, transform, primary, members))
        desired.add((x, y, round(scale, 4), transform, primary,
                     frozenset((connector, mode_id) for connector, mode_id, _ in members)))
    current = {(x, y, round(scale, 4), transform, primary,
                frozenset((spec[0], current_modes.get(spec[0])) for spec in specs))
               for x, y, scale, transform, primary, specs, _properties in current_logical}
    if desired == current and not layout_changed:
        return 'unchanged', None
    return 'applied', GLib.Variant('(uua(iiduba(ssa{sv}))a{sv})',
                                   (serial, PERSISTENT_METHOD, arguments, apply_properties))


class ChildDisplay:
    """Apply one selected child's saved layout; newer selections supersede older."""

    def __init__(self, broker_call):
        self._broker_call = broker_call
        self._revision = 0

    def select(self, target_uid):
        self._revision += 1
        revision = self._revision
        self._broker_call('GetChildMonitorsConfig', GLib.Variant('(u)', (target_uid,)), '(s)',
                          lambda connection, result: self._saved(connection, result, revision))

    def _report(self, outcome, error=None):
        if error is None:
            LOG.info('kiosk.display-config', outcome=outcome, error_type='other')
        else:
            LOG.warning('kiosk.display-config', outcome=outcome, error_type=error_code(error))

    def _saved(self, connection, result, revision):
        if revision != self._revision:
            return
        try:
            text, = connection.call_finish(result).unpack()
            if not text:
                self._report('absent')
                return
            bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
            bus.call(DISPLAY_NAME, DISPLAY_PATH, DISPLAY_NAME, 'GetCurrentState', None,
                     GLib.VariantType(STATE_SIGNATURE), Gio.DBusCallFlags.NONE, TIMEOUT_MS,
                     None, lambda bus, result: self._state(bus, result, text, revision))
        except Exception as error:
            self._report('failed', error)

    def _state(self, bus, result, text, revision):
        if revision != self._revision:
            return
        try:
            outcome, arguments = plan(text, bus.call_finish(result).unpack())
            if arguments is None:
                self._report(outcome)
                return
            bus.call(DISPLAY_NAME, DISPLAY_PATH, DISPLAY_NAME, 'ApplyMonitorsConfig', arguments,
                     None, Gio.DBusCallFlags.NONE, TIMEOUT_MS, None, self._applied)
        except Exception as error:
            self._report('failed', error)

    def _applied(self, bus, result):
        try:
            bus.call_finish(result)
        except Exception as error:
            self._report('failed', error)
        else:
            self._report('applied')
