# 007a2b — Complete caller-independent helper creation and witnesses

Acceptance: host

Requires 007a2a. Newly discovered prerequisite of
[007a2](007a2-ambient-ubuntu.md); preserve its entire installed acceptance.

## Purpose and scope

Complete the same privileged-creation correction in the Python preparation
owners and remove the credential blindness in supporting witnesses. The
[original failure and broad XHigh review](../Kiosk-Prompt.md#ubuntu-retained-ambient-checkpoint--007a2)
are the starting evidence. A native parent owned by root does not make new child
files, directories or symlinks root-group-owned without an explicit contract.

Read applicable system-design, retained-material/admission, approval, failure,
storage and test-resource owners. Own `tools/kiosk_confinement.py` runtime-copy
publication, `tools/kiosk_preparation_service.py` skeleton and transient creation,
their actual child entry routes and matching unit controls. Audit compatibility
`prepare()`/`make_tree()` creation too; preserve its stated non-production limits.
Reuse shared Python allocation mechanics with explicit ownership/modes for newly
owned scratch, copies, manifests, skeleton directories/files/links and transient
bindings. Follow 007a2a's creation-versus-reuse boundary; do not normalize retained
sources or foreign existing objects. Preserve membership, immutable source
identity, labels, deadline, bounds, publication and interruption cleanup.
Inventory legacy `.prepare-*`, numbered copies, `generation`, `records.json`,
tree/link/placeholders and `.bindings-*` explicitly without reviving that route.
Anonymous sealed `_record()` inputs have a different metadata contract and are
valid exclusions from named private-storage repair. Skeleton group inheritance
is an allocation-policy gap, not another independently reproduced denial.

Handle failed ownership initialization with its own identity-proven recovery.
`RuntimeCopyPublication` records scratch before validation, but the current
reclaimer requires root:root; an initialization failure must not strand a known
owned unnormalized object, erase its first failure or authorize an unsafe sweep.
Keep unknown/replaced objects intact. The `private_store` unit fixture rewrites
every observed UID/GID to zero, so it currently hides this product defect;
correct or supplement that fixture without weakening production assertions.

Correct `tests/integration/system_kiosk_confinement.py:first_exec()` and its
finite caller controls so GDM-equivalent group/filesystem credential and umask
ordering is established before PAM, rather than after the tested boundary.
Keep the systemd-manager entrypoint's actual distinct credentials. Supporting
case 292 receipts obtained with the old ordering do not qualify this context.
Do not turn an earlier helper/attestation refusal into an admission witness.

Record the real/effective/filesystem UID and GID and umask before the native PAM
boundary for each entrypoint, with a host control proving their order relative
to `pam_open_session()`. A post-call snapshot cannot qualify pre-call creation.
Keep the actual GDM nonzero filesystem-group witness distinct from the manager's
context. The staged [Ubuntu](007a2d-bootstrap-ubuntu.md) and
[Fedora](007a2e-bootstrap-fedora.md) tasks own the real loaded-policy proof.

## Validation and close-out

Cover root UID with nonzero filesystem GID, effective-vs-filesystem GID, SGID
inheritance and restrictive umasks including 0777; assert exact ownership/modes,
unchanged caller context and correct symlink handling. Keep complete fresh and
retained production transactions and permanent initialization-failure,
interruption, foreign/replaced-state and cleanup controls. Mark any metadata
doubles accurately; actual credential/loaded-policy proof remains installed work.

007a2a's native-only 0777 transactions deliberately reset the test preparation
child's umask to isolate the still-unfixed Python boundary. Add cumulative
transactions that exercise both native and Python creation under the original
caller context; retire that fixture reset when these full controls replace its
bounded native-only proof. Preserve the original transaction assertions.

Apply the master's mandatory
[Astra XHigh review and revision gate](../Kiosk-Prompt.md#astra-review-and-revision-for-every-product-fix)
to each product correction before acceptance; retain the separately required
independent Sol XHigh review below.

Run affected preparation service/entry, runtime-copy/confinement, fresh/retained,
publication/record, native-update observer and applicable resource/storage
regressions through the maintained unit launcher. Reconcile cumulative 007a2a
and 007a2b inputs, not only this task's newest selectors. Require the explicitly
requested independent GPT-6.1 Sol XHigh broad-pattern review. Run `make build`
after the final packaged edit and finish all owned cleanup.

Record exact changed-input applicability: the original Ubuntu 293 failure and
older root-group bootstrap checks remain failures/historical supporting evidence.
007a2 must repeat its entire installed history on final inputs. Shared changes
must also be qualified on Fedora under the existing unfinished Fedora retained
history; preserve that owner and do not claim a new Fedora pass from host checks.
Close only this prerequisite after host/build acceptance and cleanup; 007a2c and
the original installed consumer remain unchecked.
