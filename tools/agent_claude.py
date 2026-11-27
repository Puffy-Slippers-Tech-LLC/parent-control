"""Claude Code sessions beneath shared supervision, over `claude -p` stream-json.

Batch, interactive and plain goal sessions all run the CLI as the supervised
child; no SDK or bridge process is involved. The adapter renders the shared
permission, sandbox, instruction and role policy into native options. Workflow
acceptance, budgets and process ownership stay with the shared launchers.
"""

import ast
import itertools
import json
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from agent_adapter import (BACKEND_REVIEW_INSTRUCTIONS, ROLES, SESSION_GOAL, AgentSelection,
                           ModelProfile, PreparedSession, SessionEvent, helper_profile,
                           resolve_capacity_fallback, resolve_role_profile)


SANDBOX_TOOLS = ('bwrap', 'socat')
READ_TOOLS = ('Read', 'Glob', 'Grep')
WRITE_TOOLS = ('Edit', 'Write', 'Bash', 'TodoWrite')
NO_MCP = '{"mcpServers":{}}'
# Inherited identities and overrides would attach to, or reconfigure, another session.
INHERITED = ('CLAUDECODE', 'CLAUDE_CODE_ENTRYPOINT', 'CLAUDE_CODE_SESSION_ID',
             'CLAUDE_CODE_PARENT_SESSION_ID', 'CLAUDE_CODE_SSE_PORT', 'CLAUDE_CODE_EFFORT_LEVEL',
             'CLAUDE_CODE_SUBAGENT_MODEL', 'CLAUDE_CODE_SUBAGENT_MODEL_FORCE')

def host_policy(root):
    """Render the maintained Codex rules as Claude command patterns.

    Unattended, Codex allow rules run outside its sandbox and prompt/forbidden
    rules are refusals; the most restrictive rule wins in both agents. The
    machine-wide public-read curl grant lives outside this file.
    """
    from install_codex_rules import render
    allowed, denied = ['curl -fsSL *'], []
    for block in re.findall(r'prefix_rule\((.*?)\n\)', render(root), re.S):
        pattern = ast.literal_eval(re.search(r'pattern\s*=\s*(\[.*?\])\s*,\s*\n\s*decision',
                                             block, re.S).group(1))
        decision = re.search(r'decision\s*=\s*"(\w+)"', block).group(1)
        tokens = [token if isinstance(token, list) else [token] for token in pattern]
        (allowed if decision == 'allow' else denied).extend(
            ' '.join(command) + ' *' for command in itertools.product(*tokens))
    return allowed, denied


def settings(request):
    """Workspace sessions run other shell commands in a fail-closed OS sandbox."""
    if request.permissions == 'read_only':
        return {'permissions': {'allow': list(READ_TOOLS)}}
    allowed, denied = host_policy(request.root)
    return {
        'permissions': {'allow': [*READ_TOOLS, *(f'Bash({command})' for command in allowed)],
                        'deny': [f'Bash({command})' for command in denied]},
        # Ubuntu's AppArmor bwrap profile strips the capability Claude's Unix
        # socket seccomp filter needs. Sockets stay open; files and network stay confined.
        'sandbox': {'enabled': True, 'failIfUnavailable': True, 'autoAllowBashIfSandboxed': True,
                    'allowUnsandboxedCommands': False, 'excludedCommands': allowed,
                    'network': {'allowAllUnixSockets': True}},
    }


def session_instructions(request, roles):
    text = (f'Repository objective for this session: {SESSION_GOAL}\n'
            'The launcher pins this objective in this session and in every helper; there is no '
            'native goal tool. Instructions to activate, keep or complete the repository '
            'simplicity goal (including $goal, get_goal or create_goal) refer to this objective: '
            'keep working until the bounded assignment is verified. Where instructions name '
            'native apply_patch, use the Edit and Write tools; for a $skill mention, read that '
            "skill's SKILL.md. Commands that are not granted fail without a prompt; report a "
            'needed grant as a blocker instead of working around it.\n\n' + request.instructions)
    if roles:
        text += (f'Delegate only to the configured {", ".join(sorted(roles))} agents, within '
                 "the launcher's existing delegation policy. Each helper starts with fresh "
                 'context: give it a self-contained assignment with its exact scope, paths, '
                 'relevant instructions, current evidence and disjoint write ownership. Wait for '
                 "each helper's report before relying on it.\n\n")
    return text + BACKEND_REVIEW_INSTRUCTIONS


