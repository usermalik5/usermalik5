# GeloTech Agent Rules

## Before every coding task

1. Run:
   `python scripts/agent_preflight.py`
2. Read this file completely.
3. Read the relevant sections of `README.md`.
4. If the task touches a specialized subsystem, read its guide under `docs/`.
5. Inspect the current execution path before editing code.
6. Reproduce the problem when practical and identify the root cause before changing behavior.
7. Make the smallest correct change that fixes the root cause. Do not add speculative retries, timing hacks, monkey patches, or compatibility hooks when normal application code can own the behavior.
8. Run source-level checks after the change.
9. Review the complete diff before committing.

## Architecture rules

- `techtool.py` is the application shell/orchestrator. New reusable behavior belongs in a focused module or service.
- Navigation has one owner: `tech_navigation.py`. Dashboard is the universal post-login landing page.
- Background work should use `tech_task_manager.py`; worker threads must not update Tk widgets directly.
- Package database access should go through `tech_database.py` rather than duplicating cache/load logic.
- Pages should be created lazily where practical; do not eagerly initialize unrelated features before authentication.
- Mirror-specific compatibility behavior stays inside the mirror subsystem. Read `docs/SCRCPY_GUIDE.md` for mirror work. The mirror embeds the native scrcpy stream as a child window of the Dashboard phone widget; a single authorized device auto-opens the mirror 5 seconds after connect and it stays open (never auto-stops). The Dashboard log console is hidden while mirroring and restored on the Tk UI thread (configure width/height, then place) when the mirror stops.
- Theme and UI-font ownership lives in `tech_themes.py`: the 18 bundled CTkThemesPack palettes plus the UI-font picker (22 Windows families). The theme pass must recolor the GeloTech log consoles and the ttk App Cleaner list while preserving the physical phone/mirror display (widgets tagged `_gelotech_theme_role == "phone_display"` are left untouched).
- The App Cleaner table keeps its four-column layout (app name / package ID / UAD level / description) with a horizontal scrollbar for the full Description text; do not reintroduce a separate description panel.
- Per-device icon cache lives in `tech_secops4.py` (`action_sec_show_icons`, `icon_cache/<sha256(serial)[:32]>` under the settings dir); automatic sync triggers on a single newly connected device in `techtool.py::_auto_prepare_new_device_icons`.
- Do not create another mixin merely to avoid reorganizing a responsibility that is better represented by a service/component.

## Authentication and security

Security work is intentionally out of scope unless the task explicitly requests it. Do not change the existing authentication architecture as part of unrelated refactoring.

### Auth proxy Worker (do not regress)

Account operations are NOT done from the app with GitHub write credentials,
and the app contains NO credentials at all:

- The app calls the Cloudflare Worker at `AUTH_WORKER_URL` (`tech_common.py`)
  via `tech_reg.py`: `_login_user` (`POST /login`), `_request_password`
  (`POST /register`), `_set_user_blocked` (`POST /admin/block`), the users
  list `_fetch_verified_users` (`GET /accounts`, admin session required),
  and the update files `_worker_fetch` (`GET /files/<name>`, public
  allowlist: version.json, version.json.sig, gelotech_database_v3.json,
  banking_apps.json). The Worker verifies PBKDF2 hashes and the blocked
  flag server-side, emails generated passwords (SMTP is server-side), and
  signs login sessions (HMAC-SHA256, `SESSION_SECRET`, 12 h TTL).
- Admin authorization is a server-issued signed session sent as
  `Authorization: Bearer` - role comes only from the Worker's login
  response (`user.role == "admin"`). Admin login requires the password AND
  the admin secret phrase: the phrase is entered by the maintainer and sent
  with `POST /login` (`phrase` field), but it exists server-side only as
  the `ADMIN_SECRET_PHRASE` Worker secret - never embedded in the client.
  Every privileged call (`/accounts`, `/admin/block`, `/admin/password`)
  revalidates the session against the live account registry, so a blocked
  account is denied on its next authorized call — sessions are revocable
  not by an immediate cryptographic destroy but by per-request authorization
  revalidation. The client keeps the session token in memory only (`_auth_session`)
  and clears it on logout/app close.
