# Project Instructions

- Whenever a major change is made to the source code, update `README.md` accordingly before committing.
- When a major change is made to the source code, also update `PROCESS_GUIDE.md` (the process tree visual guide) when necessary — e.g. new modules, changed architecture, changed update/release flow, or new data locations.

## Security & Release Rules (DO NOT VIOLATE)

1. **OBFUSCATION APPLIES TO ALL CODE AND ALL BUILDS.** Every release exe MUST be built from the PyArmor-obfuscated spec (`GeloTechTool_obf.spec`), never the plain `GeloTechTool.spec`. Before building, ALWAYS re-run `pyarmor gen` over **every** Python module in the project (techtool.py + ALL `tech_*.py` files) so new/changed code is always obfuscated. Never ship an un-obfuscated exe.
2. **UPDATE MANIFESTS ARE SIGNED.** Every data release MUST be published with `python bump_version.py` (or `--no-commit` first to stage files). It computes SHA-256 of the data files, writes them into `version.json`, and writes the Ed25519 signature into `version.json.sig`. The app refuses unsigned/tampered updates (verifies against `tech_common.py::UPDATE_SIGN_PUBLIC_KEY`). Never edit `version.json` or data files without re-signing, and never commit `version.json.sig` without a matching `version.json`.
3. **UPDATE SOURCE IS PINNED.** The app only ever fetches from `EMBEDDED_UPDATE_URL` / `EMBEDDED_UPDATE_TOKEN` in `tech_common.py`. Never re-introduce `update_url`/`update_token` overrides from settings or from the repo's `secret.json`.
4. **SECRETS.** The signing private key (`%USERPROFILE%\.gelotech_signing\update_ed25519.pem`) must NEVER be committed or copied into the repo. Never embed write-scoped tokens or API keys in code. The embedded GitHub token is read-only (fine-grained) — if you ever need write access (release creation), do it manually or with a separate local token, never embedded.

## Build Exe Agent

---
description: Execute a task with strict boundary enforcement and concise output
agent: build exe
---
### Operating Constraints
1. DO NOT write or edit files if any ambiguities exist—ask clarifying questions FIRST.
2. Suppress step-by-step internal reasoning and verbose thought logs in your final answer.
3. Keep response output focused strictly on the final summary format.

---
### Task
$ARGUMENTS

### Project Rules
- Follow existing project style guidelines and architectural patterns.
- Do not introduce external dependencies without explicit review.

### Strict Guardrails (DO NOT ALTER)
- Do not modify files outside the immediate scope unless strictly necessary.

---
### Required Output Format
Provide output strictly matching this layout:
1. **Status / Questions**: (Clarifying questions if stuck, or confirmation if clear)
2. **Planned / Changed Files**:
3. **Verification Command Executed**:
4. **Open Items for Human Review**:
