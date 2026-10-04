# 300e — Qualify Chinese kiosk first presentation and reboot continuity

Follow the [shared task contract](../E2E-Execution-Contracts.md#task-brief-contract)
and [capability acceptance](../E2E-Execution-Contracts.md#capability-acceptance).

Required tasks (queue IDs; use delivered scope, not predecessor briefs):
- **300a** — Installed Chinese locale, system translations and CJK fonts with read-only FIX06 verification.
- **300b** — Jordan desktop-language setting and independent AccountsService readback with explicit renewal required.
- **300d** — Genuine old-release install/activation and current upgrade, independent final reboot notice and unchanged-boot readback.

Estimate: 40–60 minutes.
Session exception: Genuine installation, activation, upgrade without reboot, first kiosk notice and the subsequent reboot/first presentation require one continuous owned package lifecycle attempt.

## Scope

Qualify the first three phases of the
[Chinese kiosk lifecycle recipe](../E2E-Scenario-Recipes.md#chinese-kiosk-language-lifecycle-planned-task-300).
Use Jordan, `zh_CN.UTF-8` desktop language and default `zh-Hans` product language;
keep Jamie and the kiosk station English and Jordan's personal product language
unset. Observe the actual Chinese restart notice on the first post-upgrade kiosk
entry before any generic language handler acts. Then perform the declared reboot
and observe the Chinese chooser, selected default and underlying initial form
before saving any personal language choice. Native approval belongs to 300f;
the full multilingual/RTL and Chinese history remains task 300's single case.

Behavior owners are [localization validation](../../SystemDesign/Localization.md#validation-contract),
[personal language selection](../../SystemDesign/Frontends.md#personal-language-selection)
and [package lifecycle](../../SystemDesign/Lifecycle.md#startup-login-and-update-lifecycle).
Keep the recipe's genuine release and real reboot-request gates. No simulated
notice, private guard/preference write or later language switch can qualify an
incorrect initial presentation.

## Implementation entry

Read the [support guide](../../../tests/support/README.md),
[bounded supporting work](../E2E-Building-Blocks.md#keep-supporting-work-bounded)
and [composition preflight](../E2E-Building-Blocks.md#composition-preflight).
Start at these complete callables and follow their affected dependencies:

- [package_upgrade.py](../../../tests/e2e/package_upgrade.py): `PackageUpgradeJourney`,
  `install_previous`, `upgrade_entry`, `upgrade_current` and `PLAN`;
  [package_install.py](../../../tests/e2e/package_install.py): `submit_release` /
  `observe_release`; [qualified package binding](../E2E-Building-Blocks.md#genuine-package-upgrade).
- [account_language.py](../../../tests/e2e/account_language.py): `AccountLanguage`;
  [Chinese preparation and DESK13](../E2E-Building-Blocks.md#chinese-language-preparation-and-desktop-language-setup).
  Reuse the finite Jordan setting, read-only verification and explicit renewal;
  never infer a Chinese desktop from command success alone.
- [accessible_ui.py](../../../tests/e2e/accessible_ui.py): `language_scope`,
  `choose_language`, `save_language`, `language_save_completed` and
  `complete_language_setup`. Inspect owned `update-required-*` and language
  controls through public IDs. Add only the shared initial-observation/modal
  operations missing for this binding; suppress automatic setup until the
  caller's initial-language assertions finish.
- [customer_reboot.py](../../../tests/e2e/customer_reboot.py),
  [installed_journey.py](../../../tests/e2e/installed_journey.py) and
  [onpc_customer_reboot.pm](../../../tests/integration/graphical_smoke/lib/onpc_customer_reboot.pm):
  reuse the owned boot transition and shared return/entry mechanics. Extend the
  finite composition for the second declared reboot; never restore the baseline
  midway or silently reuse old UI/session state.
- Shared kiosk entry and request observations in
  [kiosk_entry.py](../../../tests/e2e/kiosk_entry.py) and
  [request_flow.py](../../../tests/e2e/request_flow.py), through the existing
  worker, observation and recorder path. Keep initial-presentation assertions
  in the recipe and reusable language/modal mechanics in their shared owners.

## Acceptance

1. In a fresh product-free owned attempt, verify Chinese FIX06 and immutable
   genuine release inputs. Install/activate v1.2 through the qualified package
   and reboot composition. Apply and independently confirm Jordan's Chinese
   account setting, explicitly renew and observe the fresh child desktop.
   Preserve Jamie/station/system language and unrelated accounts/files.
2. Upgrade once to current and independently establish successful completion,
   actual final reboot notice, installed version and unchanged boot. Reach the
   first kiosk entry with no intervening reboot or personal language save.
   Require Jordan as the default child and the restart message/buttons already
   Chinese; an English chooser must not displace the notice. Observe before
   `complete_language_setup` can dismiss or save anything.
3. Exit through the supported public prompt/session flow and perform one
   declared LIFE02 reboot in the same attempt. Independently require changed
   boot and fresh usable greeter/kiosk entry. With Jordan still selected and no
   saved personal language, require the first chooser already Chinese, Chinese
   selected by default and the underlying initial usable request form Chinese.
   Check the recipe's representative headings, child/approver/duration/Request
   labels and actions against independent Chinese expectations.
4. Refuse wrong entry/account, stale or ambiguous UI ownership, missing genuine
   reboot request, unexpected boot change, replay and premature language setup
   before releasing later input. Preserve single-use uncertainty and immutable
   captures through the real worker/decoder/recorder path. Complete capture
   reconciliation, collection, worker/callback shutdown, baseline restoration,
   finalization and host/source preservation.

Planned selector (unimplemented; register and cleanup-test before use):

```bash
tools/run-tests integration check_e2e_chinese_kiosk_lifecycle
```

Run the affected host package/reboot/account-language/language-control and
worker/recorder safety checks before live work. Pass the qualification on every
enabled VM, then require `check_e2e_package_upgrade` as the affected package
composition regression and `check_e2e_kiosk_entry` for shared kiosk entry.
If shared Parent launch changes, retain case 6 under the shared live policy.
Apply the session's first-new-live-failure boundary and wait for owned cleanup.

## Session boundary

No implementation or live acceptance is supplied by this allocation. Stop the
qualified slice at the initial Chinese form without saving a personal language
or submitting native authentication. Task 300f owns the separate Chinese MATE
binding; task 300 preserves the uninterrupted complete recipe and all original
multilingual/RTL assertions. Task 301's broader fresh-install modal Close/re-entry
and all-surface branches remain separate.