- Maintainer password changes go through the Worker
  (`POST /admin/password`, `tech_reg._admin_set_password`) - the client
  never hashes or stores passwords; there is NO client-side PBKDF2 code
  (removed in v2.2.0).
- The repo write token, SMTP credentials and session-signing key must stay
  OUT of the app code (they exist only as Cloudflare Worker secrets; stale
  copies still embedded in `tech_common.py` are legacy and must not be used
  by app code). Do not reintroduce `_mutate_secret`/`_send_password_email`/
  write-token/read-token usage in the app.
- The signed database flow (version.json + Ed25519 + sha256-pinned
  `gelotech_database_v3.json`) is served by the Worker's `/files` allowlist
  and must keep working; the app still verifies the signature and hashes
  itself and never trusts the Worker for integrity.
- Worker code lives in `worker/` (tests: `node --test src/*.test.js`). After
  changing Worker routes or the response contract, update the app client in
  `tech_reg.py` and `tests/test_auth_proxy_client.py` in the same change.

## Testing

Minimum source check:

```bash
python -m compileall -q .
python -m pytest -q
```

For login/navigation changes, also run `python techtool.py` directly. If an EXE is affected, test the packaged build separately.

Distinguish real-device tests from mocked/no-device tests. Never claim a real-device fix from a mocked test.

## Code intelligence

Use LSP / semantic navigation features before broad text searches whenever they are available.

Preferred order:

1. Go to definition
2. Find references
3. Find implementations
4. Inspect inheritance / overrides
5. Inspect diagnostics, types, and imports
6. Use targeted text search only when semantic navigation is insufficient

Before modifying a symbol:

1. Find its definition.
2. Find all references.
3. Identify inheritance / override relationships.
4. Identify packaging / build references if the change affects EXE behavior.
5. Identify tests covering the behavior.
6. Then modify the smallest correct owner.

Rule: do not change an override before checking whether another module defines the
same method. This is especially important for the GeloTech mixin architecture,
where multiple mixins can define the same method name and only the MRO winner runs.

## Release

Use:

```bash
python scripts/release.py
```

The release helper validates the source tree, runs tests, regenerates PyArmor output, and builds the supported obfuscated EXE. It does not commit, tag, push, or publish releases.

### Documentation sync gate

Documentation is part of the release artifact. **Do not build, tag, or publish a release until `README.md`, `PROCESS_GUIDE.md`, and `AGENTS.md` describe the current source behavior.**

Before every release:

1. Review the code changes since the previous release and identify user-visible behavior, workflow changes, UI changes, packaging changes, and important development-process changes.
2. Update `README.md` for user-visible behavior and supported workflows.
3. Update `PROCESS_GUIDE.md` for architecture, execution flow, subsystem ownership, and build/release behavior.
4. Update `AGENTS.md` when agent rules, release gates, ownership rules, or mandatory workflow requirements change.
5. Run `python scripts/release.py`. The release script contains a documentation-sync gate and will stop the release if required markers are missing or the README release version is stale.
6. Do not bypass the documentation gate by using `--skip-tests`, a manual build, or a non-obfuscated build. Fix the documentation first.

The documentation gate intentionally checks current features that have historically drifted, including the CTkThemesPack theme picker and UI-font support, full App Cleaner descriptions exposed through the horizontal scrollbar, and automatic device icon preparation/cache behavior.

### Obfuscated build is mandatory for production

The **obfuscated** PyInstaller build (`GeloTechTool_obf.spec`, produced by
`python scripts/release.py` with no `--standard` flag) is the ONLY supported
production build. It is required because:

