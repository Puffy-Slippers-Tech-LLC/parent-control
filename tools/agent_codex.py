"""Codex-native session configuration and protocol beneath shared supervision."""

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time

from agent_adapter import (AgentSelection, ModelProfile, PreparedSession, ProfileRole,
                           SessionEvent, SessionRequest, resolve_workflow_profile,
                           resolve_capacity_fallback)


SESSION_GOAL = ('Simple, lean, robust; do not overengineer. Prefer solutions that simplify '
                'the resulting codebase as a whole, not merely minimize the patch. '
                'Keep refactoring within the task’s scope.')

GOAL_INSTRUCTIONS = f"""Before task work, use get_goal to inspect this session's actual
Codex goal state. If absent or complete, call create_goal with objective:
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

SUBAGENT_CONTEXT_INSTRUCTIONS = """Each new task starts with fresh context.
On every spawn_agent call, explicitly set fork_turns="none".
Never omit fork_turns or use "all". Give every helper a self-contained assignment
with its exact scope, paths, relevant instructions, current evidence and disjoint
write ownership. This applies to workers, monitors, advisers and backend reviewers;
it does not authorize delegation beyond the launcher's existing policy.

"""

BACKEND_REVIEW_INSTRUCTIONS = """For product backend code involving core functionalities,
AGENTS.md requires an independent code review by the backend_reviewer agent
(using its configured metadata profile) before completing the changes. This mandate applies across
all launchers, including repair, recovery and optimization sessions. It overrides
coordinator-model and no-delegation rules only for this required review; keep the launcher's
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


def session_instructions(request):
    return (GOAL_INSTRUCTIONS + request.instructions + SUBAGENT_CONTEXT_INSTRUCTIONS
            + BACKEND_REVIEW_INSTRUCTIONS)


class CodexAdapter:
    name = 'codex'

    def __init__(self, root=None):
        self.selection = AgentSelection(self.name, root or Path(__file__).resolve().parents[1])

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
        workflows = {
            'implementation': 'execute-plan', 'translator': 'sync-whatsnew',
            'commit_helper': 'commit-helper', 'conflict_resolver': 'conflict-resolver',
            'startup_pull_recovery': 'startup-pull-recovery',
            'worker': 'plan-worker', 'monitor': 'plan-monitor',
            'backend_reviewer': 'backend-reviewer',
        }
        if role not in workflows:
            raise ValueError('unsupported agent model profile')
        return resolve_workflow_profile(workflows[role], selection=self.selection,
                                        model=model, effort=effort)

    def capacity_fallback(self, model):
        return resolve_capacity_fallback(model, selection=self.selection)

    def helper_profile(self, request, role):
        delegation = request.delegation
        return (self.resolve_profile(role, model=delegation.model or request.model,
                                     effort=delegation.effort or request.effort)
                if role == 'translator' else self.resolve_profile(role))

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
                required.append(self.helper_profile(request, role))
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
        if request.interactive and (request.run is None or request.schema is None):
            raise ValueError('interactive agent sessions require an owned run and schema')
        goal_session = request.run is not None and request.schema is None
        if goal_session and (request.continuation_key is not None or request.thread_id is not None):
            raise ValueError('plain goal sessions always start a fresh native thread')
        if (request.interactive or goal_session) and request.extra_directories:
            raise ValueError('app-server agent sessions do not yet support extra directories')
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
        if goal_session:
            setting('features.goals', True)
        setting('features.multi_agent', delegation.enabled)
        setting('features.multi_agent_v2', False)
        setting('agents.enabled', delegation.enabled)
        setting('developer_instructions', session_instructions(request))
        setting('agents.max_concurrent_threads_per_session', delegation.max_concurrent)
        setting('agents.max_depth', delegation.max_depth)
        if delegation.model is not None:
            setting('agents.default_subagent_model', delegation.model)
        if delegation.effort is not None:
            setting('agents.default_subagent_reasoning_effort', delegation.effort)
        for role in delegation.roles if delegation.enabled else ():
            name, filename, description = ROLES[role]
            setting(f'agents.{name}.description', description)
            asset = Path(__file__).with_name(filename)
            # Run-less preparations are catalogue inspection only. Supervision
            # always supplies its owned run before starting the native session.
            if request.run is not None:
                profile = self.helper_profile(request, role)
                text = (f'model = {json.dumps(profile.model)}\n'
                        f'model_reasoning_effort = {json.dumps(profile.effort)}\n'
                        + asset.read_text())
                asset = request.run / f'agent-{role}.toml'
                temporary = asset.with_suffix('.tmp')
                temporary.write_text(text, encoding='utf-8')
                temporary.chmod(0o600)
                temporary.replace(asset)
            setting(f'agents.{name}.config_file', str(asset))
        if request.standard_speed:
            setting('service_tier', 'default')
            setting('features.fast_mode', False)
        from host_compute import VARIABLE as COMPUTE
        compute_environment = ((COMPUTE, os.environ[COMPUTE]),) if COMPUTE in os.environ else ()
        for name, value in (*request.shell_environment, *compute_environment):
            if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', name):
                raise ValueError('invalid agent shell environment name')
            setting(f'shell_environment_policy.set.{name}', value)
        if request.interactive or goal_session:
            setting('approval_policy', 'never')
            setting('sandbox_mode', sandbox)
            argv = [executable, 'app-server', '--listen', 'stdio://', *config]
        else:
            argv = [executable, '--ask-for-approval', 'never', 'exec',
                    '--sandbox', sandbox, '--model', request.model, *config,
                    '--json', '--color', 'never', '--cd', str(request.root)]
            if request.run is not None and request.schema is not None:
                argv += ['--output-schema', str(request.schema),
                         '--output-last-message', str(request.run / 'agent-result.json')]
            for directory in request.extra_directories:
                argv += ['--add-dir', str(directory)]
            argv.append('-')
        child_environment = dict(environment)
        for name in ('CODEX_THREAD_ID', 'CODEX_PARENT_THREAD_ID', 'CODEX_SESSION_ID'):
            child_environment.pop(name, None)
        protocol = (CodexGoalProtocol(request) if goal_session else
                    CodexProtocol(request) if request.interactive else None)
        return PreparedSession(self, request, tuple(argv), child_environment, request.root,
                               protocol=protocol,
                               presentation=None if protocol is not None else CodexBatchPresentation())


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