def failure(category, message):
    return SessionEvent('failure', {
        'message': message, 'context': 'turn failed',
        'details': {'agent': 'claude', 'category': category},
        'task_error': message, 'capacity': category == 'capacity'})


def result_event(packet, *, structured):
    """Return a failure, the structured candidate, or None for a plain success.

    A native success does not settle the workflow's own status, which remains
    the workflow validator's decision.
    """
    if packet.get('stop_reason') == 'refusal':
        return failure('refusal', 'Claude refused the assignment; no result accepted')
    status = packet.get('api_error_status')
    if (packet.get('subtype') != 'success' or packet.get('is_error') is not False
            or packet.get('terminal_reason') not in (None, 'completed')
            or packet.get('errors') or status is not None):
        detail = '; '.join(map(str, packet.get('errors') or ())) or str(packet.get('result') or '')
        category = ('authentication' if status in (401, 403) else 'rate_limit' if status == 429 else
                    'capacity' if status == 529 or 'overloaded' in detail.lower() else 'process')
        return failure(category, f'Claude ended without a completed result ({category})'
                       + (f': {detail[:1000]}' if detail else ''))
    if not structured:
        return None
    value = packet.get('structured_output')
    if not isinstance(value, dict):
        return failure('malformed_result', 'Claude returned no structured coordinator result')
    return SessionEvent('text', {'id': 'result', 'text': json.dumps(value), 'complete': True})


def usage_event(packet):
    # The CLI's per-turn coordinator counters, as reported.
    return SessionEvent('usage', {'usage': packet.get('usage')})


