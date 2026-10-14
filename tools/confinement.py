#!/usr/bin/env python3
"""Run confinement plan steps sequentially, with at most 16 Codex sessions."""

from pathlib import Path
import re
import subprocess
import sys

from detached_launcher import environment

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / 'docs/confinement.md'
MAX_LOOPS = 16
PROMPT = """Execute next step in docs/confinement.md
# Requirements
- Drive subagents (stick to 6.1-sol of variant efforts) as needed to divide and conquer especially with lower-tier agent on routine monitoring and coverage refreshes
- Before writing code, have full understanding of existing relevant code
- No hacky code allowed. Must write lean code with supported APIs
- DO NOT ask for approval, DON't. Must use established auto approvals.
- Probe live VM for troubleshooting, use live VM to validate fixes before full e2e tests"""


def all_done():
    """Include both task rows and phase exit gates in the plan."""
    states = re.findall(r'^\|\s*\[([ xX])\]\s*\|', PLAN.read_text(encoding='utf-8'), re.MULTILINE)
    if not states:
        raise ValueError('no task checkbox rows found in docs/confinement.md')
    return all(state.lower() == 'x' for state in states)


def main():
    # Automatic review handles eligible approvals without waiting for a person.
    # This flag also selects workspace-write; "never" would disable review.
    command = [
        'codex', 'exec', '--approve-for-me', '--ephemeral',
        '--model', 'gpt-6.1-sol',
        '-c', 'model_reasoning_effort="xhigh"',
        '-c', 'features.multi_agent=true',
        '-c', 'features.multi_agent_v2=false',
        '-c', 'agents.enabled=true',
        '-c', 'agents.default_subagent_model="gpt-6.1-sol"',
        '-c', 'agents.default_subagent_reasoning_effort="medium"',
        '--cd', str(ROOT), '-',
    ]
    for loop in range(1, MAX_LOOPS + 1):
        if all_done():
            print('All confinement tasks are done.', flush=True)
            return 0
        print(f'Confinement loop {loop}/{MAX_LOOPS}', flush=True)
        result = subprocess.run(command, input=PROMPT, text=True, cwd=ROOT, env=environment())
        if result.returncode:
            print(f'Codex failed with exit code {result.returncode}; stopping.', file=sys.stderr)
            return 1
    if all_done():
        print('All confinement tasks are done.', flush=True)
        return 0
    print(f'Stopped after {MAX_LOOPS} loops; confinement tasks remain.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
    except (OSError, ValueError) as error:
        print(f'confinement: {error}', file=sys.stderr)
        sys.exit(1)