class CodexWire:
    """App-server framing and presentation shared by independent lifecycles."""

    def __init__(self, request):
        self.request = request
        self.thread = self.turn = None
        self.pending = b''
        self.requests = {}
        self.counter = 0
        self.outgoing = bytearray()

    def encode(self, packet):
        self.outgoing.extend((json.dumps(packet) + '\n').encode('utf-8'))

    def rpc(self, method, params):
        self.counter += 1
        self.requests[self.counter] = (method, params)
        self.encode({'id': self.counter, 'method': method, 'params': params})

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


class CodexProtocol(CodexWire):
    """Structured app-server conversation beneath shared workflow input gates."""

    def __init__(self, request):
        super().__init__(request)
        self.completed = False
        self.recovery = None
        self.schema_retried = False
        self.discarded_turns = set()
        self.interrupted = False

    @property
    def ready(self):
        return self.thread is not None

    @property
    def active_turn(self):
        return self.recovery is not None or self.turn is not None

    @property
    def turn_requests_pending(self):
        return self.recovery is not None or any(method in ('turn/start', 'turn/steer', 'turn/interrupt')
                   for method, _ in self.requests.values())

    def start(self):
        self.schema = json.loads(self.request.schema.read_text())
        self.rpc('initialize', {'clientInfo': {'name': 'onpc_launcher',
                 'title': 'Task launcher', 'version': '1.0'},
                 'capabilities': {'experimentalApi': True}})

    def start_turn(self, text):
        self.completed = False
        self.interrupted = False
        self.rpc('turn/start', {'threadId': self.thread,
                 'input': [{'type': 'text', 'text': text}], 'outputSchema': self.schema,
                 'model': self.request.model, 'effort': self.request.effort})

    def steer(self, text):
        self.rpc('turn/steer', {'threadId': self.thread, 'expectedTurnId': self.turn,
                 'input': [{'type': 'text', 'text': text}]})

    def interrupt(self):
        self.interrupted = True
        if self.recovery is not None:
            # Recovery is already draining the native turn. Honor the user's
            # interruption without issuing a second interrupt or retrying input.
            self.recovery['interrupted'] = True
            return
        self.rpc('turn/interrupt', {'threadId': self.thread, 'turnId': self.turn})

    def recovered_input(self):
        """An interrupt acknowledgment and terminal turn must both drain first."""
        if self.recovery['acknowledged'] and self.recovery['completed']:
            text = self.recovery['text']
            interrupted = self.recovery['interrupted']
            self.recovery = None
            self.turn = None
            self.completed = interrupted
            if interrupted:
                yield SessionEvent('turn_completed', {'interrupted': True})
            else:
                yield SessionEvent('retry_input', {'text': text, 'recovered': True})

    def poll(self):
        if self.recovery is not None and time.monotonic() >= self.recovery['deadline']:
            raise ValueError('Codex active-turn recovery timed out; saved input and conversation were retained')

    def event(self, packet):
        if 'method' not in packet:
            method, params = self.requests.pop(packet['id'])
            if 'error' in packet:
                if (method == 'turn/start' and not self.schema_retried
                        and 'ActiveTurnOutputSchemaMismatch' in str(packet['error'].get('message', ''))):
                    # Resume can start an automatic goal turn without our schema.
                    # Keep this thread and input; never relax the result schema or
                    # retry arbitrary provider/authentication/policy failures.
                    self.schema_retried = True
                    self.recovery = dict(text=params['input'][0]['text'], turn=None,
                                         acknowledged=False, completed=False, completed_turn=None,
                                         interrupted=self.interrupted, deadline=time.monotonic() + 30)
                    self.rpc('thread/read', {'threadId': self.thread, 'includeTurns': True})
                    yield SessionEvent('discard_result', {})
                    yield SessionEvent('notice', {'text': 'Draining an active conversation turn before retrying the saved input.'})
                elif (method == 'turn/interrupt' and self.recovery is not None
                      and self.recovery['completed']):
                    # The selected turn can finish before its interrupt is
                    # handled. Its terminal notification already drained it.
                    self.recovery['acknowledged'] = True
                    yield from self.recovered_input()
                elif method == 'turn/steer' and (self.completed or self.turn is None):
                    # Completion raced with steering. Deliver once as a new turn.
                    yield SessionEvent('retry_input', {'text': params['input'][0]['text']})
                elif method == 'turn/interrupt' and self.completed:
                    yield SessionEvent('discard_result', {})
                else:
                    yield self.failure(method, packet['error'])
                return
            result = packet['result']
            if method == 'thread/read' and self.recovery is not None:
                if result['thread']['id'] != self.thread:
                    raise ValueError('agent recovery thread identity changed')
                active = [turn for turn in result['thread']['turns'] if turn['status'] == 'inProgress']
                if len(active) > 1:
                    raise ValueError('agent recovery found multiple active turns')
                if active:
                    turn = active[0]['id']
                    self.discarded_turns.add(turn)
                    self.recovery['turn'] = turn
                    if self.recovery['completed_turn'] == turn:
                        self.recovery.update(acknowledged=True, completed=True)
                        yield from self.recovered_input()
                    else:
                        self.rpc('turn/interrupt', {'threadId': self.thread, 'turnId': turn})
                else:
                    # Completion raced the read; there is nothing left to stop.
                    self.recovery.update(acknowledged=True, completed=True)
                    yield from self.recovered_input()
            elif method == 'turn/interrupt' and self.recovery is not None:
                self.recovery['acknowledged'] = True
                yield from self.recovered_input()
            elif method == 'initialize':
                self.encode({'method': 'initialized', 'params': {}})
                params = {'model': self.request.model, 'cwd': str(self.request.root),
                         'approvalPolicy': 'never',
                         'developerInstructions': session_instructions(self.request),
                         'sandbox': 'read-only' if self.request.permissions == 'read_only' else 'workspace-write'}
                if self.request.thread_id is None:
                    self.rpc('thread/start', dict(params, ephemeral=False))
                else:
                    self.rpc('thread/resume', dict(params, threadId=self.request.thread_id,
                                                   excludeTurns=True))
            elif method in ('thread/start', 'thread/resume'):
                self.thread = result['thread']['id']
                if self.request.thread_id is not None and self.thread != self.request.thread_id:
                    raise ValueError('resumed agent thread identity changed')
                yield SessionEvent('ready', {'thread_id': self.thread})
            elif method == 'turn/start':
                self.schema_retried = False
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
        if self.recovery is not None:
            # Neither results nor failures from the displaced turn belong to
            # the new assignment. Retain only its terminal cleanup boundary.
            if method == 'turn/completed':
                turn = params['turn']['id']
                self.discarded_turns.add(turn)
                self.recovery['completed_turn'] = turn
                if turn == self.recovery['turn']:
                    self.recovery['completed'] = True
                    yield from self.recovered_input()
            return
        if params.get('turnId', params.get('turn', {}).get('id')) in self.discarded_turns:
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

    def finalize_result(self, text):
        try:
            value = json.loads(text)
        except ValueError:
            return None
        return value if isinstance(value, dict) else None


