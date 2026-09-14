"""Pure, test-only correlation of a native witness and fapolicyd syslog.

This is NOT an activation receipt. The caller must obtain journal entries from
the local journal and bracket the probe with independently captured backend
inputs. No collector, policy writer, process operation or product hook lives
here. Equal snapshots cannot exclude an intervening change and restoration.
"""

from dataclasses import dataclass
import hashlib
import re


ROOT = '/run/oh-no-parent-control/probes'
SYSLOG_FORMAT = 'rule,dec,perm,pid,uid,:,path'
_ID = re.compile(r'[0-9a-f]{32}')
_HASH = re.compile(r'[0-9a-f]{64}')
_RULE = re.compile(
    r'(?:allow|deny|allow_syslog|deny_syslog) perm=execute '
    r'(?:all|uid=(?:0|[1-9][0-9]{0,9})) : (?:all|path=/[A-Za-z0-9_./-]+)')
_MESSAGE = re.compile(
    r'rule=([1-9][0-9]{0,9}) dec=allow_syslog perm=execute '
    r'pid=([1-9][0-9]{0,9}) uid=0 : '
    r'path=(/run/oh-no-parent-control/probes/[0-9a-f]{32}/witness)')


class DecisionRefused(ValueError):
    """Fixed reason only: never echo journal fields, paths or account data."""


def _require(condition, reason):
    if not condition:
        raise DecisionRefused(reason)


def _identifier(value):
    return isinstance(value, str) and _ID.fullmatch(value) and value != '0' * 32


@dataclass(frozen=True)
class BackendInputs:
    boot: str
    invocation: str
    pid: int
    executable_sha256: str
    compiled: bytes
    config: bytes
    active_state: str
    legacy_rules_present: bool


@dataclass(frozen=True)
class PositiveDecision:
    """A correlated observation only; deliberately has no activation flag."""

    generation: str
    witness_sha256: str
    compiled_sha256: str
    config_sha256: str
    boot: str
    daemon_pid: int
    daemon_sha256: str
    daemon_invocation: str
    probe_invocation: str
    peer_pid: int
    rule_number: int
    cursor: str


def _positive_rule(compiled, witness):
    # Qualify only a small controlled fixture grammar. Do not imitate the full
    # daemon parser or count a physical line number as a decision rule number.
    _require(type(compiled) is bytes and 0 < len(compiled) <= 1024 * 1024,
             'compiled-input-invalid')
    try:
        lines = compiled.decode('ascii').split('\n')
    except UnicodeError:
        raise DecisionRefused('compiled-input-invalid') from None
    expected = f'allow_syslog perm=execute uid=0 : path={witness}'
    rules = []
    for line in lines:
        if not line or line.startswith('#'):
            continue
        _require(_RULE.fullmatch(line) is not None, 'compiled-grammar-unqualified')
        rules.append(line)
    _require(rules.count(expected) == 1, 'generation-rule-missing-or-duplicate')
    return rules.index(expected) + 1


