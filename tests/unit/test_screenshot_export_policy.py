"""Execute the actual Polkit rule against allowed and excluded requests."""

import json
from pathlib import Path
import subprocess

import pytest


RULE = Path(__file__).resolve().parents[2] / 'config/50-onpc-screenshot-export.rules'


@pytest.mark.parametrize('override,allowed', [
    ({}, True),
    ({'program': '/usr/bin/install'}, False),
    ({'program': '/usr/bin/python3'}, False),
    ({'program': '/usr/local/libexec/onpc-test-runner'}, False),
    ({'program': '/tmp/onpc-export-screenshot'}, False),
    ({'program': '/usr/local/libexec/onpc-export-screenshot-other'}, False),
    ({'id': 'another.action'}, False),
    ({'user': 'another-user'}, False),
    ({'local': False}, False),
    ({'active': False}, False),
    ({'admin': False}, False),
    ({'program': None}, False),
])
def test_authorization_scope(override, allowed):
    request = dict(id='org.freedesktop.policykit.exec',
                   program='/usr/local/libexec/onpc-export-screenshot',
                   user='root', local=True, active=True, admin=True)
    request.update(override)
    script = '''
const fs = require('fs');
const vm = require('vm');
const request = JSON.parse(process.argv[1]);
let rule;
vm.runInNewContext(fs.readFileSync(process.argv[2], 'utf8'), {
    polkit: {addRule: callback => {rule = callback;}, Result: {YES: 'yes'}}
});
const result = rule({id: request.id, lookup: key => request[key]}, {
    local: request.local, active: request.active,
    isInGroup: group => group === 'sudo' && request.admin
});
process.stdout.write(result === 'yes' ? 'allow' : 'abstain');
'''
    result = subprocess.run(['node', '-e', script, json.dumps(request), str(RULE)],
                            capture_output=True, text=True, check=True)
    assert result.stdout == ('allow' if allowed else 'abstain')
