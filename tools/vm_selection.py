"""Shared explicit VM selection for unprivileged development launchers."""

from pathlib import Path
import os
import json
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tests/integration'))
import vm_config
sys.path.pop(0)

extract = vm_config.extract
arguments = vm_config.arguments
select = vm_config.select
selected = vm_config.selected
registry = vm_config.registry
VARIABLE = vm_config.VARIABLE
BATCH = 'ONPC_TEST_VM_BATCH'
BASELINE_INSTRUCTIONS = (
    'When authorized baseline preparation is needed in launcher/session work, use '
    'tools/prepare-baseline --vm NAME --mode auto --y (or --mode manual --y only '
    'with explicit developer authorization). --y suppresses y/n confirmation; '
    'omit it for manual work. All VM, ownership, lease and validation checks still apply.')


def execution_selection(name=None):
    concurrency, vms = vm_config.execution(name)
    select(vms[0].name)
    if name is None:
        os.environ[BATCH] = json.dumps({'concurrency': concurrency, 'vms': [vm.name for vm in vms]})
    else:
        os.environ.pop(BATCH, None)
    return concurrency, vms


def execution_arguments():
    return [] if BATCH in os.environ else arguments()


def execution_binding():
    if BATCH in os.environ:
        return json.loads(os.environ[BATCH])
    vm = selected(required=False)
    return vm.name if vm else None


def execution_instructions():
    if BATCH in os.environ:
        queue = json.loads(os.environ[BATCH])
        return (f"Run VM tests through tools/run-tests without --vm: it executes all enabled VMs "
                f"({', '.join(queue['vms'])}), at most {queue['concurrency']} simultaneously. "
                "Use an explicit --vm NAME only for scoped diagnosis, maintenance or preparation. "
                "Complete required live validation on every enabled VM before closing the task. "
                + BASELINE_INSTRUCTIONS)
    vm = selected(required=False)
    selection = (f'Every VM command must include --vm {vm.name}; Make VM targets use VM={vm.name}. '
                 'Do not select another VM. ') if vm else ''
    return selection + BASELINE_INSTRUCTIONS


def choice_screen(screen, names, ids):
    """Terminal VM selection with one shared keyboard/mouse selection index."""
    import curses
    selected = 0
    digits = ''
    # Keep the terminal's configured foreground/background instead of ncurses'
    # white-on-black defaults, which can be unreadable in a light theme.
    try:
        curses.use_default_colors()
    except curses.error:
        pass  # Monochrome terminals may not support default color pairs.
    screen.keypad(True)
    curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
    curses.mouseinterval(0)
    try:
        curses.curs_set(0)
    except curses.error:
        pass
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        if height < len(names) + 5 or width < 24:
            raise ValueError('VM chooser needs a larger terminal; use --vm NAME')
        screen.addnstr(0, 0, 'Choose a VM from config/test-vm.json:', width - 1)
        for index, name in enumerate(names):
            label = f'  {ids[index]}. {name}'
            screen.addnstr(index + 1, 0, label, width - 1,
                           curses.A_BOLD if index == selected else curses.A_NORMAL)
        screen.addnstr(len(names) + 2, 0, f'Select VM ID [{", ".join(ids)}]: {ids[selected]}', width - 1)
        screen.addnstr(len(names) + 3, 0, 'Up/Down, mouse or number; Enter confirms; Esc cancels.', width - 1)
        screen.refresh()
        key = screen.get_wch()
        if key in ('\n', '\r', curses.KEY_ENTER):
            return selected
        if key in ('\x1b', '\x03', '\x04'):
            raise ValueError('VM selection cancelled; supply --vm NAME to proceed')
        if key in (curses.KEY_UP, curses.KEY_DOWN):
            selected = (selected + (-1 if key == curses.KEY_UP else 1)) % len(names)
            digits = ''
        elif key == curses.KEY_MOUSE:
            _device, _x, y, _z, buttons = curses.getmouse()
            if buttons & curses.BUTTON4_PRESSED:
                selected = max(0, selected - 1)
            elif buttons & getattr(curses, 'BUTTON5_PRESSED', 0):
                selected = min(len(names) - 1, selected + 1)
            elif 1 <= y <= len(names):
                selected = y - 1
            digits = ''
        elif isinstance(key, str) and key.isascii() and key.isdecimal():
            candidate = digits + key
            if candidate in ids:
                digits = candidate
                selected = ids.index(candidate)
            elif any(identifier.startswith(candidate) for identifier in ids):
                digits = candidate
            elif key in ids:
                digits = key
                selected = ids.index(key)


