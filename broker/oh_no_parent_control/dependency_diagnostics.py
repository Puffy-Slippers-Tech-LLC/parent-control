"""Read-only, closed-field observations of runtime dependencies for feedback.

Journal messages are inspected transiently, never attached or logged verbatim.
Invocation identifiers only relate journal entries to the observed service;
they are not emitted. Earlier attempts on this boot remain available after
automatic recovery or a manual restart.
"""

from datetime import datetime, timezone
import json
import os
import re
import selectors
import subprocess
import time

from common.oh_no_parent_control_ui.diagnostic_events import get_logger
from . import config

LOG = get_logger("execution-policy")
MAX_OUTPUT = 256 * 1024
DEPENDENCIES = {"fapolicyd.service": "fapolicyd",
                "accounts-daemon.service": "accounts-service",
                "polkit.service": "polkit", "systemd-logind.service": "logind"}
PROPERTIES = ("Id", "LoadState", "ActiveState", "Result", "ExecMainCode", "ExecMainStatus",
              "Restart", "NRestarts", "InvocationID")
KIOSK_LOG = get_logger("kiosk")
KIOSK_APP_UNIT = "oh-no-parent-control-app.service"
ADMISSION_STAGES = (
    'arguments', 'identity', 'attestation', 'payload', 'enforcement', 'executable-inventory',
    'privileged-inventory', 'directory-layout', 'manager-generation', 'runtime', 'recovery',
    'generation-create', 'generation-verify', 'bindings')
ADMISSION_REASONS = (
    'invalid-caller', 'invalid-arguments', 'unowned-account', 'substituted-path',
    'untrusted-path', 'untrusted-ancestor', 'unexpected-file-type', 'unexpected-executable-mode',
    'non-native-executable', 'source-changed', 'invalid-executable-substitution',
    'missing-executable', 'conflicting-executable-roles', 'unexpected-preserved-executable',
    'preserved-executable-label', 'preserved-executable-changed', 'preserved-executable-layout',
    'inventory-outside-usr', 'unsafe-directory-entry', 'directory-inventory-too-large',
    'directory-generation-changed', 'selinux-not-enforcing', 'selinux-query-unavailable',
    'selinux-domain-not-enforcing', 'apparmor-not-enforcing', 'unknown-backend',
    'manager-unavailable', 'manager-identity', 'manager-not-confined', 'manager-exited',
    'mounted-preparation', 'linked-preparation', 'unknown-preparation-file', 'unowned-preparation',
    'policy-snapshot-not-attested', 'runtime-mode', 'executable-inventory-too-large',
    'copy-changed', 'generation-changed', 'executable-label-changed',
    'stale-manager-reboot-required', 'generation-limit-reboot-required', 'verification',
    'command-timeout', 'command-failed', 'os-error')


def _run_bounded(command, timeout):
    """Cap both pipes while reading; always reap the command we launched."""
    deadline = time.monotonic() + timeout
    output, errors = bytearray(), bytearray()
    with subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, bufsize=0,
                          env={**os.environ, "LC_ALL": "C"}) as process:
        try:
            with selectors.DefaultSelector() as selector:
                for stream, buffer in ((process.stdout, output), (process.stderr, errors)):
                    os.set_blocking(stream.fileno(), False)
                    selector.register(stream, selectors.EVENT_READ, buffer)
                while selector.get_map():
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise TimeoutError()
                    for key, _events in selector.select(remaining):
                        chunk = os.read(key.fd, min(65536, MAX_OUTPUT + 1 - len(output) - len(errors)))
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        key.data.extend(chunk)
                        if len(output) + len(errors) > MAX_OUTPUT:
                            raise ValueError()
            status = process.wait(timeout=max(0, deadline - time.monotonic()))
        except BaseException:
            process.kill()
            process.wait()
            raise
    return subprocess.CompletedProcess(command, status, output.decode("utf-8"), errors.decode("utf-8"))


