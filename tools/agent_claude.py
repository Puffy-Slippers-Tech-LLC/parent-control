"""Inactive Claude transport foundation; workflow selection remains Codex-only.

Only read-only, nondelegating transport assignments are supported here. This is
not the workspace/delegation policy or qualification required to enable Claude.
The SDK is optional and imported only when preparing an interactive session.
"""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

from agent_adapter import ModelProfile, PreparedSession, SessionEvent


MODEL = 'claude-opus-5-5'
EFFORTS = ('low', 'medium', 'high', 'max')
MAX_FRAME = 8 * 1024 * 1024


def settings():
    """No shell, external tools, skills or delegation in this foundation."""
    return {
        'autoMemoryEnabled': False,
        'permissions': {'defaultMode': 'dontAsk', 'deny': [
            'Bash', 'PowerShell', 'Edit', 'Write', 'NotebookEdit', 'Agent', 'Task', 'mcp__*']},
        'sandbox': {'enabled': True, 'autoAllowBashIfSandboxed': False,
                    'allowUnsandboxedCommands': False, 'failIfUnavailable': True},
    }


def native_arguments(model, effort, schema, instructions):
    return ['--model', model, '--effort', effort, '--permission-mode', 'dontAsk',
            '--permission-prompts', 'none', '--safe-mode', '--restricted', '--setting-sources', '',
            '--settings', json.dumps(settings()), '--tools', 'Read,Glob,Grep',
            '--disallowedTools', 'Agent,Task,mcp__*', '--strict-mcp-config',
            '--mcp-config', '{"mcpServers":{}}', '--disable-slash-commands',
            '--no-chrome', '--no-session-persistence', '--json-schema', json.dumps(schema),
            '--append-system-prompt', instructions]


def failure(category, message):
    # No transient retry is enabled until native capacity behavior is qualified.
    return SessionEvent('failure', {
        'message': message, 'context': 'Claude transport',
        'details': {'agent': 'claude', 'category': category},
        'task_error': message, 'capacity': False, 'terminal': True})


def result_event(packet):
    """A coordinator result must be successful natively and structured.

    The workflow's status is deliberately left untouched. A native success can
    carry a failed workflow result, which remains the workflow validator's job.
    """
    stop = packet.get('stop_reason')
    terminal = packet.get('terminal_reason')
    if stop == 'refusal':
        return failure('refusal', 'Claude refused the assignment; no result accepted')
    if (packet.get('subtype') != 'success' or packet.get('is_error') is not False
            or terminal != 'completed' or stop not in (None, 'end_turn')
            or packet.get('errors') or packet.get('api_error_status') is not None):
        status = packet.get('api_error_status')
        category = ('authentication' if status in (401, 403) else
                    'rate_limit' if status == 429 else
                    'capacity' if status == 529 else 'process')
        return failure(category, f'Claude ended without a completed result ({category})')
    value = packet.get('structured_output')
    if not isinstance(value, dict):
        return failure('malformed_result', 'Claude returned no structured coordinator result')
    return SessionEvent('text', {'id': 'result', 'text': json.dumps(value), 'complete': True})


def usage_event(packet):
    # Per-turn counters and cumulative native snapshots are separate on purpose.
    return SessionEvent('usage', {'usage': packet.get('usage'), 'agent': 'claude',
        'scope': 'coordinator_turn', 'model_usage': packet.get('model_usage'),
        'total_cost_usd': packet.get('total_cost_usd'), 'snapshot_scope': 'session_cumulative'})


