# Saved-data migration

[System design overview](../System-Design.md)

Read this for saved-data compatibility, versioned preference migrations,
package configuration ordering, and migration safety and retries.

Implementation: [data_migration.py](../../broker/oh_no_parent_control/data_migration.py), [preferences.py](../../broker/oh_no_parent_control/preferences.py), [preinst](../../debian/preinst), [postinst](../../debian/postinst), [broker launcher](../../broker/oh-no-parent-control-broker), [broker unit](../../data/systemd/oh-no-parent-control-broker.service).

Oh No! Parent Control migrates application-owned persistent data automatically during package configuration. Data schema versions are independent of distribution package versions: package releases may leave a schema unchanged, and one release may migrate more than one saved-data family.

The current framework migrates unified per-user records in `/var/lib/oh-no-parent-control/preferences/`, including personal settings and child policy/request choices. It also configures the separately versioned [What's New installation history](#whats-new-installation-history). Machine configuration, transient markers, logs, AccountsService, Malcontent, and files managed as Debian conffiles are not preference data and must not be added to that migration chain. If another application-owned data family later needs versioning, give it its own current-version constant, migration registry, validation, and migration pass in `migrate_all_state()`.

The current preference schema is version 4. Its `3 -> 4` step adds
`personal.language = ""` (follow the frontend session language) without changing
saved policy or request choices. Existing `1 -> 2` and `2 -> 3` steps are unchanged;
direct upgrades execute all three steps. Current personal-only records use the
same validation and migration pass, including UID 0 for root's personal settings.
The existing package exclusion marker prevents old/new broker writers from
running while migration changes records. Unsupported older brokers cannot read
version 4; downgrades remain unsupported.

The optional version-4 notification field uses compatible read normalization,
as described in [State](State.md#persistent-and-derived-state). Existing migration
functions are unchanged. Missing fields receive reminder defaults, while saved
customizations and explicitly empty reminder lists survive migration retries
and future package upgrades.

## Package lifecycle

`debian/preinst` creates `/var/lib/oh-no-parent-control/migration-in-progress` before a new payload is unpacked. Both the broker launcher and its systemd unit refuse to start while that marker exists. `preinst` explicitly stops a running broker before package files or saved records can change.

After unpacking, `debian/postinst` runs the newly installed `/usr/libexec/oh-no-parent-control-migrate-state`. It retains the marker through provisioning, trust-database readiness and activation preparation, releasing it immediately before broker activation. A successful configuration that defers a changed trust backend until reboot releases the migration marker and retains the separate [boot-scoped trust guard](Lifecycle.md#startup-login-and-update-lifecycle). Configuration also establishes the marker and stops/verifies an existing broker when entered without `preinst`, so reconfiguration has the same exclusion. Failures before activation retain the marker and prevent D-Bus clients from starting the broker early.

The maintainer script deliberately fails if migration fails. The marker then keeps the broker unavailable and APT leaves the package unconfigured. Fixing the underlying record or migration and running `dpkg --configure -a` retries the operation. A successfully migrated record is skipped on retry, so an interruption between records is safe.

The Fedora RPM embeds the same lifecycle templates. Its `%pre` creates the
exclusion marker and stops the broker, and `%posttrans` invokes migration before
provisioning/activation. RPM can record an installed package despite a failed
post-transaction script; the marker continues to exclude the broker. Use the
[installed configuration retry](../Fedora-Packaging.md#fedora-lifecycle) after
resolving the cause. Fedora installed lifecycle qualification remains pending.

## What's New installation history

`/var/lib/oh-no-parent-control/whats-new-installation.json` is a root-private,
mode-0600 schema-1 record with `version`, `first_version` and `current_version`.
The migration command configures it under the same process lock and package
exclusion as preferences, using the shared validated reader and atomic/fsynced
writer. Its schema is independent of preference format 4. Malformed, unsafe,
future-schema and downgrade histories are refused and preserved.

A fresh installation records the current product version as its origin. Before
the first upgrade to a payload with this feature, shared Debian/RPM pre-install
code saves the old installed `app.json` as mode-0600 `previous-product.json`.
It captures only on upgrade when neither history nor a pending bootstrap input
exists, and refuses substituted paths. This supports old payloads that have no
history writer and interrupted unpack/configuration retries. Capture writes and
flushes a private temporary file before atomic publication and a directory flush;
a failed copy never becomes the bootstrap input retained by the next attempt. Configuration uses
that input once, then removes it only after the history write succeeds.
Subsequent upgrades advance the current version without changing origin;
same-version configuration is idempotent. Removal retains this saved family and
purge deletes it with the product state directory.

The optional per-user `whats_new_seen` field uses compatible normalization,
without changing any released migration or incrementing preference schema 4.
The [state contract](State.md#whats-new-backend) owns record identity, eligibility,
acknowledgement and garbage collection.

## Adding a preference migration

The implementation is in `broker/oh_no_parent_control/data_migration.py`. When a preference change is not readable and writable with the existing schema:

1. Increment `FORMAT_VERSION` in `preferences.py`.
2. Add a pure `migrate_preferences_vN_to_vN_plus_1()` function.
3. Register it under key `N` in `PREFERENCE_MIGRATIONS`.
4. Update current-schema defaults and `validate_preferences()`.
5. Add unit fixtures for realistic version-N records, boundary values, malformed input, direct multi-version upgrades, and interrupted retries.
6. Ensure the new broker behavior is deployed only after the migration code is packaged and invoked during package configuration.

Every migration advances exactly one integer version and returns a new object. Released migrations are an on-disk compatibility contract: never change or remove an existing migration. Append the next step instead. The runner applies all required steps in order, so a direct `1 -> 4` package upgrade executes `1 -> 2 -> 3 -> 4`.

A migration function must be deterministic and limited to transforming one decoded record. It must not call D-Bus, use the network, inspect whether an account still exists, start a service, or change AccountsService or Malcontent. External state changes belong in a separate, idempotent reconciliation after all files migrate successfully.

An optional field with an unambiguous default may remain compatible and be normalized by the current reader. Renaming or removing data, changing its type or meaning, or changing a default in a way that alters an existing user's state requires a schema increment and explicit migration. Never use the Debian package version to interpret saved data.

## Safety contract

The runner accepts only numeric UID JSON records, regular files owned by the invoking privileged identity with mode `0600`, and a preference directory that is not group- or world-writable. It rejects duplicate JSON keys, malformed or missing versions, gaps in the migration registry, invalid migration output, and schemas newer than the installed program. Unknown future data must never be replaced with defaults.

Each changed record is validated with the production current-schema validator, written to a mode-`0600` temporary file in the same directory, flushed, and atomically replaced. The directory is then flushed. A crash therefore leaves either the complete old record or the complete new record. A process-wide file lock serializes migration commands, while the marker excludes broker access.

Migrations are forward-only. Installing an older package after a schema change is unsupported unless that release deliberately supplies and tests a reverse migration. Ordinary upgrades must preserve every user selection; backups are not a substitute for deterministic validation and atomic replacement.

## Related design

- For current schemas, defaults, and data ownership, read [State](State.md#persistent-and-derived-state).
- For broker readiness and installation, read [Lifecycle](Lifecycle.md#startup-login-and-update-lifecycle).
- For activation after successful migration, follow [Package update](../Publishing.md#package-update-activation).