def _query(command, deadline, *, empty_match=False):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError()
    result = _run_bounded(command, min(3, remaining))
    no_matches = empty_match and result.returncode == 1 and not result.stdout and not result.stderr
    if (result.returncode != 0 and not no_matches) or len(result.stdout) > MAX_OUTPUT:
        raise ValueError()
    return result.stdout


def _category(value, choices):
    return value if value in choices else "unknown"


def _number(value, maximum):
    if type(value) is str and re.fullmatch(r"[0-9]{1,10}", value):
        number = int(value)
        if number <= maximum:
            return number
    return maximum + 1


def _journal_event(message):
    # Exact shipped-daemon markers only. No generic error/path extraction.
    if message == "Updating trust database":
        return "trust-update-started", 0
    if message == "Cannot update trust database!":
        return "trust-update-failed", 0
    if message == "db_max_size needs to be increased":
        return "trust-capacity-exhausted", 0
    if type(message) is str:
        match = re.fullmatch(r"Cannot delete database \(([1-4])\)", message)
        if match:
            return "trust-delete-failed", int(match[1])
    return None


def _service_states(output):
    states = {}
    for block in output.strip().split("\n\n"):
        properties = {}
        for line in block.splitlines():
            key, separator, value = line.partition("=")
            if separator and key in PROPERTIES and key not in properties:
                properties[key] = value
            else:
                raise ValueError()
        if properties.keys() != set(PROPERTIES):
            raise ValueError()
        unit = properties["Id"]
        if unit not in DEPENDENCIES or unit in states:
            raise ValueError()
        states[unit] = properties
    if states.keys() != DEPENDENCIES.keys():
        raise ValueError()
    return states


def collect_dependency_diagnostics():
    """Best effort, five-second budget; no service/database/policy mutations.

    Always runs during feedback collection, including diagnostics-only mode. A
    failed source is explicit and cannot prevent the customer report from opening.
    """
    deadline = time.monotonic() + 5
    invocation = None
    try:
        output = _query([
            "/usr/bin/systemctl", "show", *DEPENDENCIES, "--no-pager",
            "--property=" + ",".join(PROPERTIES),
        ], deadline)
        states = _service_states(output)
        candidate = states["fapolicyd.service"]["InvocationID"]
        if re.fullmatch(r"[0-9a-f]{32}", candidate):
            invocation = candidate
        for unit, properties in states.items():
            LOG.info(
                "execution-policy.backend-state",
                dependency=DEPENDENCIES[unit],
                loaded=_category(properties["LoadState"], (
                    "loaded", "not-found", "masked", "error", "bad-setting")),
                active=_category(properties["ActiveState"], (
                    "active", "inactive", "failed", "activating", "deactivating", "reloading")),
                result=_category(properties["Result"], (
                    "success", "exit-code", "signal", "core-dump", "timeout", "oom-kill",
                    "start-limit-hit", "resources", "protocol", "watchdog")),
                restart=_category(properties["Restart"], (
                    "no", "always", "on-success", "on-failure", "on-abnormal", "on-abort", "on-watchdog")),
                exit_kind={"0": "none", "1": "exited", "2": "killed", "3": "dumped"}.get(
                    properties["ExecMainCode"], "unknown"),
                exit_status=_number(properties["ExecMainStatus"], 255),
                restarts=_number(properties["NRestarts"], 2147483646),
            )
    except Exception:
        LOG.warning("execution-policy.backend-observation", source="service", outcome="unavailable", count=0)
    try:
        output = _query([
            "/usr/bin/journalctl", "--unit=fapolicyd.service", "--no-pager", "--quiet",
            "--output=json", "--lines=200", "--since=-24hours", "--boot=0",
            "--output-fields=MESSAGE,__REALTIME_TIMESTAMP,_SYSTEMD_INVOCATION_ID,_EXE",
            "--grep=^(Updating trust database|Cannot update trust database!|"
            "Cannot delete database \\([1-4]\\)|db_max_size needs to be increased)$",
        ], deadline, empty_match=True)
        selected = []
        partial = invocation is None
        lines = output.splitlines()
        for line in lines:
            try:
                item = json.loads(line)
                if (type(item) is not dict or
                        item.get("_EXE") not in ("/usr/sbin/fapolicyd", "/usr/bin/fapolicyd")):
                    continue
                source_invocation = item.get("_SYSTEMD_INVOCATION_ID")
                if (type(source_invocation) is not str or
                        not re.fullmatch(r"[0-9a-f]{32}", source_invocation)):
                    partial = True
                    continue
                marker = _journal_event(item.get("MESSAGE"))
                if marker is None:
                    continue
                stamp = item.get("__REALTIME_TIMESTAMP")
                if type(stamp) is not str or not re.fullmatch(r"[0-9]{1,17}", stamp):
                    raise ValueError()
                occurred = datetime.fromtimestamp(int(stamp) / 1000000, timezone.utc)
                selected.append((marker, occurred.isoformat(timespec="milliseconds"),
                                 ("other" if invocation is None else
                                  "current" if source_invocation == invocation else "previous")))
            except (ValueError, TypeError, OverflowError, OSError):
                partial = True
        # A full tail may have omitted earlier evidence. Never claim completeness.
        partial = partial or len(lines) >= 200 or len(selected) > 20
        for (reason, code), occurred, relation in selected[-20:]:
            LOG.info("execution-policy.backend-journal", reason=reason,
                     diagnostic_code=code, occurred_at=occurred, invocation_relation=relation)
        LOG.info("execution-policy.backend-observation", source="journal",
                 outcome="partial" if partial else "complete", count=min(len(selected), 20))
    except Exception:
        LOG.warning("execution-policy.backend-observation", source="journal", outcome="unavailable", count=0)


