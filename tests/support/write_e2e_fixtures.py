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
            'handoff': 'Continue task 001 with the launcher-selected coordinator.',
            'blocker': {'explanation': 'The VM check is waiting because the duration checks disagree.',
                        'question': 'Which duration format should the launcher use?',
                        'options': ['Use the compact duration format and update its checks.',
                                    'Restore the long duration format in the launcher.',
                                    'Inspect the evidence before choosing a duration format.']}
                       if status == 'blocked' else None,
            'host_validated': True, 'live_result': live,
            'stage_paths': [workflow.PLAN, workflow.QUEUE] if status == 'task_complete' else [],
            'progress': {'failure_checkpoint': 'qualification:entry' if live == 'failed' else '',
                         'furthest_checkpoint': 'qualification:prepared',
                         'repair_outcome': 'stalled' if status == 'stalled' else
                                           'diagnostic' if status == 'ready_for_vm' else 'not_applicable'},
            **values}


def prerequisite_writes(no_dependencies='Baseline'):
    return {
        workflow.PLAN: 'Next task: **000a — [Prerequisite](E2E-Tasks/000a.md)**.\n',
        workflow.QUEUE: f'| [ ] | 000a | [Prerequisite](E2E-Tasks/000a.md) | {no_dependencies} | Setup |\n'
                        '| [ ] | 001 | [First](E2E-Tasks/001.md) | 000a | Consumer |\n'
                        '| [ ] | 002 | Second | 001 | Later |\n',
        'docs/TestAutomation/E2E-Tasks/000a.md': 'Implement and qualify the prerequisite.\n',
        'docs/TestAutomation/E2E-Tasks/001.md': 'Resume the incomplete consumer after 000a.\n',
    }