- This is production-level software; the released EXE must be PyArmor-obfuscated.
- The non-obfuscated `--standard` build exists ONLY for local debugging and
  must never be committed, tagged, pushed, or distributed.

Rule: **never run, rely on, or publish the `--standard` (non-obfuscated) build
unless the user explicitly asks for a debug build.** If PyArmor reports
`out of license` or a size/limit error, the fix is to split oversized source
modules into smaller files (~35 KB each) so the obfuscated build clears the
limit — NOT to fall back to `--standard`. Keep source modules at or below
~35 KB so PyArmor can obfuscate them.

### PyArmor Trial size gate

The repository currently uses the PyArmor Trial edition. Treat the approximate
**35 KB per-source-file limit as a hard release constraint**.

- **32 KB or more:** review the module for obvious extraction opportunities before adding more code.
- **35 KB or more:** do not attempt a production release build. Split the module into cohesive focused modules first.
- Keep the limit enforced by the release tooling rather than relying only on agent memory or documentation.
- When a module exceeds the threshold, report the exact file and size, split responsibilities cleanly, update PyArmor module lists and PyInstaller hidden imports, then rebuild.
- A PyArmor failure caused by the Trial size/license limit is a **release blocker**, not permission to use `--standard`.

The expected failure mode is:

```text
source module exceeds configured PyArmor Trial threshold
        -> release is stopped
        -> exact oversized file + byte size are reported
        -> module is split into focused files
        -> PyArmor is rerun
        -> obfuscated EXE is built and verified
```

A successful PyInstaller build without successful PyArmor obfuscation is **not**
a production build.

### Release bookkeeping (every release)

Every time a new release is built, tagged, or published (and on every
`APP_VERSION` bump), the agent MUST also:

1. Bump `APP_VERSION` in `tech_common.py` to the new version and keep it
   matching the release tag (`v<APP_VERSION>`).
2. Update the **"Latest release"** version text in `README.md` (Download
   section) to the new version, so the visible `(vX.Y.Z)` label matches the
   released tag. The `releases/latest` URL already redirects automatically,
   but the label is static and must be edited by hand.
3. Mention the version change in the release notes.
4. Rebuild the obfuscated EXE (`python scripts/release.py`) before tagging.
5. Publish the EXE to the **public download repo** `usermalik5/usermalik5`
   (the GeloTech-Tool repo is private, so its releases are not accessible to
   users). Create a matching release there and attach the EXE:
   `gh release create v<APP_VERSION> dist\\GeloTechTool.exe --repo usermalik5/usermalik5 --title "GeloTechTool v<APP_VERSION>" --notes-file <notes>`
   and make sure `https://github.com/usermalik5/usermalik5/releases/latest`
   redirects to it. The profile README's "Latest Release" link already points
   there; verify it after each release.
6. `gh` uses a fine-grained PAT scoped to `usermalik5/GeloTech-Tool` — it must
   also have access to `usermalik5/usermalik5` with **Contents: Read and
   write** (covers Releases). If the public-repo upload fails with HTTP 403,
   ask the user to add that repository access to the token before retrying.
7. Verify `SECURITY.md` still describes the current security model — the
   release script blocks the build if it drifts (it requires the
   `auth proxy Worker` / `wrangler secret put` / `AUTH_WORKER_URL` markers
   and rejects the obsolete embedded write-token/SMTP wording). If the
   auth/security model changed since the last release, update its "Current
   Security Model" section in the same release.

A release where `README.md` still shows an older `(vX.Y.Z)` label is
incomplete — treat the stale label as a release defect and fix it in the same
commit as the version bump.

## Documentation authority

- `AGENTS.md` defines mandatory agent behavior.
- `README.md` defines current application behavior and supported workflows.
- `PROCESS_GUIDE.md` is the long-form architecture/process reference.

When these documents conflict with the actual source code, stop and report the conflict. Do not guess or silently reintroduce behavior described only by stale documentation.
