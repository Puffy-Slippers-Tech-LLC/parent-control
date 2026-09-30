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
    sources = {path: dict(feeds=Feeds(runtime), output=Output(path), vm_feeds={})
               for path, runtime in zip(roots, runtimes)}
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
    locks, publications = {}, {}
    stage = ''
    failure = []
    peers = []

    def start(index):
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
                              test=labels[path] + ' UI', phase='call')
        publications[index] = source

    def finish(index):
        publications.pop(index).close()
        locks.pop(index).close()

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
                        elif index >= count and index in locks:
                            finish(index)
                elif stage == 'finish-main':
                    finish(0)
                elif stage == 'finish-third':
                    finish(2)
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
            for publication in publications.values():
                publication.serve()
                publication.frames.publish()
            cells = {labels[Path(name)]: list(app.checkout_grid.query_child(view))
                     for name, view in app.checkouts.items()
                     if view.get_parent() == app.checkout_grid}
            evidence.write_text(json.dumps(dict(
                cells=cells, blank=app.checkout_blank.get_parent() == app.checkout_grid,
                active=[labels[Path(name)] for name, view in app.checkouts.items() if view.active],
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
        for lock in locks.values():
            lock.close()
        for peer in peers:
            peer.wait(timeout=5)
        stack.close()
    if failure:
        raise failure[0]
    return status
