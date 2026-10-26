"""Reloadable observer policy. Reattachment never invokes workflow admission."""

import json
from pathlib import Path
import signal
import sys

import launcher_bootstrap


def reload_if_requested(request, run, label, view, display, *, test_session=False):
    if (not (run / 'cancel').exists() and not (run / 'stop').exists()
            and request.pending() and display.reload_ready()):
        # The bootstrap catches this only after all terminal, file and caller
        # contexts unwind. It resumes this exact run, never the original CLI.
        display.reloading = True
        raise launcher_bootstrap.ReloadObserver(json.dumps({
            'run': str(run), 'label': label, 'plan': view.plan,
            'test_session': test_session}))


def main():
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        import detached_launcher as launcher
        from launcher_view import plan_view, view_for
        request = json.loads(sys.argv[1])
        run, label = Path(request['run']), request['label']
        if not run.is_dir():
            raise ValueError('retained run is unavailable')
        launcher.private_directory(run)
        view = plan_view(*request['plan']) if request['plan'] else view_for(label)
        previous = signal.getsignal(signal.SIGINT)
        if label != 'sync-whatsnew':
            signal.signal(signal.SIGINT, lambda *_: (run / 'cancel').touch(mode=0o600))
        try:
            if request['test_session']:
                from regression_session import follow
                return follow(run)
            return launcher.follow(run, label=label, view=view)
        finally:
            signal.signal(signal.SIGINT, previous)
    except BrokenPipeError:
        return 0
    except KeyboardInterrupt:
        return 130
    except (OSError, ValueError, KeyError, ImportError) as error:
        print(f'launcher observer: {error}; reattach to the retained run.', file=sys.stderr)
        return 2
