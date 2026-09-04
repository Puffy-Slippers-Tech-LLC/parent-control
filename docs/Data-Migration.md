# Saved-data migration

Oh No! Parent Control migrates application-owned persistent data automatically during package configuration. Data schema versions are independent of Debian package versions: package releases may leave a schema unchanged, and one release may migrate more than one saved-data family.

The current framework migrates the per-child records in `/var/lib/oh-no-parent-control/preferences/`. Machine configuration, transient markers, logs, AccountsService, Malcontent, and files managed as Debian conffiles are not preference data and must not be added to that migration chain. If another application-owned data family later needs versioning, give it its own current-version constant, migration registry, validation, and migration pass in `migrate_all_state()`.

## Package lifecycle

`debian/preinst` creates `/var/lib/oh-no-parent-control/migration-in-progress` before a new payload is unpacked. Both the broker launcher and its systemd unit refuse to start while that marker exists. `preinst` explicitly stops a running broker before package files or saved records can change.

After unpacking, `debian/postinst` runs the newly installed `/usr/libexec/oh-no-parent-control-migrate-state`. It removes the marker only after all migrations and current-schema validation succeed, then continues with provisioning and package-update activation.

The maintainer script deliberately fails if migration fails. The marker then keeps the broker unavailable and APT leaves the package unconfigured. Fixing the underlying record or migration and running `dpkg --configure -a` retries the operation. A successfully migrated record is skipped on retry, so an interruption between records is safe.

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
