"""Private, input-free rendering of the watch viewer into active case WebMs.

The runner owns retained paths and case publication. This child owns only its
explicit compositor and encoder. Its inherited SOCK_SEQPACKET control endpoint
has no pathname, discovery or connection to a manually opened watch window.
"""

from contextlib import ExitStack
import argparse
import ctypes
from functools import lru_cache
import json
import os
from pathlib import Path
import queue
import resource
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import textwrap
import time
import traceback

FPS = 5
WIDTH, HEIGHT = 1400, 900
_owner_fd = None
_stop_requested = threading.Event()


class CaptureGate:
    """Keep opacity until stale authentication textures have been replaced."""

    def __init__(self):
        self.tokens = set()
        self.resume_after_ns = self.ready_ns = None

    def seal(self, token, sealed, at_ns):
        if sealed:
            self.tokens.add(token)
            self.ready_ns = None
        elif token in self.tokens:
            self.tokens.remove(token)
            if not self.tokens:
                self.resume_after_ns = at_ns
                self.ready_ns = None

    def masked(self, panels, at_ns):
        if self.tokens:
            return True
        if self.resume_after_ns is None:
            return False
        for panel in panels:
            # Screen.meta belongs to the texture actually applied to GTK,
            # rather than a newer asynchronous feed header still in transit.
            screen = panel.screen
            if screen.texture is not None and screen.meta.get('updated_ns', 0) < self.resume_after_ns:
                self.ready_ns = None
                return True
        if self.ready_ns is None:
            self.ready_ns = at_ns
        # WidgetPaintable may retain the preceding rendered node until GTK's
        # next paint. Never snapshot immediately inside the unseal callback.
        if at_ns - self.ready_ns < 1_000_000_000 // FPS:
            return True
        self.resume_after_ns = self.ready_ns = None
        return False


def launch_command(root, control_fd, *, owner_fd=None, vm_names=None):
    """Run inside a private session bus; pass control and scratch owner FDs."""
    return ['dbus-run-session', '--', '/usr/bin/python3', '-B',
            str(Path(__file__).resolve()), '--control', str(control_fd),
            '--root', str(root),
            *(['--owner', str(owner_fd)] if owner_fd is not None else []),
            *(['--vms', json.dumps(list(vm_names))] if vm_names is not None else [])]


def launch_environment():
    """Use host GTK libraries and schemas for the entire private bus session."""
    environment = dict(os.environ)
    for name in ('LD_PRELOAD', 'LD_LIBRARY_PATH', 'GTK_PATH', 'GTK_EXE_PREFIX',
                 'GTK_DATA_PREFIX', 'GTK_IM_MODULE', 'GTK_MODULES',
                 'GDK_PIXBUF_MODULE_FILE', 'GDK_PIXBUF_MODULEDIR',
                 'GIO_MODULE_DIR', 'GIO_EXTRA_MODULES', 'GI_TYPELIB_PATH'):
        environment.pop(name, None)
    environment.update(PATH='/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin',
                       XDG_DATA_DIRS='/usr/local/share:/usr/share',
                       GSETTINGS_SCHEMA_DIR='/usr/share/glib-2.0/schemas')
    return environment


def shared_owner_descriptors():
    """Keep the master ownership lease held by every explicitly owned child."""
    from test_storage import scratch_descriptors
    return tuple(dict.fromkeys((*scratch_descriptors(),
                                *((_owner_fd,) if _owner_fd is not None else ()))))


def secret_pixels(width=WIDTH, height=HEIGHT, *, names=()):
    """Cache opaque omissions by the public VM labels actually in this layout."""
    return _secret_pixels(width, height, tuple(sorted(set(names))))


