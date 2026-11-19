"""Overall case accounting for the shared test runner."""

import json
import os


SELECTION = 'ONPC_TEST_PROGRESS_SELECTION'


def repair_selection():
    from test_results import REPAIR_QUEUE
    text = os.environ.get(SELECTION, '') if os.environ.get(REPAIR_QUEUE) == '1' else ''
    if text:
        try:
            args = json.loads(text)
            if args and isinstance(args, list) and all(isinstance(arg, str) for arg in args):
                return args
        except ValueError:
            pass
    return None


class OverallProgress:
    """Keep each group's latest counts for the full launcher selection."""

    def __init__(self):
        self.groups = {}

    def update(self, group, passed, failed, total):
        self.groups[group] = passed, failed, total
        return self.counts()

    def counts(self):
        return combine_counts(self.groups.values())


def combine_counts(counts):
    passed = failed = total = 0
    for group_passed, group_failed, group_total in counts:
        passed += group_passed
        failed += group_failed
        total = None if total is None or group_total is None else total + group_total
    return passed, failed, total


def percentage(passed, failed, total):
    return '?' if total is None else str(100 * (passed + failed) // max(total, 1))


def overall_line(passed, failed, total):
    return (f'Overall - {percentage(passed, failed, total)}% '
            f'({passed}/{failed}/{"?" if total is None else total})')


def recorded_cases(records, *, options=None):
    from test_results import same_desktop_profile
    passed, failed = set(), set()
    for record in records:
        if record['case'] and (options is None or same_desktop_profile(
                record['category'], record.get('options', []), options)):
            key = record['family'], record['category'], record['case']
            (failed if record['status'] else passed).add(key)
    return passed, failed


def case_counts(selected, passed, failed):
    return len((passed - failed) & selected), len(failed & selected), len(selected)
