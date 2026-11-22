# TAMS Repository Audit

Audit date: 2026-11-22

## Executive Summary

The repository has a well-defined desktop application structure, an
idempotent test database setup, and broad automated test coverage. The
migration graph has one head and applies successfully to a fresh database.
The audit also found 180 passing tests.

The highest-priority work is to verify and authenticate software updates,
protect sensitive log output, make database restore atomic, and harden
release automation.

## Security Findings

| # | Severity | File | Lines | Vulnerability | Confidence |
|---|----------|------|-------|---------------|------------|
| 1 | 🟠 HIGH | app/ui/app_update_dialog.py; app/services/coaching_helper_service.py | 59-82; 344-357; 389-425 | Downloaded installer is executed without signature or hash verification | 9/10 |
| 2 | 🟡 MEDIUM | .github/workflows/build-windows.yml | 70-79 | Third-party release action is mutable and receives repository write credentials | 8/10 |
| 3 | 🟡 MEDIUM | app/services/coaching_helper_service.py | 58-70; 429; 477; 884 | Sensitive-log filter sanitizes `record.msg` but not formatted `record.args` | 8/10 |

### 1. Verify downloaded installers

The update worker downloads an asset and executes it directly. The
application should verify a signed installer or publish and validate a
cryptographically strong hash for each release before execution.

Recommended changes:

- Pin update assets to the expected GitHub release and repository.
- Publish a trusted SHA-256 manifest or signature alongside each installer.
- Verify Authenticode plus the hash before launching the installer.
- Download only to a private, application-owned directory.
- Reject redirects or asset URLs outside the approved release domain.

### 2. Pin and restrict release automation

The release workflow grants `contents: write` and uses
`softprops/action-gh-release@v2` by mutable tag. Third-party actions should
be pinned to reviewed commit SHAs, and the workflow should run with the
minimum required permissions.

Recommended changes:

- Pin `actions/checkout`, `actions/setup-python`, `actions/upload-artifact`,
  and `softprops/action-gh-release` to immutable commit SHAs.
- Publish checksums and use authenticated signing for release artifacts.
- Consider code-signing the Windows executable and installer.
- Split build and release permissions so PR builds cannot receive secrets or
  write access.

### 3. Complete sensitive-log filtering

The sensitive-data filter only changes string values in `record.msg`. It does
not format and scrub `record.args`, so secrets embedded in exception or
argument formatting may reach disk.

Recommended changes:

- Sanitize the fully formatted log message.
- Avoid logging raw HTTP responses, exception bodies, or authorization
  headers.
- Add tests that cover string messages, formatted arguments, exceptions,
  bearer headers, and access tokens.

## Confirmed Reliability and Maintainability Findings

### 1. Database restore is not atomic

**File:** `app/services/backup_service.py`

**Lines:** 251-258

The restore function deletes `tams.db` before renaming the temporary restored
database into place. Although a pre-restore snapshot is attempted, a failure
during `rename()` or copy cleanup can leave the live database missing.

Recommended fix:

- Copy the backup to a verified temporary file.
- Atomically replace the database file where the platform supports it.
- Preserve the original database until the replacement is validated.
- Add rollback recovery if process or file operations fail.
- Test restore failure and process-restart scenarios.

### 2. Backup labels can create unsafe or surprising filenames

**File:** `app/services/backup_service.py`

**Lines:** 55-57

Custom backup labels are trimmed and appended directly to a filename. Labels
containing path separators or platform-invalid characters can create paths
outside the intended backup name or fail on Windows.

Recommended fix:

- Restrict labels to a short allowlist pattern such as letters, numbers,
  hyphens, and underscores.
- Reject or replace all other characters.
- Keep labels in separate metadata instead of filenames if arbitrary labels
  are required.

### 3. Fresh databases bypass the migration chain

**File:** `app/database/init_db.py`

**Lines:** 40-55

On a fresh database, initialization creates tables from SQLAlchemy metadata
and stamps the database at the migration head. This can hide differences
between model metadata and migration scripts and skips migration upgrade
testing.

Recommended fix:

- Create fresh databases through `alembic upgrade head`.
- Reserve stamp operations for explicit legacy-database upgrades.
- Make migration startup fail clearly rather than silently continuing after
  migration exceptions.
- Add tests for migration upgrades at representative historical revisions.

### 4. Restore, backup, and test lifecycle has process edge cases

**Files:** `app/services/backup_service.py`,
`app/services/coaching_helper_service.py`, `app/ui/settings_dialog.py`

Restore can stop and restart the companion, but it disposes SQLAlchemy
connections and replaces the database while the main UI may still have active
sessions or workers. Concurrent process behavior should be coordinated and
tested more explicitly.

Recommended changes:

- Stop both application and helper database workers during restore.
- Hold an application-level restore lock or use a dedicated IPC state.
- Resume workers only after validation and successful connection reopening.
- Add integration tests for concurrent helper, backup, restore, and UI usage.

