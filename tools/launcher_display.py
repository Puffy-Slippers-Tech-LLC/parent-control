"""Status and task-summary formatting shared by Watch views."""

import time

from rich.text import Text

from launcher_chat import TASK_STATUSES
from launcher_render import clean, style_task_counts
from launcher_session import clock_duration


def launcher_status_color(status):
    """One palette for launcher titles and both content status fields."""
    if status in ('Repair Pending', 'Repairing', 'Verifying', 'Checking Impact',
                  'Reload Requested', 'Stop Requested', 'Stopping'):
        return '#ffa500'
    if status in ('finished', 'Finished', 'Committing Fix', 'Closing Task'):
        return '#008000'
    if status in ('failed', 'Failed', 'stopped', 'Stopped', 'Waiting for input'):
        return '#f14c4c'
    return '#0098ff'


def launcher_status_line(value, color):
    line = Text('Status: ')
    line.stylize('bold', 0, len('Status:'))
    line.append(value, style=color)
    return line


def error_status_lines(task_info, key, clock, *, status_override=None, status_color=None):
    """Shared Last Error/Status fields and observer fallback clock."""
    error = clean(task_info.get('last_error', '')).strip()
    has_error = bool(error and error != '-')
    status = task_info.get('status')
    if not has_error:
        status = 'Running'
    elif status not in TASK_STATUSES or status == 'Running':
        status = TASK_STATUSES[0]
    if status_override is not None:
        status = status_override
    key = (*key, status)
    if clock is None or clock[0] != key:
        clock = (key, time.time())
    status_at = clock[1] if status_override is not None else task_info.get('status_at', clock[1])
    status_age = clock_duration(time.time() - status_at)
    last_error = Text('Last Error: ')
    last_error.stylize('bold', 0, len('Last Error:'))
    if has_error:
        last_error.append(error, style='red')
        error_at = task_info.get('last_error_at')
        if error_at is not None:
            last_error.append(f' ({clock_duration(time.time() - error_at)} ago)')
    else:
        last_error.append('-')
    colors = dict(zip(TASK_STATUSES, ('#0098ff', '#0098ff', 'yellow', 'green', '#0098ff',
                                    'yellow', '#0098ff')))
    color = status_color or (launcher_status_color('Repair Pending') if status_override is not None else colors[status])
    status_line = launcher_status_line(status, color)
    status_line.append(f' ({status_age} ago)', style='#0098ff')
    return [last_error, Text(''), status_line], clock


def task_summary_lines(totals, duration):
    """Share task totals and their palette across terminal and editor views."""
    completed, unfinished, total = totals or ('—', '—', '—')
    counts = Text(f'Total Tasks: {completed}/{unfinished}/{total}')
    style_task_counts(counts)
    return [counts, Text('Total Duration: ' + duration)]