def bind_positive_decision(entry, *, before, after, probe, start_usec, end_usec):
    """Bind one independently collected entry; refuse ambiguity or mismatch.

    Times bound journal *reception*, not exec. The fresh single-use generation
    and admitted peer supply causal coordinates. An external collector must
    retain cursor ordering/completeness and reject multiple candidate records.
    """
    _require(type(before) is BackendInputs and type(after) is BackendInputs,
             'backend-input-invalid')
    _require(before == after, 'backend-input-changed')
    _require(_identifier(before.boot) and _identifier(before.invocation) and
             type(before.pid) is int and 0 < before.pid < 2**31 and
             isinstance(before.executable_sha256, str) and
             _HASH.fullmatch(before.executable_sha256) and
             before.active_state == 'active' and before.legacy_rules_present is False,
             'backend-identity-unproven')
    _require(type(before.config) is bytes and 0 < len(before.config) <= 65536,
             'backend-config-invalid')
    # Require explicit, single settings. Defaults or duplicate directives are
    # not evidence of the running daemon's mode; live qualification stays open.
    settings = {'permissive': [], 'syslog_format': []}
    try:
        for line in before.config.decode('ascii').splitlines():
            name, separator, value = line.partition('=')
            if separator and name.strip() in settings:
                settings[name.strip()].append(value.strip())
    except UnicodeError:
        raise DecisionRefused('backend-config-invalid') from None
    _require(settings == {'permissive': ['0'], 'syslog_format': [SYSLOG_FORMAT]},
             'backend-config-unqualified')
    _require(type(start_usec) is int and type(end_usec) is int and
             0 <= start_usec < end_usec, 'observation-window-invalid')

    generation = probe.generation
    admission = probe.admission
    _require(generation is not None and admission is not None, 'native-binding-missing')
    _require(_identifier(generation.token) and
             generation.directory == f'{ROOT}/{generation.token}' and
             generation.witness == f'{generation.directory}/witness' and
             isinstance(generation.sha256, str) and _HASH.fullmatch(generation.sha256),
             'generation-identity-invalid')
    _require(probe.native_verified is True and probe.terminal_observed is True and
             probe.cleanup_complete is True and probe.client_closed is True and
             probe.reference_released is True and probe.create_outcome == 'replied' and
             probe.outcome == 'identity-unproven' and probe.channel_result == 'executed' and
             probe.exit_code == 1 and probe.exit_status == 23 and
             probe.job_timeout_usec == 4_000_000 and
             probe.service_result == 'exit-code', 'native-execution-unproven')
    _require(_identifier(probe.invocation) and
             admission.peer.invocation == probe.invocation and admission.peer.uid == 0 and
             type(admission.peer.pid) is int and 0 < admission.peer.pid < 2**31 and
             admission.manager == probe.manager and re.fullmatch(r':[0-9]+\.[0-9]+', probe.manager) and
             admission.unit == probe.unit == f'onpc-execution-probe-{generation.token}.service' and
             admission.job == probe.job and
             re.fullmatch(r'/org/freedesktop/systemd1/job/[1-9][0-9]*', probe.job),
             'native-binding-mismatch')
    rule_number = _positive_rule(before.compiled, generation.witness)

    _require(type(entry) is dict, 'journal-entry-invalid')
    expected = {
        '_BOOT_ID': before.boot, '_SYSTEMD_INVOCATION_ID': before.invocation,
        '_PID': str(before.pid), '_UID': '0', '_EXE': '/usr/sbin/fapolicyd',
        '_SYSTEMD_UNIT': 'fapolicyd.service', '_TRANSPORT': 'syslog',
    }
    # journalctl JSON represents repeated/binary fields as arrays: equality to
    # an exact string rejects them, rather than selecting a convenient value.
    _require(all(entry.get(key) == value for key, value in expected.items()),
             'journal-origin-mismatch')
    stamp = entry.get('__MONOTONIC_TIMESTAMP')
    cursor = entry.get('__CURSOR')
    _require(isinstance(stamp, str) and re.fullmatch(r'[0-9]{1,20}', stamp) and
             start_usec <= int(stamp) <= end_usec, 'journal-window-mismatch')
    _require(isinstance(cursor, str) and 0 < len(cursor) <= 1024 and
             all(33 <= ord(char) <= 126 for char in cursor), 'journal-cursor-invalid')
    message = entry.get('MESSAGE')
    _require(isinstance(message, str) and len(message) < 512, 'decision-message-invalid')
    match = _MESSAGE.fullmatch(message)
    _require(match is not None, 'decision-message-invalid')
    _require(int(match[1]) == rule_number and int(match[2]) == admission.peer.pid and
             match[3] == generation.witness, 'decision-binding-mismatch')
    return PositiveDecision(
        generation.token, generation.sha256, hashlib.sha256(before.compiled).hexdigest(),
        hashlib.sha256(before.config).hexdigest(), before.boot, before.pid,
        before.executable_sha256, before.invocation, probe.invocation,
        admission.peer.pid, rule_number, cursor)
