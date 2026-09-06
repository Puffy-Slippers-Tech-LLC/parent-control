# Task 19P backend preflight — 2026-09-06

This is tooling and source-review evidence. **No guarded graphical smoke has
run; Task 19P remains incomplete.** The first slice resolved a real host tooling
failure before implementing the VM adapter. No VM mutation, baseline restore,
product installation, game download, or feedback delivery occurred.

## Candidate integration and public sources

The reviewed candidate is Ubuntu's
`os-autoinst=5.1768577300.b85e4864-1`, upstream revision `b85e4864`, public test
API 48, with `BACKEND=generalhw`. Its documented
[VNC and command variables](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/doc/backend_vars.asciidoc)
provide a TCP VNC console and external lifecycle/serial scripts. The
[backend implementation](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/backend/generalhw.pm)
requests power-off, waits three seconds, requests power-on, and attaches VNC.
It requests power-off again at shutdown. Flash/image extraction is optional.

Inference: these public hooks can delegate to the existing `system_runner.Lease`
without making os-autoinst a second VM lifecycle owner. This is a candidate
design, not demonstrated compatibility. Ordinary
[svirt setup](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/doc/backends.md)
creates/configures its own domain; the QEMU backend also owns its guest. Neither
is the proposed integration for this existing leased domain.

The current `system_runner.isolated_xml` retains only SPICE with `listen=none`.
The reviewed `generalhw` VNC console takes a TCP hostname/port.
[Libvirt's public graphics XML](https://libvirt.org/formatdomain.html#graphical-framebuffers)
supports VNC, loopback listeners, automatic ports, passwords and Unix sockets.
The next adapter must resolve graphics from the live lease-validated domain,
protect access, and revalidate ownership before controls. Do not use remembered
ports, direct host-window automation, QEMU monitor commands, or a new guest.

Smallest proposed live experiment: reset/isolate the existing VM under `Lease`,
use bounded lifecycle callbacks, recognize GDM, open and dismiss a harmless menu
with real mouse and keyboard input, retain screen-change evidence, obtain a
fixed read-only observation through a supported transport, then complete lease
cleanup. The launch wrapper, endpoint, observation and screen assertions are
not yet implemented, so there is no working graphical invocation to copy.

## Tooling failure, fix and verification

Installing the pinned backend with `--no-install-recommends` added 246 required
packages, with no upgrades/removals. The package requires all Tesseract language
data even without recommendations. Recommended Open vSwitch services and a
separate VNC server were excluded. The initial `isotovideo --version` failed:
`Feature::Compat::Try` was missing. Installing the archive package
`libfeature-compat-try-perl=0.05-1` fixed it. Both explicit pins and the installation
shape are now in `setup.sh` and the tool inventory.

After the isolated `test_system_runner_cleanup_safety.py` prerequisites,
the reusable read-only invocation is:

```sh
/usr/bin/python3 -B tests/integration/graphical_backend.py
```

It verifies installed status and exact package pins, runs the public CLI version
query, and compiles/loads `generalhw` dependencies with Perl `-c`. Commands use
the existing pidfd-owned timeout implementation. It opens no libvirt connection
and explicitly reports `scope=tooling-only`, `graphical_smoke=not-run`.
Observed runtime was **0.696 seconds**, outcome passed, test API 48. The Ubuntu
CLI's release string is `unknown`; package metadata supplies version identity.

| Verified file | SHA-256 |
| --- | --- |
| `/usr/bin/isotovideo` | `f5e27f472952d1ac067dde13b6b253c2379ae8f525f90ffb31e6bae012835428` |
| `/usr/lib/os-autoinst/backend/generalhw.pm` | `c740198ab5b47031da13f9d0e60370eda51ace1aec3ccf66cb3c3ae39c4ab344` |
| `tests/integration/graphical_backend.py` | `724d3baa9a921f0366b8c1ada51b8a7a2a833ac95f5e7e3b279e5babb184c4c5` |
| `tests/unit/test_graphical_backend.py` | `5111dd9f06b51d92669a1f2b7c011ae7e1230827bf2e8ee206083d1905c5499a` |
| `setup.sh` | `df0ee74045a40dd64e67847988e3631514993c3b113e9a1d942f144efcbc4074` |
| `tests/test-tools-ubuntu-26.04.txt` | `e4befdd68a7dcc3eb861f204f9b7c8de97ff0d11cf6d6cc0219ba3ce37a5cad1` |

Base revision: `f9bae49189f99eec3a3dcdad1935bb85b8f93a64`; the table identifies this
slice's uncommitted inputs. Concurrent publishing/compliance edits appeared
during the session and were preserved. This is not a frozen release run.

Checks: 16 isolated cleanup regressions; 12 focused preflight regressions;
`make check` passed (935 unit/contract, 17 private-D-Bus component tests and its
static/traceability checks); `bash -n setup.sh`; `git diff --check`.
Approximately 25 minutes including investigation/install/verification; no VM
attempts or VM cleanup time. Both package operations and all test commands
finished. A final read-only domain-state query confirmed `ubuntu26.04` off.

## Capture, cleanup and downstream prerequisites

The public [password API](https://github.com/os-autoinst/os-autoinst/blob/b85e4864/testapi.pm)
uses `secret => 1` to suppress typed text in logs; it does not suppress video or
screenshots. Enter no credentials in the feasibility smoke. Later authentication
must verify a masked prompt before typing and test both failure and interrupted
capture paths. `_SECRET_`/`_PASSWORD` variables are excluded on the test process's
secret-filtered save, but startup also writes unfiltered working vars. Treat the
working directory as private; never export raw vars, terminal output or backend
logs as safe evidence. A safe collector must prove credential exclusion.

The backend owns subprocesses as well as the VM callbacks. Review and test its
actual interruption/cleanup behavior before a live worker. The preflight's
pidfd regressions qualify only the reused command wrapper, not all os-autoinst
descendant cleanup or lifecycle callbacks.

[SuperTux 0.7.0](https://www.supertux.org/) is an available maintained game
candidate with bundled, versioned offline levels, including
[Welcome to Antarctica](https://github.com/SuperTux/supertux/blob/v0.7.0/data/levels/world1/welcome_antarctica.stl).
The Ubuntu cache offers older `0.6.3-5`; do not silently select that instead of
reviewing the maintained release. Task 26C must pin verified delivery bytes and
level assets, then prove normal-UI entry and windowed/fullscreen gameplay. No
game package or release asset was downloaded or installed here.

External feedback delivery needs an explicitly authorized dedicated test
recipient/profile on the actual supported service. Current product code fixes
the endpoint at `https://tech.puffyslippers.com/api/oh-no-parent-control/feedback`;
no dedicated delivery profile is established by this slice. Draft/cancel tests
can proceed, but required delivery acceptance needs that profile. No request
was sent to the feedback endpoint.
