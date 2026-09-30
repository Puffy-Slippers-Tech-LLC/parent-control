"""Fixed Internet probes and online/offline/recovery sequence, no app assertions."""
import json
from pathlib import Path
from types import SimpleNamespace

from owned_commands import CommandError, require
from vm_internet import InternetIsolation, restore
from watch_activity import operation

# Two independent public DNS operators, with TCP and actual UDP DNS replies.
# IP literals avoid conflating a broken resolver with Internet isolation.
PROBE = '''import json,socket,struct,subprocess
routes=json.loads(subprocess.check_output(["ip","-j","-6","route","show","default"]))
families=[(socket.AF_INET,["1.1.1.1","8.8.8.8"])]
if routes: families.append((socket.AF_INET6,["2606:4700:4700::1111","2001:4860:4860::8888"]))
query=b"\\x19\\x3a\\x01\\x00\\x00\\x01\\x00\\x00\\x00\\x00\\x00\\x00\\x07example\\x03com\\x00\\x00\\x01\\x00\\x01"
result={"ipv6_default_route":bool(routes),"probes":[]}
for family,addresses in families:
 for address in addresses:
  for protocol in ("tcp","udp-dns"):
   success=False
   with socket.socket(family,socket.SOCK_STREAM if protocol=="tcp" else socket.SOCK_DGRAM) as peer:
    peer.settimeout(3)
    try:
     peer.connect((address,53))
     if protocol=="tcp":
      peer.sendall(struct.pack("!H",len(query))+query)
      head=peer.recv(2)
      if len(head)==2:
       data=peer.recv(struct.unpack("!H",head)[0])
       success=len(data)>=12 and data[:2]==query[:2] and bool(data[2]&128)
     else:
      peer.send(query); data=peer.recv(4096)
      success=len(data)>=12 and data[:2]==query[:2] and bool(data[2]&128)
    except (OSError,TimeoutError): pass
   result["probes"].append({"family":4 if family==socket.AF_INET else 6,"address":address,"protocol":protocol,"reachable":success})
print(json.dumps(result))
'''


def internet_result(transport):
    raw = transport.call(['/usr/bin/python3', '-I', '-c', PROBE], timeout=90)
    require(type(raw) is bytes and len(raw) <= 4096, 'internet:probe-output')
    value = json.loads(raw)
    require(type(value) is dict and set(value) == {'ipv6_default_route', 'probes'}
            and type(value['ipv6_default_route']) is bool, 'internet:probe-schema')
    endpoints = [(4, '1.1.1.1'), (4, '8.8.8.8')]
    if value['ipv6_default_route']:
        endpoints += [(6, '2606:4700:4700::1111'), (6, '2001:4860:4860::8888')]
    require(type(value['probes']) is list and len(value['probes']) == len(endpoints) * 2,
            'internet:probe-schema')
    for actual, expected in zip(value['probes'], [(family, address, protocol)
            for family, address in endpoints for protocol in ('tcp', 'udp-dns')]):
        require(type(actual) is dict and set(actual) == {'family', 'address', 'protocol', 'reachable'}
                and (actual['family'], actual['address'], actual['protocol']) == expected
                and type(actual['reachable']) is bool, 'internet:probe-schema')
    return value


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
