"""Host fixtures read configured identities without duplicating deployed names or IDs."""

import vm_config
from tests.support.paths import ROOT


def vm_name(index=0, *, fixture_path=None):
    return [vm.name for vm in vm_config.registry(ROOT / 'config/environment.json').values()
            if fixture_path is None or vm.fixture_path == fixture_path][index]
