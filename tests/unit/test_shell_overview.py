"""The retained direct-Shell helper refuses before any state operation."""

from unittest.mock import Mock

import pytest

from tests.ui import shell_overview


@pytest.mark.parametrize('active', [True, False])
def test_direct_overview_state_route_is_always_refused(active):
    wait = Mock(side_effect=AssertionError('wait must not run'))
    with pytest.raises(RuntimeError, match='ID-addressed public Shell interaction'):
        shell_overview.set_overview(active, wait)
    wait.assert_not_called()
