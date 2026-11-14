"""Codex-native session configuration and protocol beneath shared supervision."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tomllib

from agent_adapter import ModelProfile, PreparedSession, ProfileRole, SessionEvent, SessionRequest


SESSION_GOAL = ('Simple, lean, robust; do not overengineer. Prefer solutions that simplify '
                'the resulting codebase as a whole, not merely minimize the patch. '
                'Keep refactoring within the task’s scope.')

GOAL_INSTRUCTIONS = f"""Before task work, use get_goal to inspect this session's actual
Codex goal state. If absent, call create_goal with objective:
{SESSION_GOAL}
Verify that this exact goal is active. Literal /goal prompt text or following the
objective as advice is insufficient. If goal activation fails, stop and report
the failure through the workflow's existing blocker/error route; do not silently
continue without it. Do not add a token budget or change task scope, acceptance,
session limits or delegation policy. Complete the goal after verifying your
bounded assignment, before the final handoff. Include these goal setup instructions
and the exact objective in every fresh helper assignment, including workers,
monitors, advisers and reviewers.

"""

SUBAGENT_CONTEXT_INSTRUCTIONS = """Every launcher session starts with fresh context.
On every spawn_agent call, explicitly set fork_turns="none".
Never omit fork_turns or use "all". Give every helper a self-contained assignment
with its exact scope, paths, relevant instructions, current evidence and disjoint
write ownership. This applies to workers, monitors, advisers and backend reviewers;
it does not authorize delegation beyond the launcher's existing policy.

