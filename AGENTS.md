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
- Mirror-specific compatibility behavior stays inside the mirror subsystem. Read `docs/SCRCPY_GUIDE.md` for mirror work.
- Do not create another mixin merely to avoid reorganizing a responsibility that is better represented by a service/component.

## Authentication and security

Security work is intentionally out of scope unless the task explicitly requests it. Do not change the existing authentication architecture as part of unrelated refactoring.

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

## Documentation authority

- `AGENTS.md` defines mandatory agent behavior.
- `README.md` defines current application behavior and supported workflows.
- `PROCESS_GUIDE.md` is the long-form architecture/process reference.

When these documents conflict with the actual source code, stop and report the conflict. Do not guess or silently reintroduce behavior described only by stale documentation.