class ClaudeAdapter:
    name = 'claude'

    def __init__(self, root=None):
        self.selection = AgentSelection(self.name, root or Path(__file__).resolve().parents[1])

    def setup(self, root, *, headless=False):
        """Nothing to install: each session receives its policy as native options."""

    def prepare_environment(self, root, environment):
        # The native installer's user-local path; do not source shell rc files.
        environment = dict(environment)
        path, home = environment.get('PATH', ''), environment.get('HOME')
        if home and not shutil.which('claude', path=path):
            environment['PATH'] = str(Path(home) / '.local/bin') + (':' + path if path else '')
        return environment

    def executable(self, environment):
        executable = shutil.which('claude', path=environment.get('PATH', ''))
        if executable is None:
            raise ValueError('Claude CLI is missing; install and authenticate it before running this launcher')
        return executable

    def readiness(self, root, environment):
        environment = self.prepare_environment(root, environment)
        executable = self.executable(environment)
        try:
            response = subprocess.run([executable, 'auth', 'status'], cwd=root, env=environment,
                                      capture_output=True, text=True, timeout=15)
            logged_in = json.loads(response.stdout).get('loggedIn') is True
        except (OSError, subprocess.SubprocessError, ValueError, AttributeError):
            logged_in = False
        if not logged_in:
            raise ValueError(f'Claude login is not ready for executing checkout {root}; '
                             'run claude auth login separately as this account, then rerun ./setup.sh')
        self.sandbox_ready(environment)
        return 'Claude login and sandbox prerequisites verified for this account; model access is checked before each workflow'

    def sandbox_ready(self, environment):
        missing = [tool for tool in SANDBOX_TOOLS if not shutil.which(tool, path=environment.get('PATH', ''))]
        if missing:
            raise ValueError(f'Claude sandbox prerequisites are missing ({", ".join(missing)}); '
                             'install them through ./setup.sh dependency setup')

    def resolve_profile(self, role, *, model=None, effort=None):
        return resolve_role_profile(role, selection=self.selection, model=model, effort=effort)

    def capacity_fallback(self, model):
        return resolve_capacity_fallback(model, selection=self.selection)

    def catalog(self, executable, root, environment):
        """Read the CLI's model list from its initialize handshake; no model request."""
        request = json.dumps({'type': 'control_request', 'request_id': 'catalog',
                              'request': {'subtype': 'initialize'}}) + '\n'
        try:
            response = subprocess.run([executable, '-p', '--verbose', '--input-format', 'stream-json',
                '--output-format', 'stream-json', '--no-session-persistence', '--setting-sources', '',
                '--strict-mcp-config', '--mcp-config', NO_MCP, '--tools', ''],
                input=request, cwd=root, env=environment, capture_output=True, text=True,
                check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            reason = ('timed out after 30 seconds' if isinstance(error, subprocess.TimeoutExpired) else
                      f'exited {error.returncode}' if isinstance(error, subprocess.CalledProcessError) else
                      'could not execute the CLI')
            raise ValueError(f'Claude model preflight {reason}; check CLI readiness and authentication '
                             'separately before retrying this launcher') from error
        for line in response.stdout.splitlines():
            try:
                packet = json.loads(line)
                if packet['type'] == 'control_response' and packet['response']['request_id'] == 'catalog':
                    models = packet['response']['response']['models']
                    if isinstance(models, list):
                        return [entry for entry in models if isinstance(entry, dict)]
            except (ValueError, KeyError, TypeError):
                continue
        raise ValueError('Claude returned an invalid model catalog')

    def preflight(self, request, environment, profiles=()):
        """Check advertised model/effort support and sandbox prerequisites only."""
        self.validate(request)
        executable = self.executable(environment)
        if request.permissions == 'workspace':
            self.sandbox_ready(environment)
        entries = self.catalog(executable, request.root, environment)
        required = [ModelProfile(request.model, request.effort), *profiles]
        if request.delegation.enabled:
            required += [helper_profile(self, request, role) for role in request.delegation.roles]
        for model, effort in dict.fromkeys(required):
            if not any(model in (entry.get('value'), entry.get('resolvedModel'))
                       and effort in (entry.get('supportedEffortLevels') or ()) for entry in entries):
                raise ValueError(f'Claude model catalog has no {model} with {effort} effort; '
                                 'no fallback was selected')

    def validate(self, request):
        if request.permissions not in ('workspace', 'read_only'):
            raise ValueError('unsupported agent write boundary')
        if request.interactive and (request.run is None or request.schema is None):
            raise ValueError('interactive agent sessions require an owned run and schema')
        if request.continuation_key is not None or request.thread_id is not None:
            raise ValueError('Claude sessions always start fresh; conversation resume is unsupported')
        delegation = request.delegation
        if (type(delegation.max_concurrent) is not int or delegation.max_concurrent < 1
                or type(delegation.max_depth) is not int or delegation.max_depth < 1
                or any(role not in ROLES for role in delegation.roles)
                or (request.permissions == 'read_only' and delegation.enabled
                    and 'worker' in delegation.roles)):
            raise ValueError('unsupported agent delegation requirements')
        for name, _ in request.shell_environment:
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
                raise ValueError('invalid agent shell environment name')

    def agents(self, request):
        """Native roles: shared instructions, pinned profiles and enforced tool sets."""
        if not request.delegation.enabled:
            return {}
        shared = (f'Repository objective for this assignment: {SESSION_GOAL}\n'
                  "You are a fresh helper without the coordinator's conversation. Do not "
                  'delegate.\n\n' + request.instructions)
        roles = {}
        for role in request.delegation.roles:
            name, filename, description = ROLES[role]
            asset = tomllib.loads(Path(__file__).with_name(filename).read_text())
            profile = helper_profile(self, request, role)
            roles[name] = dict(description=description,
                               prompt=asset['developer_instructions'].strip() + '\n\n' + shared,
                               tools=[*READ_TOOLS, *(WRITE_TOOLS if role == 'worker' else ())],
                               model=profile.model, effort=profile.effort)
        return roles

    def prepare_session(self, request, environment):
        self.validate(request)
        environment = self.prepare_environment(request.root, environment)
        executable = self.executable(environment)
        goal = request.run is not None and request.schema is None
        batch = not request.interactive and not goal
        workspace = request.permissions == 'workspace'
        roles = self.agents(request)
        tools = [*READ_TOOLS, *(WRITE_TOOLS if workspace else ()), *(('Agent',) if roles else ())]
        argv = [executable, '-p', '--verbose', '--output-format', 'stream-json',
                '--input-format', 'text' if batch else 'stream-json',
                '--model', request.model, '--effort', request.effort,
                '--no-session-persistence', '--setting-sources', 'project',
                '--strict-mcp-config', '--mcp-config', NO_MCP, '--no-chrome',
                '--permission-mode', 'acceptEdits' if workspace else 'dontAsk',
                '--permission-prompts', 'none', '--tools', ','.join(tools),
                '--settings', json.dumps(settings(request)),
                '--append-system-prompt', session_instructions(request, roles)]
        if roles:
            argv += ['--agents', json.dumps(roles)]
        if request.schema is not None:
            schema = json.loads(request.schema.read_text())
            if not isinstance(schema, dict):
                raise ValueError('Claude result schema must be an object')
            argv += ['--json-schema', json.dumps(schema)]
        for directory in request.extra_directories:
            argv += ['--add-dir', str(directory)]
        child_environment = {name: value for name, value in environment.items() if name not in INHERITED}
        child_environment.update(request.shell_environment)
        child_environment.update(
            CLAUDE_CODE_DISABLE_AUTO_MEMORY='1', CLAUDE_CODE_RETRY_WATCHDOG='0',
            ENABLE_CLAUDEAI_MCP_SERVERS='false',
            # Only the configured roles, no forks, and helpers always joined.
            CLAUDE_AGENT_SDK_DISABLE_BUILTIN_AGENTS='1', CLAUDE_CODE_FORK_SUBAGENT='0',
            CLAUDE_CODE_DISABLE_BACKGROUND_TASKS='1',
            CLAUDE_CODE_MAX_CONCURRENT_SUBAGENTS=str(request.delegation.max_concurrent),
            CLAUDE_CODE_MAX_SUBAGENT_SPAWN_DEPTH=str(request.delegation.max_depth))
        protocol = ClaudeGoalProtocol() if goal else ClaudeProtocol() if request.interactive else None
        return PreparedSession(self, request, tuple(argv), child_environment, request.root,
            protocol=protocol, presentation=None if protocol is not None else ClaudeBatchPresentation(
                request.run / 'agent-result.json' if request.run is not None else None))


def text_of(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return '\n'.join(block.get('text', '') for block in content
                         if isinstance(block, dict) and block.get('type') == 'text')
    return ''


def tool_item(block):
    """Map a coordinator tool call onto the shared renderer's item vocabulary."""
    name, value, identity = block.get('name'), block.get('input') or {}, block.get('id')
    if name == 'Bash':
        return {'id': identity, 'type': 'command_execution', 'command': str(value.get('command', '')),
                'status': 'in_progress'}
    if name in ('Edit', 'Write', 'NotebookEdit'):
        return {'id': identity, 'type': 'file_change', 'changes': [{
            'path': str(value.get('file_path') or value.get('notebook_path') or ''),
            'kind': 'write' if name == 'Write' else 'update'}]}
    if name in ('Agent', 'Task'):
        return {'id': identity, 'type': 'sub_agent_activity', 'tool': 'spawn_agent',
                'agent': value.get('subagent_type'), 'prompt': value.get('prompt')}
    if name == 'TodoWrite':
        return {'id': identity, 'type': 'todo_list', 'items': [
            {'text': str(task.get('content', '')), 'completed': task.get('status') == 'completed'}
            for task in value.get('todos') or () if isinstance(task, dict)]}
    return {'id': identity, 'type': 'mcp_tool_call', 'server': 'claude', 'tool': str(name),
            'arguments': value}


class ClaudeStream:
    """Coordinator stream-json decoding; helper internals and reasoning stay private."""

    def __init__(self):
        self.pending = b''
        self.tools = {}

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            if not line.strip():
                continue
            try:
                packet = json.loads(line)
            except ValueError:
                yield SessionEvent('diagnostic', {'text': line.decode('utf-8', errors='replace')})
                continue
            if isinstance(packet, dict):
                yield from self.packet(packet)

    def packet(self, packet):
        kind = packet.get('type')
        if kind == 'result':
            yield from self.result(packet)
        elif packet.get('parent_tool_use_id') is None and kind in ('assistant', 'user'):
            for index, block in enumerate((packet.get('message') or {}).get('content') or ()):
                if isinstance(block, dict):
                    yield from self.block(packet, index, block)
        # System, rate-limit and unknown packets are not presentation.

    def block(self, packet, index, block):
        kind = block.get('type')
        if kind == 'text' and packet['type'] == 'assistant' and block.get('text'):
            yield SessionEvent('text', {'id': f"{packet.get('uuid')}:{index}", 'text': block['text'],
                                        'complete': True})
        elif kind == 'tool_use' and block.get('name') != 'StructuredOutput':
            item = tool_item(block)
            if item['type'] != 'todo_list':
                self.tools[item['id']] = item
            yield SessionEvent('item', {'item': item, 'complete': item['type'] == 'todo_list'})
        elif kind == 'tool_result' and (item := self.tools.pop(block.get('tool_use_id'), None)):
            item = dict(item, status='failed' if block.get('is_error') is True else 'completed')
            if item['type'] == 'command_execution':
                item.update(aggregated_output=text_of(block.get('content')), exit_code=None)
            elif item['type'] == 'mcp_tool_call' and item['status'] == 'failed':
                item['error'] = text_of(block.get('content'))[:2000]
            yield SessionEvent('item', {'item': item, 'complete': True})


class ClaudeBatchPresentation(ClaudeStream):
    """Batch decoding; persists only a successful coordinator's structured result."""

    def __init__(self, result_path):
        super().__init__()
        self.result_path = result_path

    def finish(self):
        if self.pending.strip():
            yield from self.feed(b'\n')

    def result(self, packet):
        yield usage_event(packet)
        event = result_event(packet, structured=True)
        if event.kind == 'text' and self.result_path is not None:
            from detached_launcher import atomic
            atomic(self.result_path, json.loads(event.data['text']))
        yield event
        if event.kind != 'failure':
            yield SessionEvent('turn_completed', {'interrupted': False})


class ClaudeProtocol(ClaudeStream):
    """Interactive turns; the shared AppSession owns mailbox and acceptance gates.

    Input sent during a native turn runs as a later native turn, so follow-ups
    wait for the current result and return through retry_input. An interrupt
    discards that turn's candidate and settles once the CLI acknowledges it.
    """

    def __init__(self):
        super().__init__()
        self.outgoing = bytearray()
        self.ready = False
        self.active_turn = False
        self.turn_requests_pending = False
        self.interrupted = False
        self.queued = []
        self.requests = 0

    def send(self, packet):
        self.outgoing.extend((json.dumps(packet) + '\n').encode())

    def control_request(self, subtype):
        self.requests += 1
        self.send({'type': 'control_request', 'request_id': f'{subtype}-{self.requests}',
                   'request': {'subtype': subtype}})

    def user(self, text):
        self.active_turn = True
        self.send({'type': 'user', 'message': {'role': 'user', 'content': text},
                   'parent_tool_use_id': None, 'session_id': ''})

    def start(self):
        self.control_request('initialize')

    def poll(self):
        return None

    def start_turn(self, text):
        if self.active_turn or self.turn_requests_pending:
            raise ValueError('Claude previous turn has not drained')
        self.interrupted = False
        self.user(text)

    def steer(self, text):
        self.queued.append(text)

    def interrupt(self):
        self.interrupted = True
        self.turn_requests_pending = True
        self.control_request('interrupt')

    def packet(self, packet):
        if packet.get('type') == 'control_response':
            yield from self.control(packet.get('response') or {})
        else:
            yield from super().packet(packet)

    def control(self, response):
        request = str(response.get('request_id', ''))
        if request.startswith('interrupt-'):
            # Even a late interrupt is acknowledged; the result was discarded.
            self.turn_requests_pending = False
        elif response.get('subtype') != 'success':
            yield failure('process', 'Claude rejected session initialization: '
                          + str(response.get('error', ''))[:500])
        elif not self.ready:
            self.ready = True
            yield SessionEvent('ready', {})

    def result(self, packet):
        if not self.active_turn:
            return  # Not attributable to a submitted coordinator turn.
        self.active_turn = False
        yield usage_event(packet)
        yield from self.settle(packet)

    def settle(self, packet):
        if not self.interrupted:
            event = result_event(packet, structured=True)
            yield event
            if event.kind == 'failure':
                return
        yield SessionEvent('turn_completed', {'interrupted': self.interrupted})
        if self.queued:
            yield SessionEvent('retry_input', {'text': '\n\n'.join(self.queued)})
            self.queued.clear()

    def finalize_result(self, text):
        try:
            value = json.loads(text)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None


class ClaudeGoalProtocol(ClaudeProtocol):
    """One fresh plain assignment; queued developer input runs as follow-up turns.

    The session ends when a successful turn leaves no queued input. There is
    no output schema; the runner's own results decide what remains.
    """

    def __init__(self):
        super().__init__()
        self.started = self.done = False
        self.status = 1

    @property
    def chat_ready(self):
        return self.started and not self.done

    def start_turn(self, text):
        if self.started:
            raise ValueError('plain goal session already received its assignment')
        self.started = True
        super().start_turn(text)

    def settle(self, packet):
        event = result_event(packet, structured=False)
        if event is not None:
            self.done = True
            yield event
            return
        if self.queued:
            self.user('\n\n'.join(self.queued))
            self.queued.clear()
        else:
            self.done = True
            self.status = 0
        yield SessionEvent('turn_completed', {'interrupted': False})