def notification_error_reason(stderr):
    """Reduce the CLI's C-locale FIFO errors to closed categories."""
    if type(stderr) is not str or len(stderr) > 8192:
        return "other"
    for reason, suffix in (("notification-endpoint-missing", "No such file or directory"),
                           ("notification-permission-denied", "Permission denied"),
                           ("notification-reader-missing", "No such device or address")):
        if stderr.strip() == "Open: /run/fapolicyd/fapolicyd.fifo -> " + suffix:
            return reason
    return "other"


def _kiosk_renderer_event(item, uid):
    if (item.get("_UID") != str(uid) or item.get("_SYSTEMD_USER_UNIT") != KIOSK_APP_UNIT
            or type(item.get("_EXE")) is not str
            or not re.fullmatch(r"/usr/bin/python3(?:\.[0-9]{1,2})?", item["_EXE"])):
        return None
    message = item.get("MESSAGE")
    if type(message) is not str:
        return None
    if re.fullmatch(r"Vulkan: [A-Za-z0-9_./-]+:[0-9]{1,6}: mmap failed: Permission denied "
                    r"\(VK_ERROR_MEMORY_MAP_FAILED\)", message):
        return "vulkan-mmap-permission-denied", "none", 0
    if message == ("vkCreateDevice(): Mapping of a memory object has failed. "
                   "(VK_ERROR_MEMORY_MAP_FAILED) (-5)"):
        return "vulkan-device-map-failed", "none", 0
    return None


def _kiosk_security_event(item, renderer_pids):
    message = item.get("MESSAGE")
    transport = item.get("_TRANSPORT")
    if type(message) is not str or transport not in ("audit", "kernel"):
        return None
    # Audit provenance and the anchored context suffix prevent application text
    # or a filename containing policy-looking text from becoming a denial event.
    if re.fullmatch(
            r"(?:AVC |audit: type=1400 audit\([0-9.:]+\): )?avc:\s+denied\s+"
            r"\{\s*map\s*\}\s+for\s+pid=[0-9]{1,10}\s+.* "
            r"scontext=system_u:system_r:onpc_kiosk_app_t:s0 "
            r"tcontext=system_u:object_r:dri_device_t:s0 tclass=chr_file permissive=0", message):
        return "selinux-gpu-map-denied", "none", 0
    if transport == "kernel":
        match = re.fullmatch(
            r"python3(?:\.[0-9]{1,2})?\[([0-9]{1,10})\]: segfault .* "
            r"in libgallium-[0-9.]+\.so\[.*", message)
        if match and match[1] in renderer_pids:
            return "mesa-segfault", "none", 0
    return None


