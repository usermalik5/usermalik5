# Project Instructions

- Whenever a major change is made to the source code, update `README.md` accordingly before committing.
- When a major change is made to the source code, also update `PROCESS_GUIDE.md` (the process tree visual guide) when necessary — e.g. new modules, changed architecture, changed update/release flow, or new data locations.

## Security & Release Rules (DO NOT VIOLATE)

1. **OBFUSCATION APPLIES TO ALL CODE AND ALL BUILDS.** Every release exe MUST be built from the PyArmor-obfuscated spec (`GeloTechTool_obf.spec`), never the plain `GeloTechTool.spec`. Before building, ALWAYS re-run `pyarmor gen` over **every** Python module in the project (techtool.py + ALL `tech_*.py` files) so new/changed code is always obfuscated. Never ship an un-obfuscated exe. Because obfuscation hides imports from PyInstaller's static analysis, ANY new import (stdlib or 3rd-party) in a `tech_*.py` module MUST also be added to `hiddenimports` in `GeloTechTool_obf.spec` — otherwise the exe crashes at startup with `ModuleNotFoundError`.
2. **UPDATE MANIFESTS ARE SIGNED.** Every data release MUST be published with `python bump_version.py` (or `--no-commit` first to stage files). It computes SHA-256 of the data files, writes them into `version.json`, and writes the Ed25519 signature into `version.json.sig`. The app refuses unsigned/tampered updates (verifies against `tech_common.py::UPDATE_SIGN_PUBLIC_KEY`). Never edit `version.json` or data files without re-signing, and never commit `version.json.sig` without a matching `version.json`. Signed hashes MUST cover the exact bytes GitHub serves — `.gitattributes` forces `eol=lf` for `*.json` and `version.json.sig`; if you renormalize or touch line endings, re-sign.
3. **UPDATE SOURCE IS PINNED.** The app only ever fetches from `EMBEDDED_UPDATE_URL` / `EMBEDDED_UPDATE_TOKEN` in `tech_common.py`. Never re-introduce `update_url`/`update_token` overrides from settings or from the repo's `secret.json`.
4. **GITHUB-ONLY DATA, NO LOCAL CREDENTIALS.** User accounts (`secret.json`) and the package database (`gelotech_database_v3.json`) are NEVER stored locally or bundled into the exe. Both are fetched from the pinned update server on every login (manifest signature + DB sha256 verified); the DB is cached for the session and deleted on app close/logout/next login. `secret.json` is the LIVE accounts file: users self-register by entering their email, the app generates a PBKDF2 password, writes it back to the repo via the embedded write token, and emails it via the embedded SMTP sender. Accounts carry an optional `blocked: true` flag (set from the Admin Panel) that denies login AND password requests. `secret.json` is therefore NOT covered by the signed manifest (database + banking list are). Passwords must stay PBKDF2 (`iters$salt$digest`) — never legacy plain SHA-256.
5. **SECRETS.** The signing private key (`%USERPROFILE%\.gelotech_signing\update_ed25519.pem`) must NEVER be committed or copied into the repo. The embedded write token (`EMBEDDED_UPDATE_WRITE_TOKEN`) and SMTP app password are extractable from the exe by a determined attacker — they MUST be scoped/rotated: write token = fine-grained, Contents Read+Write, THIS repo only; SMTP = dedicated low-privilege sender account with an app password. Never embed your personal account credentials. Admin access in the app is gated by the `ADMIN_SECRET_PHRASE` (login screen) + the PBKDF2 admin password — never change the admin password to a weak/default value.

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