"""

BACKEND_REVIEW_INSTRUCTIONS = """For product backend code involving core functionalities,
AGENTS.md requires an independent code review by the backend_reviewer agent
(GPT-6 Astra xHigh) before completing the changes. This mandate applies across
all launchers, including repair, recovery and optimization sessions. It overrides
Sol-only and no-delegation rules only for this required review; keep the launcher's
existing coordinator, implementation, consultation and escalation model policy.
Do not request this review for changes outside core backend code. Give the reviewer
the exact owned changes, relevant source/contracts and validation evidence in a
fresh context. Pause implementation while it reviews; wait for its findings and
close it before resuming. Resolve actionable findings and revalidate material
revisions; obtain a fresh review of material backend revisions before completion.
Record the review findings and resolution in the existing summary or handoff.
A missing or failed review is incomplete work, never a completed change; use the
launcher's existing continuation or blocker route. Review gives no test or installed
acceptance credit. The reviewer cannot implement, test, control resources or delegate.
"""

ROLES = {
    'backend_reviewer': ('backend_reviewer', 'backend_reviewer.toml',
        'Mandatory independent review of core backend changes only; no implementation'),
    'monitor': ('plan_monitor', 'plan_monitor.toml',
        'Routine read-only monitoring; no resource ownership or mutations'),
    'worker': ('plan_worker', 'plan_worker.toml',
        'Bounded routine work or coverage refresh on explicitly assigned files'),
    'translator': ('whatsnew_translator', 'sync_whatsnew_translator.toml',
        'Read-only latest-release translator/reviewer'),
}


class CodexAdapter:
    name = 'codex'

    def setup(self, root, *, headless=False):
        from install_codex_rules import prepare_checkout
        prepare_checkout(root, headless=headless)

    def prepare_environment(self, root, environment):
        """Discover account-local Codex/Node without interactive rc files.

        SSH and setup use the executing account's environment. Keep credentials
        and personal configuration in place; carry only the discovered PATH
        back from the maintained NVM entry point.
        """
        environment = dict(environment)
        path = environment.get('PATH', '')
        home = environment.get('HOME')
        if home and not shutil.which('codex', path=path):
            path = str(Path(home) / '.local/bin') + ':' + path
            environment['PATH'] = path
        if (shutil.which('codex', path=path) and shutil.which('node', path=path)):
            return environment
        nvm = environment.get('NVM_DIR') or (str(Path(home) / '.nvm') if home else None)
        if nvm and (Path(nvm) / 'nvm.sh').is_file():
            shell_environment = dict(environment, NVM_DIR=nvm)
            # Noninteractive Bash otherwise sources BASH_ENV even with --norc.
            shell_environment.pop('BASH_ENV', None)
            shell_environment.pop('ENV', None)
            try:
                response = subprocess.run(['/bin/bash', '--noprofile', '--norc', '-c',
                    '. "$NVM_DIR/nvm.sh" >/dev/null && printf "%s" "$PATH"'],
                    cwd=root, env=shell_environment, capture_output=True, text=True,
                    check=True, timeout=15)
            except (OSError, subprocess.SubprocessError) as error:
                raise ValueError('Codex environment preparation failed; check this account\'s '
                                 'NVM default and Node installation separately') from error
            environment['PATH'] = response.stdout
        return environment

    def readiness(self, root, environment):
        environment = self.prepare_environment(root, environment)
        executable = self.executable(environment)
        try:
            subprocess.run([executable, 'login', 'status'], cwd=root, env=environment,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                           check=True, timeout=15)
        except (OSError, subprocess.SubprocessError) as error:
            raise ValueError(f'Codex login is not ready for executing checkout {root}; '
                             'check the CLI and run codex login separately as this account, '
                             'then rerun ./setup.sh') from error
        return 'Codex login verified for this account; model access is checked before each workflow'

    def resolve_profile(self, role: ProfileRole, *, model=None, effort=None) -> ModelProfile:
        if role == 'impact_triage':
            # Failure impact always starts at this tier, independently of the
            # caller's unit-repair defaults. Capacity recovery preserves effort.
            profile = ModelProfile('gpt-6.1-sol', 'high')
            if ((model is not None and model != profile.model)
                    or (effort is not None and effort != profile.effort)):
                raise ValueError('impact triage requires gpt-6.1-sol with high effort')
            return profile
        if role in ('implementation', 'repair', 'translator', 'commit_helper', 'conflict_resolver'):
            default = ModelProfile('gpt-6.1-sol', 'medium' if role == 'repair' else 'high')
        elif role in ROLES:
            # Role assets remain the authority for their pinned native profiles.
            with Path(__file__).with_name(ROLES[role][1]).open('rb') as stream:
                config = tomllib.load(stream)
            default = ModelProfile(config['model'], config['model_reasoning_effort'])
        else:
            raise ValueError('unsupported agent model profile')
        model = model or default.model
        if role == 'repair' and model != default.model:
            raise ValueError('fix-tests model must be ' + default.model)
        if role == 'translator' and model.endswith('-sol') and model != default.model:
            raise ValueError('Sol must be ' + default.model)
        return ModelProfile(model, effort or default.effort)

    def capacity_fallback(self, model):
        return 'gpt-6-astra' if model == 'gpt-6.1-sol' else None

    def executable(self, environment):
        executable = shutil.which('codex', path=environment.get('PATH', ''))
        if executable is None:
            raise ValueError('Codex CLI is missing; install and authenticate it before running this launcher')
        return executable

    def preflight(self, request, environment, profiles=()):
        """Read the native catalogue; never install, log in or submit a task.

        This checks advertised model/effort support, not live model access or
        transport compatibility. Native authentication failures stay blockers.
        """
        executable = self.executable(environment)
        try:
            response = subprocess.run([executable, 'debug', 'models'], env=environment,
                                      cwd=request.root, capture_output=True, text=True,
                                      check=True, timeout=30)
        except (OSError, subprocess.SubprocessError) as error:
            reason = ('timed out after 30 seconds' if isinstance(error, subprocess.TimeoutExpired) else
                      f'exited {error.returncode}' if isinstance(error, subprocess.CalledProcessError) else
                      'could not execute the CLI')
            raise ValueError(f'Codex model preflight {reason}; check CLI readiness and authentication '
                             'separately before retrying this launcher') from error
        try:
            catalog = json.loads(response.stdout)
        except ValueError as error:
            raise ValueError('Codex returned an invalid model catalog') from error
        entries = catalog.get('models') if isinstance(catalog, dict) else None
        if not isinstance(entries, list):
            raise ValueError('Codex returned an invalid model catalog')
        required = [ModelProfile(request.model, request.effort), *profiles]
        delegation = request.delegation
        if delegation.enabled:
            if delegation.model is not None or delegation.effort is not None:
                required.append(ModelProfile(delegation.model or request.model,
                                             delegation.effort or request.effort))
            for role in delegation.roles:
                required.append(self.resolve_profile(role) if role != 'translator' else
                                self.resolve_profile(role, model=delegation.model or request.model,
                                                     effort=delegation.effort or request.effort))
        for model, effort in dict.fromkeys(required):
            if not any(isinstance(entry, dict) and entry.get('visibility') == 'list'
                       and entry.get('slug') == model
                       and isinstance(entry.get('supported_reasoning_levels'), list)
                       and any(isinstance(level, dict) and level.get('effort') == effort
                               for level in entry['supported_reasoning_levels'])
                       for entry in entries):
                raise ValueError(f'Codex model catalog has no listed {model} with {effort} reasoning; '
                                 'no fallback was selected')

    def prepare_session(self, request: SessionRequest, environment: dict[str, str]) -> PreparedSession:
        environment = self.prepare_environment(request.root, environment)
        executable = self.executable(environment)
        if request.permissions not in ('workspace', 'read_only'):
            raise ValueError('unsupported agent write boundary')
        if request.run is not None and request.schema is None:
            raise ValueError('agent result output requires a schema')
        if request.interactive and (request.run is None or request.schema is None):
            raise ValueError('interactive agent sessions require an owned run and schema')
        if request.interactive and request.extra_directories:
            raise ValueError('interactive agent sessions do not yet support extra directories')
        delegation = request.delegation
        if (type(delegation.max_concurrent) is not int or delegation.max_concurrent < 1
                or type(delegation.max_depth) is not int or delegation.max_depth < 1
                or any(role not in ROLES for role in delegation.roles)):
            raise ValueError('unsupported agent delegation requirements')
        sandbox = 'read-only' if request.permissions == 'read_only' else 'workspace-write'
        config = []

        def setting(key, value):
            config.extend(('-c', key + '=' + json.dumps(value)))

        setting('model_reasoning_effort', request.effort)
        setting('history.persistence', 'none')
        setting('features.memories', False)
        setting('features.multi_agent', delegation.enabled)
        setting('features.multi_agent_v2', False)
        setting('agents.enabled', delegation.enabled)
        setting('developer_instructions', GOAL_INSTRUCTIONS + request.instructions
                + SUBAGENT_CONTEXT_INSTRUCTIONS + BACKEND_REVIEW_INSTRUCTIONS)
        setting('agents.max_concurrent_threads_per_session', delegation.max_concurrent)
        setting('agents.max_depth', delegation.max_depth)
        if delegation.model is not None:
            setting('agents.default_subagent_model', delegation.model)
        if delegation.effort is not None:
            setting('agents.default_subagent_reasoning_effort', delegation.effort)
        for role in delegation.roles:
            name, filename, description = ROLES[role]
            setting(f'agents.{name}.description', description)
            setting(f'agents.{name}.config_file', str(Path(__file__).with_name(filename)))
        if request.standard_speed:
            setting('service_tier', 'default')
            setting('features.fast_mode', False)
        from host_compute import VARIABLE as COMPUTE
        compute_environment = ((COMPUTE, os.environ[COMPUTE]),) if COMPUTE in os.environ else ()
        for name, value in (*request.shell_environment, *compute_environment):
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
                raise ValueError('invalid agent shell environment name')
            setting(f'shell_environment_policy.set.{name}', value)
        if request.interactive:
            setting('approval_policy', 'never')
            setting('sandbox_mode', sandbox)
            argv = [executable, 'app-server', '--listen', 'stdio://', *config]
        else:
            argv = [executable, '--ask-for-approval', 'never', 'exec',
                    '--sandbox', sandbox, '--model', request.model, *config,
                    '--json', '--color', 'never', '--cd', str(request.root)]
            if request.run is not None:
                argv += ['--output-schema', str(request.schema),
                         '--output-last-message', str(request.run / 'agent-result.json')]
            for directory in request.extra_directories:
                argv += ['--add-dir', str(directory)]
            argv.append('-')
        child_environment = dict(environment)
        for name in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID'):
            child_environment.pop(name, None)
        return PreparedSession(self, request, tuple(argv), child_environment, request.root,
                               protocol=CodexProtocol(request) if request.interactive else None,
                               presentation=None if request.interactive else CodexBatchPresentation())


def batch_failure(error, *, terminal):
    """Only a terminal native error can classify a failed batch as capacity."""
    code = error.get('codexErrorInfo', error.get('codex_error_info')) if isinstance(error, dict) else None
    message = error.get('message', error) if isinstance(error, dict) else error
    # exec's ThreadErrorEvent may expose only the exact ServerOverloaded display.
    capacity = terminal and isinstance(error, dict) and (
        code == 'serverOverloaded' if code is not None else
        message == 'Selected model is at capacity. Please try a different model.')
    return SessionEvent('failure', {
        'message': message, 'context': 'turn failed' if terminal else 'error',
        'details': {'codex_error_info': 'serverOverloaded' if capacity else code},
        'capacity': capacity, 'terminal': terminal, 'diagnostic': error})


class CodexBatchPresentation:
    """Codex exec JSONL decoding, with no result or process authority."""

    def __init__(self):
        self.pending = b''

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            yield from self.line(line)

    def finish(self):
        if self.pending:
            pending, self.pending = self.pending, b''
            yield from self.line(pending)

    def line(self, raw):
        text = raw.decode('utf-8', errors='replace')
        try:
            packet = json.loads(text)
        except ValueError:
            yield SessionEvent('diagnostic', {'text': text})
            return
        try:
            yield from self.event(packet)
        except (KeyError, TypeError, AttributeError, ValueError):
            # Malformed/unknown output is inert, never a workflow result.
            yield SessionEvent('diagnostic', {'value': packet})

    def event(self, packet):
        kind = packet['type']
        if kind in ('thread.started', 'turn.started'):
            return
        if kind == 'turn.completed':
            # Preserve the CLI's per-turn counters without inventing helper usage.
            yield SessionEvent('usage', {'usage': packet.get('usage')})
            yield SessionEvent('turn_completed', {'interrupted': False})
        elif kind in ('error', 'turn.failed'):
            yield batch_failure(packet.get('error', packet) if kind == 'turn.failed'
                                else packet.get('message', packet.get('error', packet)),
                                terminal=kind == 'turn.failed')
        elif kind in ('item.started', 'item.updated', 'item.completed'):
            item = packet['item']
            category = item['type']
            complete = kind == 'item.completed'
            if category == 'reasoning':
                return
            if category == 'agent_message':
                text = item['text'] if complete else item.get('text', '')
                yield SessionEvent('text', {'id': item.get('id'), 'text': text,
                                           'complete': complete})
            elif category in ('command_execution', 'file_change', 'todo_list',
                              'sub_agent_activity', 'collab_tool_call', 'mcp_tool_call', 'web_search'):
                yield SessionEvent('item', {'item': item, 'complete': complete})
            else:
                yield SessionEvent('diagnostic', {'value': packet})
        else:
            yield SessionEvent('diagnostic', {'value': packet})


class CodexProtocol:
    """App-server wire state for one coordinator, beneath shared input gates."""

    def __init__(self, request):
        self.request = request
        self.thread = self.turn = None
        self.completed = False
        self.pending = b''
        self.requests = {}
        self.counter = 0
        self.outgoing = bytearray()

    @property
    def ready(self):
        return self.thread is not None

    @property
    def active_turn(self):
        return self.turn is not None

    @property
    def turn_requests_pending(self):
        return any(method in ('turn/start', 'turn/steer', 'turn/interrupt')
                   for method, _ in self.requests.values())

    def encode(self, packet):
        self.outgoing.extend((json.dumps(packet) + '\n').encode('utf-8'))

    def rpc(self, method, params):
        self.counter += 1
        self.requests[self.counter] = (method, params)
        self.encode({'id': self.counter, 'method': method, 'params': params})

    def start(self):
        self.schema = json.loads(self.request.schema.read_text())
        self.rpc('initialize', {'clientInfo': {'name': 'onpc_launcher',
                 'title': 'Task launcher', 'version': '1.0'},
                 'capabilities': {'experimentalApi': True}})

    def start_turn(self, text):
        self.completed = False
        self.rpc('turn/start', {'threadId': self.thread,
                 'input': [{'type': 'text', 'text': text}], 'outputSchema': self.schema})

    def steer(self, text):
        self.rpc('turn/steer', {'threadId': self.thread, 'expectedTurnId': self.turn,
                 'input': [{'type': 'text', 'text': text}]})

    def interrupt(self):
        self.rpc('turn/interrupt', {'threadId': self.thread, 'turnId': self.turn})

    def feed(self, data):
        lines = (self.pending + data).split(b'\n')
        self.pending = lines.pop()
        for line in lines:
            yield from self.event(json.loads(line))

    def failure(self, context, error):
        code = error.get('codexErrorInfo') if isinstance(error, dict) else None
        detail = (error.get('message') or str(error)) if isinstance(error, dict) else str(error)
        message = f"Codex {context}{f' ({code})' if code else ''}: {detail}"
        return SessionEvent('failure', {
            'message': message, 'context': context, 'details': {'codex_error_info': code},
            'task_error': 'OpenAI stopped this session under its cybersecurity safeguards.'
                          if code == 'cyberPolicy' else message,
            'capacity': context == 'turn failed' and code == 'serverOverloaded'})

    def event(self, packet):
        if 'method' not in packet:
            method, params = self.requests.pop(packet['id'])
            if 'error' in packet:
                if method == 'turn/steer' and (self.completed or self.turn is None):
                    # Completion raced with steering. Deliver once as a new turn.
                    yield SessionEvent('retry_input', {'text': params['input'][0]['text']})
                elif method == 'turn/interrupt' and self.completed:
                    yield SessionEvent('discard_result', {})
                else:
                    yield self.failure(method, packet['error'])
                return
            result = packet['result']
            if method == 'initialize':
                self.encode({'method': 'initialized', 'params': {}})
                self.rpc('thread/start', {'model': self.request.model, 'cwd': str(self.request.root),
                         'approvalPolicy': 'never',
                         'sandbox': 'read-only' if self.request.permissions == 'read_only' else 'workspace-write',
                         'ephemeral': False})
            elif method == 'thread/start':
                self.thread = result['thread']['id']
                yield SessionEvent('ready', {})
            elif method == 'turn/start':
                if not self.completed:
                    self.turn = result['turn']['id']
            return
        method, params = packet['method'], packet.get('params', {})
        if 'id' in packet:
            # Never grant server approvals or execute client tools.
            self.encode({'id': packet['id'], 'error': {'code': -32601,
                         'message': 'Client operation unavailable; report a workflow blocker.'}})
            return
        # Adviser notifications must not replace the coordinator's turn/result.
        if params.get('threadId') not in (None, self.thread):
            return
        if method == 'turn/started':
            self.turn = params['turn']['id']
        elif method == 'item/agentMessage/delta':
            if params.get('turnId') == self.turn:
                yield SessionEvent('text_delta', {'id': params['itemId'], 'text': params['delta']})
        elif method in ('item/started', 'item/completed'):
            yield from self.item(params['item'], method == 'item/completed')
        elif method == 'item/commandExecution/outputDelta':
            if params.get('turnId') == self.turn:
                yield SessionEvent('command_output', {'id': params['itemId'], 'text': params['delta']})
        elif method == 'thread/tokenUsage/updated':
            usage = params['tokenUsage']['last']
            yield SessionEvent('usage', {'usage': {'input_tokens': usage.get('inputTokens'),
                'cached_input_tokens': usage.get('cachedInputTokens'),
                'output_tokens': usage.get('outputTokens'),
                'reasoning_output_tokens': usage.get('reasoningOutputTokens')}})
        elif method == 'turn/completed':
            turn = params['turn']
            self.turn = None
            self.completed = True
            if turn['status'] == 'failed':
                yield self.failure('turn failed', turn.get('error'))
            else:
                yield SessionEvent('turn_completed', {'interrupted': turn['status'] == 'interrupted'})
        elif method in ('error', 'warning'):
            yield SessionEvent('notice', {'text': str(params.get('message', params))})

    def item(self, item, complete):
        kind = item['type']
        if kind == 'agentMessage':
            text = item['text'] if complete else item.get('text', '')
            yield SessionEvent('text', {'id': item['id'], 'text': text,
                                       'complete': complete})
            return
        if kind == 'commandExecution':
            item = {'id': item['id'], 'type': 'command_execution', 'command': item['command'],
                    'aggregated_output': item.get('aggregatedOutput', ''),
                    'exit_code': item.get('exitCode'), 'status': item.get('status')}
        elif kind == 'fileChange':
            changes = [dict(change, kind=change['kind'].get('type', 'update')
                            if isinstance(change.get('kind'), dict) else change.get('kind', 'update'))
                       for change in item['changes']]
            item = dict(item, type='file_change', changes=changes)
        elif kind in ('mcpToolCall', 'webSearch', 'subAgentActivity'):
            item = dict(item, type={'mcpToolCall': 'mcp_tool_call', 'webSearch': 'web_search',
                                   'subAgentActivity': 'sub_agent_activity'}[kind])
        elif kind in ('reasoning', 'userMessage'):
            return
        else:
            if complete:
                yield SessionEvent('diagnostic', {'value': item})
            return
        yield SessionEvent('item', {'item': item, 'complete': complete})

    def finalize_result(self, text):
        try:
            value = json.loads(text)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None