def _kiosk_session_event(item, uid):
    if (item.get("_UID") != str(uid) or item.get("_COMM") != "systemd"
            or item.get("_EXE") not in ("/usr/lib/systemd/systemd", "/lib/systemd/systemd")):
        return None
    message = item.get("MESSAGE")
    if type(message) is not str:
        return None
    match = re.fullmatch(re.escape(KIOSK_APP_UNIT) + r": Main process exited, "
                         r"code=(exited|killed|dumped), status=([0-9]{1,3})(?:/[A-Z0-9_-]+)?", message)
    if match and int(match[2]) <= 255:
        return "app-exit", match[1], int(match[2])
    reason = {
        KIOSK_APP_UNIT + ": Failed with result 'core-dump'.": "app-core-dump",
        KIOSK_APP_UNIT + ": Triggering OnFailure= dependencies.": "app-failure-shutdown",
        "Stopped target gnome-session@oh-no-parent-control.target - "
        "GNOME Session (session: oh-no-parent-control).": "session-stopped",
    }.get(message)
    return (reason, "none", 0) if reason else None


def _admission_marker(item):
    """Parse exact reviewed producers; journal identities never leave this function."""
    if item.get('_UID') != '0' or item.get('_TRANSPORT') not in ('journal', 'syslog', 'stdout'):
        return None
    message, executable = item.get('MESSAGE'), item.get('_EXE')
    if type(message) is not str or type(executable) is not str:
        return None
    fields = dict(source='pam', role='none', stage='authentication', outcome='allowed',
                  reason='none', session='unknown', transport='unknown', recovery='none',
                  status=-256, errno=-1, line=0, count=0)
    native = executable in ('/usr/libexec/gdm-session-worker', '/usr/lib/gdm3/gdm-session-worker',
                            '/usr/lib/gdm/gdm-session-worker', '/usr/lib/systemd/systemd-executor',
                            '/lib/systemd/systemd-executor')
    if native:
        if message == ('pam_unix(gdm-password:auth): user [oh-no-parent-control] has blank '
                       'password; authenticated without it') and 'gdm-session-worker' in executable:
            fields.update(source='authentication', role='gate', reason='passwordless-authenticated')
            return 'kiosk.admission-journal', fields
        wrapper = re.fullmatch(
            r'pam_oh_no_parent_control\((gdm-password|systemd-user):(account|session)\): (.+)', message)
        if wrapper is None:
            return None
        if (wrapper[1] == 'gdm-password') != ('gdm-session-worker' in executable):
            return None
        fields['role'] = 'gate' if wrapper[1] == 'gdm-password' else 'manager'
        message = wrapper[3]
        cause = re.fullmatch(
            r'onpc.pam kiosk native-view outcome=(denied|cleanup-failed) role=(manager|gate) '
            r'stage=(namespace|staging|manifest|structure|source|bind|attach|readonly|detach) '
            r'reason=(manifest|metadata|identity|namespace|mount|readonly|detach) '
            r'errno=(-1|[1-9][0-9]{0,3})', message)
        if cause:
            if (wrapper[2] != 'session' or cause[2] != fields['role']
                    or int(cause[5]) > 4095):
                return None
            fields.update(source='native-view', outcome=cause[1], stage=cause[3],
                          reason=cause[4], errno=int(cause[5]))
            return 'kiosk.admission-journal', fields
        match = re.fullmatch(
            r'onpc.pam kiosk confinement stage=(account|session) outcome=(allowed|denied) status=([0-9]{1,3})',
            message)
        if match and int(match[3]) <= 255:
            fields.update(stage=match[1], outcome=match[2], status=int(match[3]))
        else:
            match = re.fullmatch(
                r'onpc.pam kiosk confinement stage=(service|lock|account|integrity|session) '
                r'outcome=(denied|unsafe|busy|helper-failed|helper-timeout|unbound)', message)
            if match and ((match[1], match[2]) in (
                    ('service', 'denied'), ('lock', 'unsafe'), ('lock', 'busy'), ('session', 'unbound'))
                    or match[1] in ('account', 'integrity', 'session')
                    and match[2] in ('helper-failed', 'helper-timeout')):
                fields.update(stage=match[1], outcome=match[2])
            else:
                match = re.fullmatch(
                    r'onpc.pam kiosk execution-boundary outcome=(armed|denied) '
                    r'stage=(identity|admission|lock|runtime|prepare|bind|environment|ambient|mac|armed)',
                    message)
                if match:
                    fields.update(stage=match[2], outcome=match[1])
                elif message == 'onpc.pam kiosk admission outcome=denied stage=removal-barrier':
                    fields.update(stage='removal-barrier', outcome='denied')
                else:
                    return None
        return 'kiosk.admission-journal', fields
    if (not re.fullmatch(r'/usr/bin/python3(?:\.[0-9]{1,2})?', executable)
            or item.get('_COMM') != 'oh-no-parent-co'):
        return None
    identifier, unit = item.get('SYSLOG_IDENTIFIER'), item.get('_SYSTEMD_UNIT')
    if identifier == 'oh-no-parent-control-login-check':
        match = re.fullmatch(
            r'onpc.pam kiosk routing stage=(account|session|confinement|service) '
            r'outcome=(allowed|denied|unavailable) session=(unknown|dedicated|other|unset) '
            r'type=(unknown|wayland|other|unset) recovery=(none|restored|failed) '
            r'reason=(none|timeout|bus-failed|identity|verification|unavailable|integration)', message)
        if match is None:
            return None
        fields.update(source='routing', role='gate', stage=match[1], outcome=match[2],
                      session=match[3], transport=match[4], recovery=match[5], reason=match[6])
        return 'kiosk.admission-journal', fields
    if type(unit) is not str or identifier not in ('systemd', 'gdm-session-worker'):
        return None
    if re.fullmatch(r'user@[0-9]{1,10}\.service', unit):
        role = 'manager'
    elif re.fullmatch(r'session-[0-9]{1,10}\.scope', unit):
        role = 'gate'
    else:
        return None
    match = re.fullmatch(
        r'onpc.kiosk confinement preparation outcome=denied role=(manager|gate|other) '
        r'stage=([a-z-]+) reason=([a-z-]+)(?: (errno|status)=(-?[0-9]{1,4}))?'
        r'(?: source=kiosk-confinement line=([0-9]{1,6}))?', message)
    if match:
        if (match[1] not in (role, 'other') or match[2] not in (*ADMISSION_STAGES, 'other')
                or match[3] not in ADMISSION_REASONS):
            return None
        fields.update(source='preparation', role=match[1], stage=match[2], outcome='denied',
                      reason=match[3], line=int(match[6] or 0))
        if match[4]:
            value = int(match[5])
            if (match[4] == 'errno' and match[3] == 'os-error' and 0 <= value <= 4095
                    or match[4] == 'status' and match[3] == 'command-failed' and -255 <= value <= 255):
                fields[match[4]] = value
            else:
                return None
        return 'kiosk.admission-journal', fields
    match = re.fullmatch(
        r'onpc.kiosk confinement directory-entry action=(masked|omitted|denied) '
        r'reason=(metadata-unavailable|unsupported-name|non-root-owner|writable-entry|unsupported-type) '
        r'kind=(unknown|directory|file|link|special) ownership=(unknown|root|non-root) '
        r'access=(unknown|world-write|group-write|owner-change|read-only) '
        r'scope=(required|sibling) area=(usr|bin|sbin|lib|lib64|libexec|share|other) count=([0-9]{1,5})',
        message)
    if match and 1 <= int(match[8]) <= 32769:
        return 'kiosk.admission-directory', dict(
            role=role, action=match[1], reason=match[2], kind=match[3], ownership=match[4],
            access=match[5], scope=match[6], area=match[7], count=int(match[8]))
    match = re.fullmatch(
        r'onpc.kiosk confinement directory-view outcome=masked reason=writable-sibling-directory '
        r'count=([0-9]{1,5})', message)
    if match and 1 <= int(match[1]) <= 32769:
        fields.update(source='preparation', role=role, stage='directory-layout', outcome='masked',
                      reason='writable-sibling-directory', count=int(match[1]))
        return 'kiosk.admission-journal', fields
    return None