@lru_cache(maxsize=4)
def _secret_pixels(width, height, names):
    """An opaque, clearly marked omission; no captured pixels enter this image."""
    import cairo
    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    context = cairo.Context(surface)
    context.set_source_rgb(.094, .094, .094)
    context.paint()
    context.set_source_rgb(1, 1, 1)
    context.select_font_face('Sans', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
    font_options = cairo.FontOptions()
    font_options.set_antialias(cairo.ANTIALIAS_GRAY)
    context.set_font_options(font_options)
    labels = textwrap.wrap('VM panels: ' + ', '.join(names), width=85,
                           break_long_words=False, break_on_hyphens=False) if names else []
    label_size = min(18, max(10, (height - 200) / max(1, len(labels)) / 1.3))
    first = height / 2 - len(labels) * label_size * .65
    lines = [('Secret input omitted', 32, first - 8),
             ('Recording resumes after a verified safe result.', 18, first + 30)]
    lines.extend((label, label_size, first + 70 + index * label_size * 1.3)
                 for index, label in enumerate(labels))
    for text, size, baseline in lines:
        context.set_font_size(size)
        left, _top, text_width, _height, _dx, _dy = context.text_extents(text)
        context.move_to((width - text_width) / 2 - left, baseline)
        context.show_text(text)
    surface.flush()
    # Grayscale RGB channels make Cairo's native BGRA and encoder RGBA equal.
    return bytes(surface.get_data())


def final_reply(control, summary):
    """Stream large span inventories without seqpacket truncation or omissions."""
    def packet(value):
        return json.dumps(value, separators=(',', ':')).encode()
    previous_timeout = control.gettimeout()
    try:
        control.settimeout(5)
        if len(packet(summary)) > 48 * 1024:
            spans = summary['vm_spans']
            for begin in range(0, len(spans), 128):
                control.sendall(packet(dict(event='vm-spans', items=spans[begin:begin + 128])))
            summary = dict(summary, vm_spans=[])
        control.sendall(packet(summary))
    finally:
        control.settimeout(previous_timeout)


def process_identity(process):
    return identity_for_pid(process.pid)


def identity_for_pid(pid):
    value = Path(f'/proc/{pid}/stat').read_text()
    return pid, int(value[value.rfind(')') + 2:].split()[19])


def latch_termination():
    """Parent death and ordinary termination both enter the owned cleanup path."""
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda _signal, _frame: _stop_requested.set())
    parent = os.getppid()
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0):  # Linux PR_SET_PDEATHSIG.
        raise OSError(ctypes.get_errno(), 'recording parent-death guard')
    if os.getppid() != parent:
        _stop_requested.set()


def stop_owned(process, identity):
    """A Popen handle plus unchanged kernel identity is the signal authority."""
    if process.poll() is not None:
        return
    if process_identity(process) != identity:
        raise RuntimeError('recording child identity changed')
    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        if process_identity(process) != identity:
            raise RuntimeError('recording child identity changed')
        process.kill()
        process.wait(timeout=3)