def interactive_choice(names, ids):
    import curses
    # ncurses enables button reporting; xterm all-motion adds hover selection.
    # Restore it even on cancellation before returning to ordinary line input.
    try:
        sys.stdout.write('\033[?1003h')
        sys.stdout.flush()
        index = curses.wrapper(choice_screen, names, ids)
    except (EOFError, KeyboardInterrupt) as error:
        raise ValueError('VM selection cancelled; supply --vm NAME to proceed') from error
    except curses.error as error:
        raise ValueError('VM terminal chooser unavailable; supply --vm NAME') from error
    finally:
        sys.stdout.write('\033[?1003l')
        sys.stdout.flush()
    print('Choose a VM from config/test-vm.json:')
    for number, name in enumerate(names):
        line = f'  {ids[number]}. {name}'
        print('\033[1m' + line + '\033[0m' if number == index else line)
    print(f'Select VM ID [{", ".join(ids)}]: {ids[index]}')
    return index


def check_binding(run, name, *, stopping=False):
    path = run / 'vm.json'
    previous = json.loads(path.read_text())['vm'] if path.exists() else None
    if stopping and name is None and isinstance(previous, dict):
        return  # Cancellation of a configured queue does not reselect guests.
    if previous != name:
        raise ValueError('vm-config: launcher requires its original --vm NAME')


def save_binding(run, name):
    from detached_launcher import atomic
    atomic(run / 'vm.json', {'vm': name})


def make_command(root, target, environment):
    """Decode literal Make variables; never interpolate a VM name into shell code."""
    if target not in ('all', 'all-verify', 'system', 'appsnapshot', 'watch'):
        raise ValueError('vm-config:unsupported Make target')
    name = environment.get('ONPC_MAKE_VM') or None
    if target == 'watch':
        if name is not None or environment.get('ONPC_WATCH_VM_ORIGIN', 'undefined') != 'undefined':
            raise ValueError('watch: VM parameter refused; watches all registered VMs')
        return [str(root / 'tools/watch')]
    options = []
    if target == 'system':
        if environment.get('ONPC_SYSTEM_VM_IMAGE'):
            raise ValueError('VM_IMAGE-refused; choose VM=NAME')
        for key, option in (('LIST', '--list'), ('QUALIFICATION_FAILURE', '--qualification-failure')):
            value = environment.get('ONPC_SYSTEM_' + key, '')
            if value not in ('', '1'):
                raise ValueError(key + '-must-be-1')
            if value:
                options.append(option)
        for key, option in (('ARTIFACT_DIR', '--artifacts'), ('AREA', '--area'), ('TEST', '--test')):
            value = environment.get('ONPC_SYSTEM_' + key, '')
            if value:
                options.extend((option, value))
    configured = vm_config.load(name) if name is not None or '--list' not in options else None
    vm_args = ['--vm', configured.name] if configured else []
    if target == 'appsnapshot':
        return [str(root / 'tools/prepare-appsnapshot'), *vm_args]
    return [str(root / 'tools/run-tests'), target, *options, *vm_args]


if __name__ == '__main__':
    try:
        if len(sys.argv) != 3 or sys.argv[1] != '--from-make':
            raise ValueError('vm-config:internal Make entry only')
        command = make_command(Path(__file__).resolve().parents[1], sys.argv[2], os.environ)
        os.execv(command[0], command)
    except (ValueError, OSError) as error:
        sys.exit(str(error))