### 5. Logging can expose operational data

The main crash logger writes raw tracebacks, and the companion logger has
credential masking but incomplete argument handling. Desktop crash logs can
contain database values, API response details, or customer information.

Recommended changes:

- Centralize a single log-filter implementation across all processes.
- Limit traceback detail in user-facing logs.
- Define an explicit sensitive-field and secret-redaction policy.
- Document log retention and removal behavior.

## Dependency and Build Improvements

### 1. Separate runtime and development dependencies

**Files:** `requirements.txt`, `pyproject.toml`

PyInstaller and pytest are runtime-delivery dependencies in
`requirements.txt`. This increases installer build size and the dependency
surface.

Recommended changes:

- Keep runtime dependencies in the base package or lock file.
- Move pytest and PyInstaller to a development extra.
- Pin exact versions or lock transitive dependencies for reproducible builds.
- Add dependency vulnerability scanning to CI.

### 2. Add build reproducibility and artifact verification

**File:** `.github/workflows/build-windows.yml`

The workflow does not publish hashes or signatures, does not verify the
Chocolatey-installed Inno Setup package, and uses mutable actions.

Recommended changes:

- Pin Python, action, package, and tool versions.
- Build from a locked dependency set.
- Generate SHA-256SUMS for release artifacts.
- Sign the executable and installer.
- Upload artifacts on pull requests and only publish signed tagged releases.

### 3. Modernize packaging metadata

**Files:** `pyproject.toml`, `tams.spec`, `installer.iss`

The project metadata and installer are mostly consistent, but packaging
could be more maintainable.

Recommended changes:

- Derive the installer and package version from `pyproject.toml` instead of
  duplicating 2.2.1 in three places.
- Add package URL, classifiers, and an entry-point smoke test.
- Verify PyInstaller configuration in CI rather than only during manual
  release builds.
- Document supported Windows architecture and upgrade behavior.

## Documentation Improvements

### 1. Remove stale version filenames

**Files:** `README.md`, `build_windows.bat`, `installer.iss`

The documentation and build output still mention `TAMS_Setup_v2.0.0.exe`
while project metadata is 2.2.1.

Recommended changes:

- Replace stale 2.0.0 references with 2.2.1 or version-neutral names.
- Add a release section to prevent README/build-script version drift.
- Document that the Windows installer stores application data in the
  user application-data directory.

### 2. Document database and migration operations

The README does not fully explain migration history, restore behavior, backup
retention, WAL files, or failure recovery.

Recommended changes:

- Add an operator guide for backup, restore, migration, log, and uninstall
  operations.
- Document supported upgrade paths and database rollback behavior.
- Document safe companion shutdown and restart procedures.

### 3. Improve developer setup

The repository lacks a dedicated development setup target and quality tooling
configuration.

Recommended changes:

- Provide virtual-environment setup instructions for Linux and Windows.
- Document test categories and offscreen Qt execution.
- Add formatter, linter, type-check, and security scan commands.
- Use a pre-commit configuration to run fast checks.

## Testing Improvements

The suite currently passes all 180 tests and includes service, UI, migration,
messaging, backup, and lifecycle coverage.

Additional recommended coverage:

- Historical migration upgrade and downgrade tests.
- Fresh-database initialization without pre-stamping.
- Database restore success, copy failure, rename failure, and rollback.
- Concurrent TAMS and CoachingHelper database access.
- Malformed and hostile custom backup labels.
- Sensitive logs containing formatted arguments and exception values.
- Update asset redirect, checksum mismatch, invalid file, and canceled download.
- PyInstaller smoke tests for both executables.
- Inno Setup installer upgrade, uninstall, and autostart tests.
- CI tests across supported Python and Windows versions.
- Test coverage reporting and a minimum threshold on changed code.

## Code Quality Improvements

- Replace broad `except Exception: pass` blocks in critical backup, restore,
  logging, IPC, and update paths with explicit recovery or status reporting.
- Standardize service return values, validation errors, and exception handling.
- Add a shared data-validation layer for external API and UI inputs.
- Split large UI mixins and service modules where responsibilities have
  become too broad.
- Add explicit timeouts and retry limits to all external HTTP operations.
- Define and test cross-process ownership rules for SQLite, WAL, and backup
  files.
- Remove or document environment variables used for test/runtime isolation.
- Configure logging format and levels consistently across both executables.

## Validation Performed

- Installed project dependencies into a temporary virtual environment.
- Ran `QT_QPA_PLATFORM=offscreen python -m pytest -q`: 180 tests passed.
- Ran `python -m compileall` for application and entry-point sources.
- Verified Alembic has a single migration head: `d4e5f6a7b8c9`.
- Applied the complete migration chain to a fresh SQLite database without
  migration errors.
