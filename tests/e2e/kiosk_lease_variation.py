"""Finite engineering lease controls inside the caller's installed envelope."""
import json
import system_runner as system


def qualify(transport, lease, *, expectation='refusal'):
    """Qualify the selected refusal, recovery or contention expectation.

    The caller runs the complete short public history after this returns.
    Engineering callbacks alone never supply public usability acceptance.
    """
    import watch_activity
    if expectation not in ('refusal', 'recovery', 'contention'):
        raise ValueError('kiosk-lease:expectation')
    lease.guard()
    with watch_activity.operation('Qualifying owned admission lease and lifecycle writer'):
        raw = transport.call(['env', 'ONPC_EXPECTED_RUN=' + lease.state['run'],
            '/usr/bin/python3', '-B',
            system.PAYLOAD + '/system_kiosk_lease_variation.py',
            *(['contention'] if expectation == 'contention' else
              ['engineering', expectation])], timeout=420)
    if type(raw) is not bytes or not 0 < len(raw) <= 65536:
        raise RuntimeError('kiosk-lease:response-bound')
    result = json.loads(raw)
    if (type(result) is not dict or result.get('qualified') is not True
            or result.get('expectation') != expectation or result.get('restored') is not True):
        raise RuntimeError('kiosk-lease:qualification-result')
    lease.guard()
    return result
