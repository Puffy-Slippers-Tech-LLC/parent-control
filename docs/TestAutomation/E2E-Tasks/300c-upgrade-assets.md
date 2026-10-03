# 300c — Qualify verified upgrade asset transfer

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **005a** — Product-free administrator entry, command-context refusal and verified package identity in the guarded journey envelope.

Estimate: 20–30 minutes.

## Scope

Add one FIX04 binding that verifies and transfers **genuine v1.2 and current
packages together**, preserving their separate release/source identities, then
independently reads their identities and bytes in a product-free guest.
This supplies the inputs for [task 300's Chinese lifecycle](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300).
Do not install either package, register a partial scenario, write product
preferences or simulate an older release by changing current package metadata.

The existing E2E verifier/transfer owns one package. The system runner accepts
`--previous-artifacts`, but its engineering preparation does not supply a qualified
E2E dual-package transfer. Reuse maintained verification/staging mechanics;
keep the new finite binding within the existing provenance, watch, lease,
private-artifact and independent-observation envelope. Never overwrite valid
existing inputs or relax source/identity checks to admit the prior release.

## Scoped reading and implementation entry

Read FIX04 and its relevant source functions, then follow only affected callees:

- [`provenance.py`](../../../tests/e2e/provenance.py): `preflight_source`,
  `VerifiedInputs.__init__`, `asset_files`, `recheck` and evidence-input consumers.
- [`asset_transfer.py`](../../../tests/e2e/asset_transfer.py):
  `AssetTransfer.provision` and `observe`; follow the existing guest asset oracle
  in [`guest_observations.py`](../../../tests/e2e/guest_observations.py).
- [`system_runner.py`](../../../tests/integration/system_runner.py):
  `artifact_source`, `stage_assets`, `package_version` and the prior-input staging
  branch of `main`, for existing verification mechanics rather than installed
  product acceptance.
- [`build_test_artifacts.py`](../../../tools/build_test_artifacts.py):
  `build`, `verify` and source metadata; use maintained input preparation for
  missing generated assets. Establish an authentic released-v1.2 source/package
  identity independently of the current checkout. An unavailable authentic
  release remains an asset gate; report the exact unavailable input and action
  needed rather than replacing it with a reinstall or fabricated version.
- [`product_free_entry.py`](../../../tests/e2e/product_free_entry.py):
  `ProductFreeEntryJourney`; extend the shared worker/staging path from
  [`check_graphical_smoke.py`](../../../tests/integration/check_graphical_smoke.py).
- [`transfer safety`](../../../tests/unit/test_e2e_asset_transfer_cleanup_safety.py)
  and [`provenance safety`](../../../tests/unit/test_e2e_provenance.py):
  retain their ownership, immutability, partial-failure and cleanup boundaries.

`check_e2e_upgrade_assets` is implemented as an argument-free integration entry.
It uses `named_input(upgrade_source=True)` and automatic maintained preparation
of the finite v1.2/current inputs. `build_test_artifacts.released_source` pins
the signed v1.2 tag object `8eb479d4d6afa9dcc38328945ceed09cbb03e8a8` and commit
`9ed654baf593d1a6ef89bb7e324317319251136d`; it never rewrites checkout metadata.
`stage_upgrade_assets`, `VerifiedInputs(upgrade=True)` and the existing
`AssetTransfer` supply the reusable binding. Qualification/readback assertions
are in `upgrade_assets_qualification.py`; cleanup checks are in
`test_upgrade_assets_cleanup_safety.py`. Live qualification remains pending.

## Acceptance

1. Before guest mutation, independently verify two different package digests,
   the exact product name, supported architecture, authentic v1.2 release version
   and a newer current version. Bind each package's verified source identity,
   manifest and exact bytes; preserve current fixture verification. Refuse wrong
   product/version/architecture, identical or reversed packages, missing or
   changed assets and unsafe file/owner/link identities before transfer.
2. In one fresh product-free attempt, refuse transfer outside the owned
   powered-off provisioning phase. Transfer the two verified packages through
   the shared FIX04 path exactly once. Independently read both package identities
   and digests through the booted guest's read-only oracle, with fresh repeated
   readback; host copying or command success alone does not establish the result.
3. Retain independent valid entry and wrong-attempt/replay/collision refusal.
   An uncertain or partial transfer remains consumed and uses owned cleanup,
   without replay or adopting another attempt. Assert the guest remains
   product-free, with accounts, observer/system locales and unrelated files
   preserved; no installer, product preference write or session renewal occurs.
4. Run affected provenance/transfer/recorder/cleanup host regressions and the
   existing one-package transfer's affected live regression. Record exact
   selectors after checking their maintained registrations. Require private
   collection, worker shutdown, owned cleanup, baseline restoration and
   host/source preservation for both qualifications.

Live selectors, after task-local host checks (each selects every enabled VM):

```bash
tools/run-tests integration check_e2e_upgrade_assets
tools/run-tests integration check_e2e_product_free_entry
```

## Session boundary

Close only 300c after full enabled-VM qualification and cleanup. Task 300 remains
unchecked. This slice supplies no installation, upgrade, reboot-required modal,
Chinese authentication or complete-case acceptance. Afterward, task 300 still
requires bounded real upgrade/reboot-required and Chinese native-provider
prerequisites before its single complete case is registered. No live attempt
or adviser consultation has occurred for this binding.