class Encoder:
    """Bounded latest-frame handoff: a slow encoder cannot stall GTK or tests."""

    def __init__(self, output, *, width=WIDTH, height=HEIGHT, fps=FPS):
        self.width, self.height, self.fps = width, height, fps
        self.frames = queue.Queue(maxsize=1)
        self.stopping = threading.Event()
        self.finished = threading.Event()
        self.error = None
        self.count = 0
        self.vm_spans, self.shown_vms = [], {}
        self.dropped_capture_frames = 0
        self.started_ns = time.monotonic_ns()
        self.started = self.started_ns / 1e9
        self.ended = None
        self.process = subprocess.Popen([
            'ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f'{width}x{height}',
            '-framerate', str(fps), '-i', 'pipe:0', '-an',
            '-c:v', 'libvpx-vp9', '-deadline', 'realtime', '-cpu-used', '8',
            '-threads', '1', '-row-mt', '1', '-crf', '40', '-b:v', '0',
            '-g', str(fps), '-pix_fmt', 'yuv420p', str(output)],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
            pass_fds=shared_owner_descriptors())
        self.identity = process_identity(self.process)
        self.thread = threading.Thread(target=self.run, name='watch-encoder', daemon=True)
        self.thread.start()

    def submit(self, pixels, *, names=()):
        if len(pixels) != self.width * self.height * 4:
            raise ValueError('recording frame size')
        item = (time.monotonic(), pixels, tuple(sorted(set(names))))
        try:
            previous = self.frames.get_nowait()
            # Multiple control replacements in one clock slot are normal.
            # Losing an unread frame from an earlier slot means overload.
            if (int((item[0] - self.started) * self.fps)
                    > int((previous[0] - self.started) * self.fps)):
                self.dropped_capture_frames += 1
        except queue.Empty:
            pass
        try:
            self.frames.put_nowait(item)
        except queue.Full:
            pass

    def write_frame(self, pixels, names):
        """Visibility belongs to frames actually written to the encoder pipe."""
        self.process.stdin.write(pixels)
        at_ns = self.started_ns + self.count * 1_000_000_000 // self.fps
        names = set(names)
        for vm in set(self.shown_vms) - names:
            self.vm_spans.append(dict(vm=vm, start_ns=self.shown_vms.pop(vm), end_ns=at_ns))
        for vm in names - set(self.shown_vms):
            self.shown_vms[vm] = at_ns
        self.count += 1

    def run(self):
        previous = bytes((24, 24, 24, 255)) * (self.width * self.height)
        previous_names = ()
        try:
            while not self.stopping.is_set() or not self.frames.empty():
                try:
                    timestamp, pixels, names = self.frames.get(timeout=.1)
                except queue.Empty:
                    continue
                target = max(0, int((timestamp - self.started) * self.fps))
                while self.count < target:
                    self.write_frame(previous, previous_names)
                # Control acknowledgements can replace pixels several times in
                # one tick. Keep one frame per clock slot so those replacements
                # cannot stretch the stream or shift case timestamps.
                if self.count == target:
                    self.write_frame(pixels, names)
                previous, previous_names = pixels, names
            target = max(1, int((self.ended - self.started) * self.fps) + 1)
            while self.count < target:
                self.write_frame(previous, previous_names)
            self.process.stdin.close()
            if self.process.wait(timeout=10):
                raise RuntimeError('recording encoder failed')
        except (OSError, RuntimeError, subprocess.TimeoutExpired) as error:
            self.error = type(error).__name__
        finally:
            try:
                self.process.stdin.close()
            except OSError:
                pass
            self.finished.set()

    def seconds(self):
        return max(0., time.monotonic() - self.started)

    def close(self):
        self.ended = time.monotonic()
        self.stopping.set()
        if not self.finished.wait(12):
            stop_owned(self.process, self.identity)
            self.thread.join(timeout=3)
            raise RuntimeError('recording encoder did not finish')
        stop_owned(self.process, self.identity)
        if self.error:
            raise RuntimeError(self.error)
        ended_ns = self.started_ns + self.count * 1_000_000_000 // self.fps
        self.vm_spans.extend(dict(vm=vm, start_ns=start, end_ns=ended_ns)
                             for vm, start in self.shown_vms.items())
        self.shown_vms.clear()
        return dict(frames=self.count, fps=self.fps, duration_seconds=self.count / self.fps,
                    dropped_capture_frames=self.dropped_capture_frames, vm_spans=self.vm_spans)


def widget_pixels(window, width=WIDTH, height=HEIGHT):
    """Snapshot the existing GTK widget tree, including VTE and VM screens."""
    import gi
    gi.require_version('Gtk', '4.0')
    gi.require_version('Graphene', '1.0')
    gi.require_version('Gdk', '4.0')
    from gi.repository import Gdk, Graphene, Gtk
    snapshot = Gtk.Snapshot()
    paintable = Gtk.WidgetPaintable.new(window)
    paintable.snapshot(snapshot, width, height)
    node = snapshot.to_node()
    if node is None:
        # Mapping and relayout can temporarily invalidate WidgetPaintable's
        # cached node. The caller retains its last safe frame while GTK paints.
        return None
    texture = window.get_renderer().render_texture(node, Graphene.Rect().init(0, 0, width, height))
    if not hasattr(Gdk, 'TextureDownloader'):
        raise RuntimeError('recording needs GTK TextureDownloader')
    downloader = Gdk.TextureDownloader.new(texture)
    downloader.set_format(Gdk.MemoryFormat.R8G8B8A8)
    data, stride = downloader.download_bytes()
    pixels = data.get_data()
    if stride == width * 4:
        return pixels
    return b''.join(pixels[row * stride:row * stride + width * 4] for row in range(height))


