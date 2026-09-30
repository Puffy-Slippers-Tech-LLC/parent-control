"""Host fixtures read configured identities without duplicating deployed names or IDs."""

import json

from tests.support.paths import ROOT


def vm_entry(index=0):
    return json.loads((ROOT / 'config/test-vm.json').read_text())['vms'][index]


def vm_name(index=0):
    return vm_entry(index)['name']
