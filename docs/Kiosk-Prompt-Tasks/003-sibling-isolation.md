# 003 — Qualify Fedora sibling isolation

Acceptance: installed
Targets: onpc-Fedora44

Session boundary: qualify 003a's canonical selector on Fedora and reconcile both
target receipts against the candidate. 003a owns initial implementation and
Ubuntu acceptance. Session exception: keep public entry/replacement, native
isolation, exact restoration and cleanup in one history. Rerun affected Ubuntu
acceptance if a later fix invalidates 003a; no original target/assertion is dropped.

Follow the [master](../Kiosk-Prompt.md),
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance)
and [Reliability 006a](../Reliability-Tasks/006a-sibling-masking.md).
Extend canonical `system_kiosk_confinement.py` mechanics and register one finite
selector; any new selector is unimplemented until registered and listed.

On Fedora, use owned inert fixtures for root-owned 0775/0777 directories
and non-root-owned 0755/0555 directories, plus one representative omitted entry
from 002's distinct native branches. Host tests own redundant name/type matrices.
Observe usable confined entry, empty/absent private views, positive ordinary-user
contents/access and the original unchanged host fixtures. Replace a recorded
masked/omitted host input while retaining the station; its private view must not
acquire mutable content. Observe enforcing execution independently of a manifest.

Keep the entry/replacement/isolation/recovery history together. Preserve the first
failure, fix demonstrated generic causes and restore only exact owned mutations.
Retain both-target candidate identities and cleanup receipts. Supply matching
evidence to 006a for its later scope review; do not check that separate row.