class ClaudeAdapter:
    name = 'claude'

    def resolve_profile(self, role, *, model=None, effort=None):
        if role == 'impact_triage':
            # This native mapping does not qualify Claude for workflow use;
            # AgentSelection still owns that independent execution gate.
            if ((model is not None and model != MODEL)
                    or (effort is not None and effort != 'high')):
                raise ValueError('impact triage requires Claude Opus 5.5 with high effort')
            return ModelProfile(MODEL, 'high')
        if role != 'implementation':
            raise ValueError('Claude workflow/role profiles are not qualified yet')
        model, effort = model or MODEL, effort or 'high'
        if model != MODEL or effort not in EFFORTS:
            raise ValueError('unsupported Claude model/effort; no fallback was selected')
        return ModelProfile(model, effort)

    def capacity_fallback(self, model):
        return None

    def executable(self, environment):
        executable = shutil.which('claude', path=environment.get('PATH', os.defpath))
        # The native installer uses this user-local path; do not source shell rc files.
        local = Path.home() / '.local/bin/claude'
        if executable is None and local.is_file() and os.access(local, os.X_OK):
            executable = str(local)
        if executable is None:
            raise ValueError('Claude CLI is missing; prepare it separately through development setup')
        return executable

    def preflight(self, request, environment, profiles=()):
        self.validate(request)
        for profile in profiles:
            self.resolve_profile('implementation', model=profile.model, effort=profile.effort)
        executable = self.executable(environment)
        try:
            version = subprocess.run([executable, '--version'], cwd=request.root, env=environment,
                                     capture_output=True, text=True, check=True, timeout=15)
            match = re.match(r'(\d+)\.(\d+)\.(\d+)\b', version.stdout)
            if match is None or tuple(map(int, match.groups())) < (2, 1, 248):
                raise ValueError('Claude CLI lacks the required restricted transport interface')
            help_text = subprocess.run([executable, '--help'], cwd=request.root, env=environment,
                                       capture_output=True, text=True, check=True, timeout=15).stdout
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError('Claude CLI inspection failed; no task or authentication was started') from error
        for option in ('--safe-mode', '--restricted', '--permission-prompts', '--json-schema',
                       '--no-session-persistence', '--setting-sources', '--strict-mcp-config'):
            if option not in help_text:
                raise ValueError(f'Claude CLI is missing required capability {option}')
        if request.interactive:
            self.sdk()
        # Help/version establish interface readiness only, not login or model access.

    @staticmethod
    def sdk():
        try:
            from claude_agent_sdk import ClaudeAgentOptions, ResultMessage
        except ImportError as error:
            raise ValueError('Claude interactive transport needs claude-agent-sdk in the launcher '
                             'Python environment; no dependency was installed') from error
        if (not {'cli_path', 'effort', 'strict_mcp_config', 'setting_sources'}
                <= ClaudeAgentOptions.__dataclass_fields__.keys()
                or not {'origin', 'terminal_reason'} <= ResultMessage.__dataclass_fields__.keys()):
            raise ValueError('Claude SDK lacks required transport/result attribution capabilities')

    def validate(self, request):
        self.resolve_profile('implementation', model=request.model, effort=request.effort)
        if request.permissions != 'read_only' or request.delegation.enabled:
            raise ValueError('Claude transport foundation requires read_only permissions and '
                             'disabled delegation; workspace/role policy is not qualified')
        if request.run is None or request.schema is None:
            raise ValueError('Claude transport requires an owned run and result schema')
        if request.extra_directories or request.shell_environment or request.standard_speed:
            raise ValueError('Claude transport does not yet support this session requirement')

    def prepare_session(self, request, environment):
        self.validate(request)
        executable = self.executable(environment)
        schema = json.loads(request.schema.read_text())
        if not isinstance(schema, dict):
            raise ValueError('Claude result schema must be an object')
        # Project discovery is disabled: explicitly provide the shared instructions.
        instructions = (request.root / 'AGENTS.md').read_text() + '\n\n' + request.instructions
        argv = (sys.executable, '-B', str(Path(__file__).with_name('agent_claude_bridge.py')),
                'interactive' if request.interactive else 'batch', executable,
                str(request.schema), str(request.run), request.model, request.effort, instructions)
        child_environment = dict(environment)
        for name in ('CLAUDECODE', 'CLAUDE_CODE_SESSION_ID', 'CLAUDE_CODE_PARENT_SESSION_ID',
                     'CLAUDE_AGENT_SDK_SESSION_ID', 'CLAUDE_SESSION_ID'):
            child_environment.pop(name, None)
        child_environment.update(CLAUDE_CODE_DISABLE_AUTO_MEMORY='1',
                                 CLAUDE_CODE_DISABLE_BACKGROUND_TASKS='1',
                                 CLAUDE_CODE_RETRY_WATCHDOG='0',
                                 CLAUDE_CODE_MAX_RETRIES='0')
        return PreparedSession(self, request, argv, child_environment, request.root,
            protocol=ClaudeProtocol() if request.interactive else None,
            presentation=None if request.interactive else ClaudeBatchPresentation())