def _admission_context(event_id, fields):
    """Bounded phase witnesses; repeated generic denials cannot consume them."""
    source, outcome = fields.get('source'), fields.get('outcome')
    if source == 'authentication':
        return ('authentication',)
    if source == 'routing':
        return ('recovery',) if fields['recovery'] != 'none' else ('routing', fields['stage'])
    if source == 'preparation' and outcome == 'denied':
        return ('preparation', fields['role'])
    if source == 'native-view':
        return ('native-view', fields['role'], outcome)
    if event_id == 'kiosk.admission-directory' and fields['action'] == 'denied':
        return ('directory-refusal',)
    if source == 'pam':
        return ('armed',) if outcome == 'armed' else ('pam-refusal',) if outcome != 'allowed' else None
    return None


def _admission_history(selected):
    """Keep the original denial and newest phase witnesses within 20 records.

    Closed producer categories yield at most 16 phase witnesses. Fill remaining
    slots with distinct causes before repeated records, preferring failures.
    Raw journal identities never participate in selection or leave the parser.
    """
    keep, contexts, causes = {}, set(), set()
    first_failure = next((row for row in selected if row[0]), None)
    if first_failure:
        keep[first_failure[1]] = first_failure
    newest = sorted(selected, key=lambda row: (row[0], row[1]), reverse=True)
    # Context witnesses follow source order, independently of failure priority.
    for row in reversed(selected):
        context = _admission_context(row[2], row[3])
        if context is not None and context not in contexts:
            contexts.add(context)
            keep[row[1]] = row
    for row in newest:
        signature = (row[2], tuple((key, value) for key, value in row[3].items()
                                  if key not in ('occurred_at', 'count', 'line')))
        if signature not in causes:
            causes.add(signature)
            if len(keep) < 20:
                keep[row[1]] = row
    for row in newest:
        if len(keep) == 20:
            break
        keep[row[1]] = row
    return sorted(keep.values(), key=lambda row: row[1])


