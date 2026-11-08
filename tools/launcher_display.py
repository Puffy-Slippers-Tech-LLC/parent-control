"""Status and task-summary formatting shared by Watch views."""

import time

from rich.text import Text

from launcher_chat import TASK_STATUSES
from launcher_render import clean, style_task_counts
from launcher_session import clock_duration


def error_status_lines(task_info, key, clock):
    """Shared Last Error/Status fields and observer fallback clock."""
    error = clean(task_info.get('last_error', '')).strip()
    has_error = bool(error and error != '-')
    status = task_info.get('status')
    if not has_error:
        status = 'Running'
    elif status not in TASK_STATUSES or status == 'Running':
        status = TASK_STATUSES[0]
    key = (*key, status)
    if clock is None or clock[0] != key:
        clock = (key, time.time())
    status_age = clock_duration(time.time() - task_info.get('status_at', clock[1]))
    last_error = Text('Last Error: ')
    last_error.stylize('bold', 0, len('Last Error:'))
    if has_error:
        last_error.append(error, style='red')
        error_at = task_info.get('last_error_at')
        if error_at is not None:
            last_error.append(f' ({clock_duration(time.time() - error_at)} ago)')
    else:
        last_error.append('-')
    status_line = Text('Status: ')
    status_line.stylize('bold', 0, len('Status:'))
    colors = dict(zip(TASK_STATUSES, ('#0098ff', '#0098ff', 'yellow', 'green', '#0098ff',
                                    'yellow', '#0098ff')))
    status_line.append(status, style=colors[status])
    status_line.append(f' ({status_age} ago)', style='#0098ff')
    return [last_error, Text(''), status_line], clock


def task_summary_lines(totals, duration):
    """Share task totals and their palette across terminal and editor views."""
    completed, unfinished, total = totals or ('—', '—', '—')
    counts = Text(f'Total Tasks: {completed}/{unfinished}/{total}')
    style_task_counts(counts)
    return [counts, Text('Total Duration: ' + duration)]
