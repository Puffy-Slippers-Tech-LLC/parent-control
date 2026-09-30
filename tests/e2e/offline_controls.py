"""Shared LIFE06 composition of declared public controls with owned isolation."""
from copy import deepcopy

from private_artifacts import require
from vm_internet import InternetIsolation
from vm_internet_qualification import internet_result
from watch_activity import operation


def offline_controls(journey, guard, *, entry, controls, window):
    """Observe entry, run each input once offline, read its result, then recover.

    The caller owns finite operations and expected projections. Transport,
    isolation lifetime and same-window comparisons belong here. No relaunch,
    replay, private product state or fallback input is permitted.
    """
    def read(name):
        guard()
        value = journey.ui.observe(name)
        require(value['outcome'] == 'passed', 'offline-controls:public-result')
        guard()
        return value

    with operation('Checking Parent controls without Internet access and recovery'):
        initial = read(entry)
        endpoint = deepcopy(read(window)['window'])
        before = internet_result(journey.transport)
        require(all(item['reachable'] for item in before['probes']),
                'offline-controls:online-entry')
        results = []
        with InternetIsolation(journey.context.lease) as isolation:
            guard()
            isolation.enter(journey.transport)
            offline = internet_result(journey.transport)
            require(offline['ipv6_default_route'] == before['ipv6_default_route']
                    and not any(item['reachable'] for item in offline['probes']),
                    'offline-controls:offline-result')
            for input_operation, result_operation, expected in controls:
                require(read(window)['window'] == endpoint,
                        'offline-controls:window-changed')
                submitted = read(input_operation)
                observed = read(result_operation)
                require(observed['save'] == expected, 'offline-controls:control-result')
                require(read(window)['window'] == endpoint,
                        'offline-controls:window-changed')
                results.append({'input': submitted, 'result': observed})
            guard()
        after = internet_result(journey.transport)
        require(after == before, 'offline-controls:online-recovery')
        require(read(window)['window'] == endpoint, 'offline-controls:window-changed')
        return {'entry': initial, 'window': endpoint, 'online_before': before,
                'offline': offline, 'controls': results, 'online_after': after}
