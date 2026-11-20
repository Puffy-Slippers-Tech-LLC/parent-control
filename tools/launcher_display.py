"""Status and task-summary formatting shared by Watch views."""

import re
import time

from rich.text import Text
from rich.style import Style

from launcher_chat import TASK_STATUSES
from launcher_render import clean, style_task_counts
from launcher_session import clock_duration


SYSTEM_SUMMARY = re.compile(r'^(?:│  )?\[[^]]+\] Installed-system tests(?= - | \(|$)')
SYSTEM_CHECK = re.compile(r'^(?P<tree>(?:│  )?)  (?P<label>\[[^]]+\] )Check: ')
CASE_PROGRESS = re.compile(r' - (?:\d+|\?)% \((\d+)/(?:([0-9]+)/)?(\d+|\?)\)')


def launcher_status_color(status):
    """One palette for launcher titles and both content status fields."""
    if status in ('Repairing', 'Reload Requested', 'Stop Requested', 'Stopping'):
        return '#af6a00'
    if status in ('finished', 'Finished', 'Closing Task'):
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
    color = status_color or (launcher_status_color(status) if status_override is not None else colors[status])
    status_line = launcher_status_line(status, color)
    status_line.append(f' ({status_age} ago)', style='#0098ff')
    return [last_error, Text(''), status_line], clock


def task_summary_lines(totals, duration, *, failures=0):
    """Share task totals and their palette across terminal and editor views."""
    completed, unfinished, total = totals or ('—', '—', '—')
    counts = Text(f'Tasks: {completed}/{unfinished}/{total}')
    style_task_counts(counts)
    if failures:
        counts.append(' | ')
        counts.append(f'{failures} failed', style='red')
    return [counts, Text('Total Duration: ' + duration)]


def case_progress_counts(match):
    passed, failed, total = match.groups()
    return int(passed), int(failed or 0), None if total == '?' else int(total)


def format_case_progress(passed, failed, total):
    counts = []
    if total is not None:
        counts.append(f'{passed}/{total} passed')
    elif passed:
        counts.append(f'{passed} passed')
    if failed:
        counts.append(f'{failed} failed')
    return ', '.join(counts)


def format_unknown_progress(row):
    """Show the counts already known without an estimated denominator."""
    match = CASE_PROGRESS.search(row.plain)
    if match and match[3] == '?':
        counts = format_case_progress(*case_progress_counts(match))
        return row[:match.start()] + Text(f' ({counts})' if counts else '') + row[match.end():]
    match = re.search(r' \(\?\)(?=$| - )', row.plain)
    if match is None:
        return row
    return row[:match.start()] + row[match.end():]


def worker_progress(section, details):
    overall = next((row.plain for row in section if row.plain.startswith('Overall - ')), '')
    match = CASE_PROGRESS.search(overall)
    if match is None:
        return ''
    counts = case_progress_counts(match)
    passed, failed, total = counts
    for row in details:
        match = CASE_PROGRESS.search(row.plain)
        if match and case_progress_counts(match) == counts:
            return ''
    return format_case_progress(passed, failed, total if total and total > 1 else None)


def repair_status_details(lines):
    """Project runner dashboards into the repair launcher's Status tab."""
    if not lines:
        return []
    rows = [Text.from_ansi(line) for line in lines]

    def progress_rows(section):
        # The pinned task summary covers the whole selection. Worker counts
        # are added inline only if their detail rows do not already show them.
        status = [row for row in section
                  if row.plain.strip() and not row.plain.startswith('Overall - ')]
        for index, row in enumerate(status):
            if SYSTEM_SUMMARY.match(row.plain):
                children = status[index + 1:index + 3]
                if (children and (check := SYSTEM_CHECK.match(children[0].plain))
                        and (len(children) == 1 or not SYSTEM_CHECK.match(children[1].plain))):
                    # A sole child gives the actual check and its elapsed time.
                    child = children[0]
                    label = child[check.start('label'):check.end('label')]
                    status[index:index + 2] = [child[:check.end('tree')] + label + child[check.end():]]
                break
        return status

    if not rows[0].plain.startswith('VM queue | concurrency '):
        return [format_unknown_progress(row) for row in progress_rows(rows)]
    workers = [index for index, row in enumerate(rows) if row.plain.startswith('VM: ')]
    bounds = [*workers, len(rows)]
    details = progress_rows(rows[1:bounds[0]])
    for start, end in zip(bounds, bounds[1:]):
        section = rows[start + 1:end]
        status = progress_rows(section)
        group = next((row for row in status if row.plain.startswith('Test group: ')), None)
        if group is not None:
            status.remove(group)
        activity = Text(' · ').join(format_unknown_progress(row) for row in status)
        if progress := worker_progress(section, status):
            if activity:
                activity.append(' · ')
            activity.append(progress)
        name = rows[start][4:]
        name.stylize(Style(bold=True, meta={'vm_column': 'name'}))
        for column, cell in (('group', group[len('Test group: '):] if group is not None else None),
                             ('status', activity)):
            if cell:
                cell.stylize(Style(meta={'vm_column': column}))
                name.append(' — ')
                name.append_text(cell)
        details.append(name)
    return details
