"""Three isolated checkout viewers on the enclosing private display and bus."""

from contextlib import ExitStack
import fcntl
import json
from pathlib import Path
import subprocess
import sys

from test_storage import directory, runtime_directory
from ui_watch_transport import Feeds, Publication
from watch_checkouts import identity
from watch_output import Output
from watch_viewer import application
from e2e_watch_protocol import Frames, read_frame


def run(root):
    import gi
    gi.require_version('Vte', '3.91')
    from gi.repository import GLib, Gtk, Vte
    control, evidence = root / 'control', root / 'evidence.json'
    roots = [root / name for name in ('main', 'worktree', 'third')]
    for path in roots:
        (path / 'tools').mkdir(parents=True)
        (path / 'tools/watch').touch()
        (path / '.git').mkdir()
    labels = dict(zip(roots, ('main', 'worktree', 'third')))
    stack = ExitStack()
    runtimes = [stack.enter_context(runtime_directory(prefix='onpc-watch-test-')) for _ in roots]
    vm_sources = {}
    class VM:
        vm_name = 'Fixture-VM'

        def __init__(self, index):
            self.index = index

        def poll(self, *, pixels=True):
            source = vm_sources.get(self.index)
            return read_frame(source.memory, pixels=pixels) if source is not None else 'waiting'

        def progress(self):
            return None

        def activity(self):
            return None

        def close(self):
            pass

    sources = {path: dict(feeds=Feeds(runtime), output=Output(path),
                         vm_feeds={'Fixture-VM': VM(index)})
               for index, (path, runtime) in enumerate(zip(roots, runtimes))}
    class Discovery:
        def __init__(self):
            self.received = []

        def add(self, path):
            self.received.append(str(path))

        def poll(self):
            return None

        def close(self):
            pass

    discovery = Discovery()
    app = application(checkouts=labels, sources=sources, discovery=discovery)
    locks, publications, extra_publications = {}, {}, {}
    stage = ''
    failure = []
    peers = []

    def start(index):
        finish(index)
        path = roots[index]
        base = directory('sessions-host', root=path)
        session = base / ('a' * 32)
        if not session.exists():
            session.mkdir(mode=0o700)
            (base / 'current.json').write_text(json.dumps({'run': session.name}))
            (session / 'output').write_text(labels[path] + ' OUTPUT\n')
        lock = (session / 'owner').open('wb')
        (session / 'owner').chmod(0o600)
        fcntl.flock(lock, fcntl.LOCK_EX)
        locks[index] = lock
        source = Publication(runtimes[index])
        source.frames.publish(b'\x10\x20\x30\0' * 12, state='live', worker=1,
                              width=4, height=3, stride=16, format=0x20020888,
                              branch='Category A', test=labels[path] + ' UI', phase='call')
        publications[index] = source
        if index == 0:
            extra = Publication(runtimes[index])
            extra.frames.publish(b'\x10\x20\x30\0' * 12, state='live', worker=2,
                                 width=4, height=3, stride=16, format=0x20020888,
                                 branch='Category B', test='main UI second', phase='call')
            extra_publications[index] = extra
        vm = Frames(str(index + 1) * 32)
        vm.publish(b'\x10\x20\x30\0' * 12, state='live', width=4, height=3,
                   stride=16, format=0x20020888)
        vm_sources[index] = vm

    def finish(index):
        for owned in (publications, extra_publications, vm_sources, locks):
            source = owned.pop(index, None)
            if source is not None:
                source.close()

    def tick():
        nonlocal stage
        try:
            if app.window is None:
                return True
            requested = control.read_text() if control.exists() else ''
            if requested != stage:
                stage = requested
                if stage.startswith('count-'):
                    count = int(stage.removeprefix('count-'))
                    for index in range(3):
                        if index < count and index not in locks:
                            start(index)
                        elif index >= count and (index in locks or index in publications):
                            finish(index)
                elif stage == 'finish-main':
                    finish(0)
                elif stage == 'finish-third':
                    finish(2)
                elif stage == 'finish-terminals':
                    for index in tuple(locks):
                        locks.pop(index).close()
                elif stage == 'double-click-ui':
                    name = str(roots[1])
                    run = publications[1].run
                    cell = app.cells[name, 'ui-' + run][0]
                    controllers = cell.observe_controllers()
                    for index in range(controllers.get_n_items()):
                        controller = controllers.get_item(index)
                        if isinstance(controller, Gtk.GestureClick):
                            controller.emit('pressed', 2, 0., 0.)
                elif stage == 'remote':
                    # A second process must hand its checkout to the existing
                    # application, then exit without owning a second window.
                    script = ('import sys; sys.path.insert(0, '
                              + repr(str(Path(__file__).resolve().parents[2] / 'tools')) + '); '
                              'from watch_viewer import application; '
                              'raise SystemExit(application(checkouts={}).run('
                              + repr(['watch-peer', str(roots[1])]) + '))')
                    peers.append(subprocess.Popen([sys.executable, '-B', '-c', script],
                                                  stdout=subprocess.DEVNULL))
            for publication in (*publications.values(), *extra_publications.values()):
                publication.serve()
                publication.frames.publish()
            for source in vm_sources.values():
                source.publish()
            cells = {labels[Path(name)]: list(app.terminal_grid.query_child(view))
                     for name, view in app.checkouts.items()
                     if view.get_parent() == app.terminal_grid}
            scope = app.scopes[app.selected_checkout]
            viewer_cells = {app.cells[entry][1].get_label(): list(scope['grid'].query_child(cell))
                            for entry, (cell, _title) in app.cells.items()
                            if cell.get_parent() == scope['grid']}
            top_tabs = []
            tab = scope['bar'].get_first_child()
            while tab is not None:
                top_tabs.append(tab.get_label())
                tab = tab.get_next_sibling()
            evidence.write_text(json.dumps(dict(
                cells=cells, viewer_cells=viewer_cells, top_tabs=top_tabs,
                blank=scope['blank'].get_parent() == scope['grid'],
                terminal_heights=[view.get_height() for view in app.checkouts.values()
                                  if view.get_parent() == app.terminal_grid],
                active=[labels[Path(name)] for name, view in app.checkouts.items() if view.active],
                output_active=[labels[Path(name)] for name, view in app.checkouts.items() if view.output_active],
                selected_viewer=scope['selected'],
                ui_keys={labels[roots[index]]: 'ui-' + publication.run
                         for index, publication in publications.items()},
                selected=labels.get(Path(app.selected_checkout), app.selected_checkout),
                keys={labels[path]: identity(path) for path in roots},
                text={labels[Path(name)]: view.terminal.get_text_format(Vte.Format.TEXT)
                      for name, view in app.checkouts.items()},
                remote_exited=bool(peers) and peers[-1].poll() == 0,
                remote_received=str(roots[1]) in discovery.received)))
            return True
        except BaseException as error:
            failure.append(error)
            app.window.close()
            return False

    GLib.timeout_add(50, tick)
    try:
        status = app.run(['watch-test'])
    finally:
        for source in publications.values():
            source.close()
        for source in extra_publications.values():
            source.close()
        for source in vm_sources.values():
            source.close()
        for lock in locks.values():
            lock.close()
        for peer in peers:
            peer.wait(timeout=5)
        stack.close()
    if failure:
        raise failure[0]
    return status