def collect_kiosk_admission_diagnostics():
    """Independent five-second read, including when kiosk configuration is unavailable.

    Preserve causal phase witnesses before repeats when the 20-marker cap trims history.
    Neither a successful routing check nor passwordless auth attests admission.
    """
    try:
        output = _query([
            '/usr/bin/journalctl', '--no-pager', '--quiet', '--output=json', '--lines=200',
            '--since=-24hours',
            '--grep=(onpc\\.(pam kiosk|kiosk confinement)|^pam_unix\\(gdm-password:auth\\): '
            'user \\[oh-no-parent-control\\] has blank password; authenticated without it$)',
            '--output-fields=MESSAGE,__REALTIME_TIMESTAMP,_TRANSPORT,_UID,_EXE,_COMM,'
            'SYSLOG_IDENTIFIER,_SYSTEMD_UNIT', '_UID=0',
        ], time.monotonic() + 5, empty_match=True)
        lines = output.splitlines()
        selected, rejected = [], 0
        for index, line in enumerate(lines[:200]):
            try:
                item = json.loads(line)
                if type(item) is not dict:
                    raise ValueError()
                marker = _admission_marker(item)
                if marker is None:
                    raise ValueError()
                stamp = item.get('__REALTIME_TIMESTAMP')
                if type(stamp) is not str or not re.fullmatch(r'[0-9]{1,17}', stamp):
                    raise ValueError()
                occurred = datetime.fromtimestamp(int(stamp) / 1000000, timezone.utc)
                event_id, fields = marker
                fields['occurred_at'] = occurred.isoformat(timespec='milliseconds')
                failure = fields.get('outcome', fields.get('action')) not in ('allowed', 'armed', 'masked', 'omitted')
                selected.append((failure, index, event_id, fields))
            except (ValueError, TypeError, OverflowError, OSError):
                rejected += 1
        retained = _admission_history(selected)
        for _failure, _index, event_id, fields in retained:
            KIOSK_LOG.warning(event_id, **fields)
        KIOSK_LOG.info('kiosk.admission-observation',
                       outcome='partial' if len(lines) >= 200 or rejected or len(selected) > 20 else 'complete',
                       count=len(retained), recognized_count=len(selected), rejected_count=rejected,
                       dropped_count=len(selected) - len(retained))
    except Exception:
        KIOSK_LOG.warning('kiosk.admission-observation', outcome='unavailable', count=0,
                          recognized_count=0, rejected_count=0, dropped_count=0)