class CodexGoalProtocol(CodexWire):
    """One fresh assignment; Codex alone schedules automatic goal continuation.

    Unlike exec (which unsubscribes after its initial turn), this connection
    remains attached while the native goal is active. A final message or a
    completed turn is not session completion. Watch can steer the live turn;
    no output schema, resume or launcher-generated follow-up turns participate.
    """

    def __init__(self, request):
        super().__init__(request)
        self.started = self.completed = self.done = False
        self.status = 1
        self.goal = None

    def start(self):
        self.rpc('initialize', {'clientInfo': {'name': 'onpc_launcher',
                 'title': 'Task launcher', 'version': '1.0'},
                 'capabilities': {'experimentalApi': True}})

    def start_turn(self, text):
        if self.started:
            raise ValueError('plain goal session already received its assignment')
        self.started = True
        self.rpc('turn/start', {'threadId': self.thread,
                 'input': [{'type': 'text', 'text': text}],
                 'model': self.request.model, 'effort': self.request.effort})

    def poll(self):
        pass

    def steer(self, text):
        self.rpc('turn/steer', {'threadId': self.thread, 'expectedTurnId': self.turn,
                 'input': [{'type': 'text', 'text': text}]})

    def settle(self):
        if not self.done and self.completed and self.turn is None and not self.requests:
            # Native continuation owns active goals. An ordinary session end
            # supplies no test verdict; the runner's results decide what remains.
            self.done = self.goal is None or self.goal.get('status') != 'active'
            if self.done:
                self.status = 0

    def event(self, packet):
        if 'method' not in packet:
            method, params = self.requests.pop(packet['id'])
            if 'error' in packet:
                if method == 'turn/steer':
                    # A turn may end after the mailbox is drained. Do not
                    # interrupt the goal or replay input with unknown delivery.
                    yield SessionEvent('notice', {'text':
                        'Chat message was not accepted; review the session before sending again.\n'
                        + params['input'][0]['text'] + '\n' + str(packet['error'])})
                    self.settle()
                    return
                self.done = True
                self.status = 1
                yield self.failure(method, packet['error'])
                return
            result = packet['result']
            if method == 'initialize':
                self.encode({'method': 'initialized', 'params': {}})
                self.rpc('thread/start', {'model': self.request.model,
                    'cwd': str(self.request.root), 'approvalPolicy': 'never',
                    'developerInstructions': session_instructions(self.request),
                    'sandbox': 'read-only' if self.request.permissions == 'read_only' else 'workspace-write',
                    'ephemeral': False})
            elif method == 'thread/start':
                self.thread = result['thread']['id']
                yield SessionEvent('ready', {'thread_id': self.thread})
            elif method == 'turn/start':
                if not self.completed:
                    self.turn = result['turn']['id']
            elif method == 'thread/goal/get':
                self.goal = result['goal']
                self.settle()
            elif method == 'turn/steer':
                self.settle()
            return
        method, params = packet['method'], packet.get('params', {})
        if 'id' in packet:
            self.encode({'id': packet['id'], 'error': {'code': -32601,
                         'message': 'Client operation unavailable; report a workflow blocker.'}})
            return
        if params.get('threadId') not in (None, self.thread):
            return
        if method == 'turn/started':
            self.turn = params['turn']['id']
            self.completed = False
        elif method == 'thread/goal/updated':
            self.goal = params['goal']
            self.settle()
        elif method == 'thread/goal/cleared':
            self.goal = None
            self.settle()
        elif method == 'item/agentMessage/delta':
            if params.get('turnId') == self.turn:
                yield SessionEvent('text_delta', {'id': params['itemId'], 'text': params['delta']})
        elif method in ('item/started', 'item/completed'):
            yield from self.item(params['item'], method == 'item/completed')
        elif method == 'item/commandExecution/outputDelta':
            if params.get('turnId') == self.turn:
                yield SessionEvent('command_output', {'id': params['itemId'], 'text': params['delta']})
        elif method == 'thread/tokenUsage/updated':
            usage = params.get('tokenUsage', {}).get('last') or {}
            yield SessionEvent('usage', {'usage': {'input_tokens': usage.get('inputTokens'),
                'cached_input_tokens': usage.get('cachedInputTokens'),
                'output_tokens': usage.get('outputTokens'),
                'reasoning_output_tokens': usage.get('reasoningOutputTokens')}})
        elif method == 'turn/completed':
            turn = params['turn']
            self.turn = None
            self.completed = True
            if turn['status'] in ('failed', 'interrupted'):
                self.done = True
                if turn['status'] == 'failed':
                    self.status = 1
                    yield self.failure('turn failed', turn.get('error'))
                else:
                    self.status = 130
            else:
                # Read after the terminal notification, including when a goal
                # update was omitted; never infer completion from prose.
                self.rpc('thread/goal/get', {'threadId': self.thread})
            yield SessionEvent('turn_completed', {'interrupted': turn['status'] == 'interrupted'})
        elif method in ('error', 'warning'):
            yield SessionEvent('notice', {'text': str(params.get('message', params))})