def render(control, root, *, compositor=None, sources=None, vm_names=None):
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import GLib
    from watch_recording_viewer import application
    from watch_checkouts import Discovery
    state = dict(ready=False, closing=False, error=None, render_ns=0, samples=0,
                 last_render_ns=time.monotonic_ns(), skipped_render_frames=0)
    gate = CaptureGate()
    # An independent application cannot forward to a user's live singleton.
    sources = sources or {root: {}}
    if vm_names is not None:
        sources = {checkout: dict(options, vm_names=vm_names) for checkout, options in sources.items()}
    app = application(checkouts={root: root.name}, sources=sources,
                      window_size=(WIDTH, HEIGHT))
    encoders = {}
    control.setblocking(False)

    def reply(value):
        control.send(json.dumps(value, separators=(',', ':')).encode())

    def submit_frame():
        panels = {vm: view.vms[key] for view in app.checkouts.values() for vm, key in view.vm_keys.items()
                  if (str(view.root), key) in (app.viewer_layout or ('', '', ()))[2]}
        names = set(panels)
        # The omission visibly identifies these public panels. Keep the same
        # names with the encoded image even while all private pixels are sealed.
        pixels = (secret_pixels(names=names) if gate.masked(panels.values(), time.monotonic_ns())
                  else widget_pixels(app.window))
        if pixels is None:
            state['skipped_render_frames'] += 1
            return None
        for encoder in encoders.values():
            encoder.submit(pixels, names=names)
        state['last_render_ns'] = time.monotonic_ns()
        return names

    def tick():
        try:
            if _stop_requested.is_set():
                state['error'] = 'Interrupted'
                app.quit()
                return False
            if app.window is None or app.window.get_width() < 2:
                return True
            if not state['ready']:
                # Qualify the public render/download route before reporting
                # readiness; startup failure must never look like recording.
                started = time.monotonic_ns()
                if submit_frame() is None:
                    if time.monotonic_ns() - state['last_render_ns'] > 10_000_000_000:
                        raise RuntimeError('recording window never painted')
                    return True
                state['render_ns'] += time.monotonic_ns() - started
                state['samples'] += 1
                children = [('worker', identity_for_pid(os.getpid()))]
                if compositor is not None:
                    children.append(('compositor', process_identity(compositor)))
                reply(dict(event='ready', fps=FPS, width=WIDTH, height=HEIGHT,
                           started_ns=time.monotonic_ns(),
                           processes=[dict(role=role, pid=pid, start_ticks=start)
                                      for role, (pid, start) in children]))
                state['ready'] = True
            for _ in range(64):
                try:
                    data = control.recv(4096)
                except BlockingIOError:
                    break
                if not data:
                    state['closing'] = True
                    break
                command = json.loads(data)
                if not isinstance(command, dict):
                    raise ValueError('recording command object')
                operation = command.get('op')
                if operation == 'seal' and type(command.get('sealed')) is bool:
                    token = command.get('token')
                    if not isinstance(token, str) or not token or len(token) > 128:
                        raise ValueError('recording seal token')
                    gate.seal(token, command['sealed'], time.monotonic_ns())
                    # ACK follows replacing queued pixels. Secret delivery waits
                    # for this response; already queued images precede input.
                    submit_frame()
                    reply(dict(event='sealed', token=token, sealed=bool(gate.tokens)))
                elif operation in ('begin', 'end'):
                    category, identifier = command.get('category'), command.get('id')
                    from recording_storage import case_identity, _token
                    if not _token(category) or not case_identity(identifier):
                        raise ValueError('recording case identity')
                    key = command.get('vm')
                    if key not in (vm_names or ()):
                        raise ValueError('recording VM identity')
                    if operation == 'begin':
                        if key in encoders or len(encoders) >= len(vm_names or (None,)):
                            raise ValueError('recording active case limit')
                        encoder = encoders[key] = Encoder(Path(command['path']))
                        # All new encoders pass through the existing opacity gate.
                        submit_frame()
                        reply(dict(event='begun', started_ns=encoder.started_ns))
                    else:
                        submit_frame()
                        encoder = encoders.pop(key)
                        summary = encoder.close()
                        summary.update(event='ended', started_ns=encoder.started_ns)
                        final_reply(control, summary)
                elif operation == 'close':
                    state['closing'] = True
                    break
                else:
                    raise ValueError('recording command')
            if state['closing']:
                app.quit()
                return False
            started = time.monotonic_ns()
            names = submit_frame()
            if names is None:
                if time.monotonic_ns() - state['last_render_ns'] > 3_000_000_000:
                    raise RuntimeError('recording window stopped painting')
                return True
            state['render_ns'] += time.monotonic_ns() - started
            state['samples'] += 1
            if any(encoder.error for encoder in encoders.values()):
                raise RuntimeError('recording encoder failed')
            return True
        except Exception as error:
            traceback.print_exc()
            state['error'] = type(error).__name__
            app.quit()
            return False

    GLib.timeout_add(1000 // FPS, tick)
    try:
        app.discovery = Discovery(root, include_worktrees=False)
        app.run([])
    finally:
        if app.discovery is not None:
            app.discovery.close()
        # A controller normally ends each case before closing the renderer.
        # Still reap every explicitly owned encoder on interruption/failure.
        errors = []
        for encoder in encoders.values():
            try:
                encoder.close()
            except Exception as error:
                errors.append(type(error).__name__)
        if errors:
            state['error'] = errors[0]
    summary = dict(event='closed', fps=FPS, render_ns=state['render_ns'], samples=state['samples'],
                   skipped_render_frames=state['skipped_render_frames'])
    own = resource.getrusage(resource.RUSAGE_SELF)
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    cpu = own.ru_utime + own.ru_stime + children.ru_utime + children.ru_stime
    peak = own.ru_maxrss + children.ru_maxrss
    if compositor is not None and compositor.poll() is None:
        try:
            value = Path(f'/proc/{compositor.pid}/stat').read_text()
            fields = value[value.rfind(')') + 2:].split()
            cpu += (int(fields[11]) + int(fields[12])) / os.sysconf('SC_CLK_TCK')
            for line in Path(f'/proc/{compositor.pid}/status').read_text().splitlines():
                if line.startswith('VmHWM:'):
                    peak += int(line.split()[1])
        except OSError:
            pass  # The owned compositor may have exited after its final frame.
    summary['cpu_seconds'] = cpu
    summary['peak_rss_sum_kib'] = peak
    if state['error']:
        summary.update(event='error', code=state['error'])
    try:
        final_reply(control, summary)
    except OSError:
        pass
    return 1 if state['error'] else 0


def main(argv=None):
    global _owner_fd
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', type=int, required=True)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--owner', type=int)
    parser.add_argument('--vms', type=json.loads)
    args = parser.parse_args(argv)
    if args.vms is not None and (not isinstance(args.vms, list) or not args.vms
            or any(not isinstance(name, str) for name in args.vms)
            or len(set(args.vms)) != len(args.vms)):
        parser.error('recording requires a nonempty unique VM queue')
    if args.owner is not None:
        if args.owner < 0:
            parser.error('recording owner descriptor must be open')
        os.fstat(args.owner)
    _owner_fd = args.owner
    latch_termination()
    root = args.root.resolve(strict=True)
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from test_storage import runtime_directory, scratch_directory
    with socket.socket(fileno=args.control) as control, ExitStack() as stack:
        runtime = stack.enter_context(runtime_directory(prefix='onpc-watch-record-'))
        private = Path(stack.enter_context(tempfile.TemporaryDirectory(
            prefix='onpc-watch-record-', dir=scratch_directory())))
        for name in ('config', 'cache', 'data', 'state'):
            (private / name).mkdir(mode=0o700)
        display = 'watch-recording'
        # This runtime contains only compositor sockets and tiny configuration;
        # the retained video and logs are allocated by the runner elsewhere.
        os.environ.update(XDG_RUNTIME_DIR=str(runtime), WAYLAND_DISPLAY=display,
                          XDG_CONFIG_HOME=str(private / 'config'),
                          XDG_CACHE_HOME=str(private / 'cache'),
                          XDG_DATA_HOME=str(private / 'data'),
                          XDG_STATE_HOME=str(private / 'state'),
                          GDK_BACKEND='wayland', NO_AT_BRIDGE='1',
                          GSETTINGS_BACKEND='memory',
                          # Match the host Mutter rather than editor/Snap schemas.
                          GSETTINGS_SCHEMA_DIR='/usr/share/glib-2.0/schemas',
                          GTK_THEME='Adwaita',
                          MUTTER_DEBUG_DISABLE_ANIMATIONS='1')
        os.environ.pop('DISPLAY', None)
        compositor = subprocess.Popen(['mutter', '--headless', '--wayland', '--no-x11',
            '--virtual-monitor', f'{WIDTH}x{HEIGHT}', '--wayland-display', display],
            pass_fds=shared_owner_descriptors())
        identity = process_identity(compositor)
        try:
            deadline = time.monotonic() + 10
            while not (runtime / display).exists():
                if (_stop_requested.is_set() or compositor.poll() is not None
                        or time.monotonic() >= deadline):
                    raise RuntimeError('recording compositor did not start')
                time.sleep(.05)
            return render(control, root, compositor=compositor, vm_names=args.vms)
        except (OSError, ValueError, RuntimeError) as error:
            traceback.print_exc()
            try:
                control.send(json.dumps(dict(event='error', code=type(error).__name__)).encode())
            except OSError:
                pass
            return 1
        finally:
            stop_owned(compositor, identity)


if __name__ == '__main__':
    raise SystemExit(main())
