"""Refuse the unqualified Shell public-ID search route before input.

Retained search behavior regressions remain in test_accessible_e2e_ui.py.
The fresh Parent route uses a separately scoped external-provider adapter.
"""

from pathlib import Path
import sys

import gi
gi.require_version('Atspi', '2.0')
from gi.repository import Atspi, GLib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from accessible_ui import AccessibleUI, UiError


def main():
    Atspi.set_timeout(2000, 5000)
    ui = AccessibleUI(Atspi, timeout=10, query_errors=(GLib.Error,),
                      dispatch=lambda: GLib.MainContext.default().iteration(False))
    try:
        ui.find_provider_control('gnome-shell', 'desktop', 'launcher')
    except UiError as error:
        if str(error) != 'ui:unqualified-provider-application':
            raise
        print('e2e-search: provider-identity-blocked', flush=True)
        return
    raise AssertionError('Shell provider contract changed; qualify the ID-addressed search route')


if __name__ == '__main__':
    main()
