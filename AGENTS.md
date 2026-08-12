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

## Documentation authority

- `AGENTS.md` defines mandatory agent behavior.
- `README.md` defines current application behavior and supported workflows.
- `PROCESS_GUIDE.md` is the long-form architecture/process reference.

When these documents conflict with the actual source code, stop and report the conflict. Do not guess or silently reintroduce behavior described only by stale documentation.
