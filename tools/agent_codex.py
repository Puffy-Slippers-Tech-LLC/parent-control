"""Codex-native session configuration beneath shared process supervision."""

import json
from pathlib import Path
import re
import shutil

from agent_adapter import PreparedSession, SessionRequest


SESSION_GOAL = ('Simple, lean, robust, do not overengineer. If a problem can be solved '
                'by simplier approaches, do not use more complex ones')

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
    'adviser': ('e2e_adviser', 'write_e2e_adviser.toml',
        'Bounded read-only diagnosis or review; no implementation or tests'),
    'translator': ('whatsnew_translator', 'sync_whatsnew_translator.toml',
        'Read-only latest-release translator/reviewer'),
}


class CodexAdapter:
    name = 'codex'

    def prepare_session(self, request: SessionRequest, environment: dict[str, str]) -> PreparedSession:
        executable = shutil.which('codex')
        if executable is None:
            raise ValueError('Codex CLI is missing; install and authenticate it before running this launcher')
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
        for name, value in request.shell_environment:
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
        return PreparedSession(self, request, tuple(argv), child_environment, request.root)
