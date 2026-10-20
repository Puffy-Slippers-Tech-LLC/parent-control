# R11d — Qualify Fedora real update recovery

Acceptance: installed
Targets: onpc-Fedora44

Required tasks: R11c — cumulative D/E receipts; R11d1 — compatible visibility repair.
Estimate: 30–60 minutes.

Read the [master F family](../Kiosk-Resilience-Plan.md#acceptance), R09's update/
input map, [live contract](../TestAutomation/E2E-Execution-Contracts.md#live-verification-contract),
[system acceptance](../TestAutomation/E2E-Execution-Contracts.md#system-acceptance),
[VM mandate](../Mandates/VM-Mandate.MD) and [UI mandate](../Mandates/UI-Automation-Mandate.MD).

## Session boundary and acceptance

R11d1 extracts compatible AccountsService/retained-visibility repair, public
approval and metadata/ordinary-user preservation. Reuse applicable receipts;
this remaining task owns F's actual package-update histories. Use shared
registered selectors with `--vm onpc-Fedora44`, explicit timeouts and enforcing
SELinux. Cover an
unrelated package change and one actual relevant dependency/product update;
require fresh/reused public entry, genuine approval and justified activation
without exact old-manager retention or routine-drift reboot.

Keep R11d1's simulation within its engineering scope; neither it nor native
bubblewrap/xdg-dbus-proxy pairs count as AccountsService actual-update inputs.

## Close-out

Retain before/after product/dependency/fixture identities, public results and owned
restoration/cleanup. Reconcile cumulative F receipts, including R11d1. Apply
master repair gates; map shared changes to earlier Fedora/Ubuntu receipts and
schedule invalidated complete-history reruns before
R11 closes. Session exception: keep package mutation, activation, public recovery
and restoration together; split independent excess histories before execution.
