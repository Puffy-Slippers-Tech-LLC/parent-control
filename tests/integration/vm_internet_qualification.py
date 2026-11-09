"""Fixed Internet probes and online/offline/recovery sequence, no app assertions."""
import json
from pathlib import Path
from types import SimpleNamespace

from owned_commands import CommandError, require
from vm_internet import InternetIsolation, internet_result, restore
from watch_activity import operation


def controller_result(journey, guard):
    guard()
    require(journey.transport.call(['printf', 'ONPC-WATCH-SSH-STDOUT\\n']) ==
            b'ONPC-WATCH-SSH-STDOUT\n', 'internet:controller-command')
    # Observe the public desktop semantically through a fresh SSH connection.
    ui = journey.ui.observe('fresh-parent-desktop')
    require(ui['outcome'] == 'passed', 'internet:public-observation')
    journey.transport.call(['ls', '--', '/onpc-watch-missing-entry'], check=False)
    require(journey.transport.commands.last_returncode != 0, 'internet:stderr-probe')
    with operation('Qualifying VM Internet isolation'):
        watch = json.loads(journey.context.commands.run(['/usr/bin/python3', '-B',
            str(Path(__file__).with_name('e2e_watch_probe.py')), '--internet'], timeout=40))
    guard()
    return {'command': True, 'public_ui': ui, 'watch': watch}


def online_offline_online(journey, guard):
    """Shared finite sequence; an interruption must unwind owned restoration."""
    lease = journey.context.lease
    isolation = InternetIsolation(lease)
    guard()
    # Wrong transport entry must refuse before creating filter/journal resources.
    wrong = SimpleNamespace(config={**journey.transport.config, 'domain_uuid': 'wrong'})
    try:
        isolation.enter(wrong)
    except CommandError as error:
        require(str(error) == 'internet:transport-identity', 'internet:wrong-entry-refusal')
    else:
        require(False, 'internet:wrong-entry-accepted')
    before = internet_result(journey.transport)
    require(all(item['reachable'] for item in before['probes']), 'internet:online-unavailable')
    result = {'wrong_entry_refused': True, 'online_before': before}
    try:
        with isolation:
            isolation.enter(journey.transport)
            try:
                isolation.enter(journey.transport)
            except CommandError as error:
                require(str(error) == 'internet:uncertain-replay', 'internet:replay-refusal')
            else:
                require(False, 'internet:replay-accepted')
            result['replay_refused'] = True
            offline = internet_result(journey.transport)
            require(offline['ipv6_default_route'] == before['ipv6_default_route'] and
                    not any(item['reachable'] for item in offline['probes']), 'internet:isolation-failed')
            result['offline'] = offline
            result['offline_controller'] = controller_result(journey, guard)
            # Exercise the same exception-unwind cleanup used on cooperative
            # cancellation, after independent absence and control observations.
            raise InterruptedError('owned-isolation-qualification')
    except InterruptedError as error:
        require(str(error) == 'owned-isolation-qualification', 'internet:unexpected-interruption')
    guard()
    require(lease.state['internet_isolation']['phase'] == 'restored', 'internet:interruption-cleanup')
    restore(lease)  # Independently verify the completed cleanup is still absent.
    after = internet_result(journey.transport)
    require(after == before, 'internet:restoration-failed')
    result.update(online_after=after, interruption_cleanup=True,
                  online_controller=controller_result(journey, guard))
    return result


def qualify(journey, guard):
    return online_offline_online(journey, guard)
