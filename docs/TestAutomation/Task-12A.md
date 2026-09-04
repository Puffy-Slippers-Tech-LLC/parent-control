### Task 12A — Add guarded in-VM test-account preparation

- Complexity: high. This provisions durable login identities and handles one
  shared password, but it does not install the product or alter libvirt state.
- Recommended Codex model: `gpt-5.6-sol`
- Recommended reasoning effort: `high`
- Execution location: the existing Ubuntu 26.04 guest exposes the development
  checkout at `/Data/Code/PST/parent-control`, the same path used on the host.
  Implementation and host-safe tests happen on the development computer; a
  later operator step runs `make prep-vm` from that path inside the guest. This
  preparation-only `/Data` virtiofs share is not part of the captured QCOW2 and
  must not be exposed to later disposable test guests.
- Objective: provide one idempotent, guarded command that prepares the existing
  Ubuntu VM with the same two parent and two child identities shown by the
  preview applications, ready for a pre-product-install baseline capture.
- Fixed test identities:
  - `onpc-parent-jamie`, display name `Jamie Parker`, is a local interactive
    administrator.
  - `onpc-parent-casey`, display name `Casey Parker`, is a local interactive
    administrator.
  - `onpc-child-riley`, display name `Riley Parker`, is a local interactive
    standard user.
  - `onpc-child-jordan`, display name `Jordan Parker`, is a local interactive
    standard user.
  The preview-only numeric UIDs are not an installed-system contract. The
  preparation script records the real UIDs allocated in this VM, and later
  tests resolve the accounts by their stable usernames and verify their live
  roles.
- Work:
  1. Add a `make prep-vm` entry point backed by a repository script intended to
     run only inside the existing `ubuntu26.04` guest. It must fail before any
     mutation unless it is running as root in a virtual machine, the guest is
     Ubuntu 26.04, and the repository checkout is
     the complete checkout at `/Data/Code/PST/parent-control`. Report which
     identity or environment check failed in a clear, redacted error. These
     fixed checks require no VM name, UUID, image, or path argument. It must also
     refuse to run if the Oh No! Parent Control package, installed product
     payload, configuration, saved state, service or session integration, PAM or
     Polkit integration, GNOME extension payload, log tree, or product-created
     kiosk account is present. Repository source and build artifacts under the
     checkout do not count as an installation. After preflight, set the guest
     hostname to `ubuntu26.04` using `hostnamectl set-hostname`; the existing
     hostname is not an identity prerequisite. This preparation-only change
     activates immediately and is not shipped in the Debian package, so it
     requires no package activation classification or development-host setup.
  2. Require the operator to acquire a root shell before invoking the target so
     the target itself presents exactly one password prompt. Read the shared
     test-account password once without echo or confirmation and apply that same
     value to all four accounts through standard input. Never place it in an
     argument, environment variable, command trace, log, repository file,
     preparation marker, or artifact.
  3. Create or reconcile the four fixed usernames, home directories, interactive
     shells, display names, and unlocked password state. The two parent accounts
     must be current local administrators; the two child accounts must not be in
     `sudo`, `adm`, or another administrative group. Refuse UID collisions,
     system-account identities, unsafe pre-existing ownership, or a conflicting
     account rather than repurposing it.
  4. Cache or refresh the four accounts through the supported AccountsService
     interface and verify each resulting UID, locality, system-account flag,
     account type, lock state, shell, and group role. The operation must be
     idempotent; a successful repeat changes only the shared password and
     reasserts the intended account properties.
  5. Write a root-owned, mode-`0600`, regular preparation record at
     `/etc/oh-no-parent-control-test-baseline.json`. Give it an exact versioned
     schema containing the guest identity, Ubuntu version, preparation-script
     digest, fixed usernames, resolved UIDs, and verified roles. It must contain
     no password, password hash, token, SSH material, or other secret.
  6. Add useful stage, outcome, and bounded error-category messages using labels
     such as `[Test parent 1]` and `[Test child 1]`; do not log account passwords
     or raw account records.
  7. Add host-safe unit and source-contract tests for the environment guard,
     exact checkout path, clear guard failures, exact identity map, role
     validation, idempotent command construction, secret-handling boundary,
     marker schema and permissions, and refusal for each category of installed
     product payload or residue. Do not run `make prep-vm` as part of this
     subtask.
  8. Document the guest prerequisite and command in the integration README,
     including the shared `/Data/Code/PST/parent-control` checkout, that the
     share exists only on the source VM, and that this command prepares accounts
     only; it does not install the product.
- Verification:
  - Run the focused host-safe preparation-script unit tests.
  - Run shell syntax and source-contract checks for the new script.
  - Run `make check` and `git diff --check`.
- Completion criteria: `make prep-vm` is implemented and host-tested, cannot run
  on the development host, provisions exactly the four preview identities with
  one shared password prompt, records no secret, and never installs the product.
  Do not run the command or mark Task 12B complete in this session.
