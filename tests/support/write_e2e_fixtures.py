"""Shared queue and agent-result fixtures for write-e2e unit tests."""

import write_e2e as workflow


def prepare(root):
    (root / workflow.PLAN).parent.mkdir(parents=True)
    (root / workflow.PLAN).write_text('Next task: **001 — [First](first.md)**.\n')
    (root / workflow.QUEUE).write_text(
        '| [ ] | 001 | First |\n| [ ] | 002 | Second |\n'
        '## Deferred future work\n| [ ] | 999 | Deferred |\n')


def reply(status='ready_for_vm', live='failed', **values):
    return {'status': status, 'task_id': '001', 'summary': 'Host checks passed.',
            'handoff': 'Continue task 001; run its exact live selector with Astra High.',
            'blocker': {'explanation': 'The VM check is waiting because the duration checks disagree.',
                        'question': 'Which duration format should the launcher use?',
                        'options': ['Use the compact duration format and update its checks.',
                                    'Restore the long duration format in the launcher.',
                                    'Inspect the evidence before choosing a duration format.']}
                       if status == 'blocked' else None,
            'host_validated': True, 'live_result': live,
            'stage_paths': [workflow.PLAN, workflow.QUEUE] if status == 'task_complete' else [],
            **values}