class ClaudeBatchPresentation:
    """Decode bridge output without accepting or persisting workflow results."""

    def __init__(self):
        self.pending = b''

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        if len(self.pending) > MAX_FRAME:
            raise ValueError('Claude transport frame is too large')
        for line in lines:
            if len(line) > MAX_FRAME:
                raise ValueError('Claude transport frame is too large')
            packet = json.loads(line)
            yield from self.event(packet)

    def finish(self):
        if self.pending:
            raise ValueError('Claude transport ended with an incomplete frame')
        return iter(())

    def event(self, packet):
        if packet.get('type') == 'result':
            yield usage_event(packet)
            yield result_event(packet)
        elif packet.get('type') == 'text':
            yield SessionEvent('text', {'id': packet.get('id'), 'text': packet['text'], 'complete': True})
        elif packet.get('type') == 'failure':
            yield failure(packet['category'], packet['message'])
        # Unknown native content is never rendered: it may contain reasoning.


class ClaudeProtocol(ClaudeBatchPresentation):
    """Bridge framing; the shared AppSession still owns mailbox/acceptance gates."""

    def __init__(self):
        super().__init__()
        self.outgoing = bytearray()
        self.ready = False
        self.active_turn = False
        self.turn_requests_pending = False
        self.turn = 0
        self.interrupted = False
        self.queued = []

    def send(self, operation, **fields):
        self.outgoing.extend((json.dumps(dict(operation=operation, turn=self.turn, **fields)) + '\n').encode())

    def start(self):
        pass  # The owned bridge reports ready after SDK initialization.

    def start_turn(self, text):
        if self.active_turn or self.turn_requests_pending:
            raise ValueError('Claude previous turn has not drained')
        self.turn += 1
        self.active_turn = True
        self.interrupted = False
        self.send('query', text=text)

    def steer(self, text):
        # SDK query queues input; it does not steer an active turn. Deliver it
        # through AppSession as a new turn only after the native result drains.
        self.queued.append(text)

    def interrupt(self):
        self.interrupted = True
        self.turn_requests_pending = True
        self.send('interrupt')

    def event(self, packet):
        kind = packet.get('type')
        if kind == 'ready':
            if self.ready:
                raise ValueError('Claude bridge initialized twice')
            self.ready = True
            yield SessionEvent('ready', {})
        elif kind == 'ack' and packet.get('turn') == self.turn:
            self.turn_requests_pending = False
        elif kind == 'failure':
            yield from super().event(packet)
        elif packet.get('turn') == self.turn and self.active_turn:
            if kind == 'result':
                self.active_turn = False
                yield usage_event(packet)
                if not self.interrupted:
                    event = result_event(packet)
                    yield event
                    if event.kind == 'failure':
                        return
                yield SessionEvent('turn_completed', {'interrupted': self.interrupted})
                if self.queued:
                    # AppSession prepends retry_input. Emit once so separately
                    # queued developer messages retain their original order.
                    yield SessionEvent('retry_input', {'text': '\n\n'.join(self.queued)})
                    self.queued.clear()
            elif kind == 'text':
                # Text is presentation only; only structured_output can be a candidate.
                yield SessionEvent('notice', {'text': packet['text']})

    def finalize_result(self, text):
        try:
            value = json.loads(text)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