def collect_kiosk_diagnostics(config_path):
    """Project pre-paint crashes into feedback, even after the user manager exits.

    Five seconds total, three bounded journal reads, no live-session action.
    UID/PID and raw messages are transient selectors, never diagnostic fields.
    Source timestamps relate the observations; they do not prove causation.
    """
    deadline = time.monotonic() + 5
    try:
        uid = config.load(config_path).kiosk_uid
    except Exception:
        KIOSK_LOG.warning("kiosk.session-observation", source="identity", outcome="unavailable", count=0)
        return
    renderer_pids = set()
    sources = (
        ("renderer", ["_UID=" + str(uid), "_SYSTEMD_USER_UNIT=" + KIOSK_APP_UNIT],
         r"^(Vulkan: .*VK_ERROR_MEMORY_MAP_FAILED.*|vkCreateDevice.*)$"),
        ("security", ["_TRANSPORT=audit", "+", "_TRANSPORT=kernel"],
         r"(avc:.*onpc_kiosk_app_t.*dri_device_t|segfault.*libgallium)"),
        ("session", ["_UID=" + str(uid), "_COMM=systemd"],
         r"^(oh-no-parent-control-app\.service: (Main process exited|Failed with result|"
         r"Triggering OnFailure=)|Stopped target gnome-session@oh-no-parent-control\.target)"),
    )
    for source, matches, pattern in sources:
        try:
            output = _query([
                "/usr/bin/journalctl", "--no-pager", "--quiet", "--output=json",
                "--lines=200", "--since=-24hours", "--boot=0", "--grep=" + pattern,
                "--output-fields=MESSAGE,__REALTIME_TIMESTAMP,_TRANSPORT,_UID,_PID,_EXE,"
                "_COMM,_SYSTEMD_USER_UNIT", *matches,
            ], deadline, empty_match=True)
            selected = []
            lines = output.splitlines()
            partial = len(lines) >= 200
            for line in lines:
                try:
                    item = json.loads(line)
                    if type(item) is not dict:
                        raise ValueError()
                    if source == "renderer":
                        marker = _kiosk_renderer_event(item, uid)
                    elif source == "security":
                        marker = _kiosk_security_event(item, renderer_pids)
                    else:
                        marker = _kiosk_session_event(item, uid)
                    if marker is None:
                        continue
                    stamp = item.get("__REALTIME_TIMESTAMP")
                    if type(stamp) is not str or not re.fullmatch(r"[0-9]{1,17}", stamp):
                        raise ValueError()
                    occurred = datetime.fromtimestamp(int(stamp) / 1000000, timezone.utc)
                    selected.append((marker, occurred.isoformat(timespec="milliseconds")))
                    pid = item.get("_PID")
                    if source == "renderer" and type(pid) is str and re.fullmatch(r"[0-9]{1,10}", pid):
                        renderer_pids.add(pid)
                except (ValueError, TypeError, OverflowError, OSError):
                    partial = True
            partial = partial or len(selected) > 20
            for (reason, exit_kind, exit_status), occurred in selected[-20:]:
                KIOSK_LOG.warning("kiosk.session-journal", source=source, reason=reason,
                                  exit_kind=exit_kind, exit_status=exit_status, occurred_at=occurred)
            KIOSK_LOG.info("kiosk.session-observation", source=source,
                           outcome="partial" if partial else "complete", count=min(len(selected), 20))
        except Exception:
            KIOSK_LOG.warning("kiosk.session-observation", source=source, outcome="unavailable", count=0)
