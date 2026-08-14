# Security Policy

## Supported Versions

Only the latest distributed build is supported. Data-only updates (database /
settings pushed to the repo) are supported for builds that include the
embedded update system.

| Build | Supported |
|---|---|
| Latest exe (with embedded update system) | :white_check_mark: |
| Older exes | :x: |

## Reporting a Vulnerability

This is a private repository. If you have access and find a security issue
(such as an embedded credential, an authentication flaw in the auth proxy
Worker, or a credential-handling problem), report it to the repository owner
directly rather than opening a public issue.

## Current Security Model

- **Authentication goes through the auth proxy Worker** (Cloudflare,
  `worker/`, deployed at `AUTH_WORKER_URL`). Login, password requests and
  admin block/unblock are server-side operations:
  - passwords are verified with PBKDF2-SHA256 (100,000 iterations) on the
    Worker, never in the client;
  - generated passwords are hashed and written to the repo's `secret.json`
    and emailed by the Worker;
  - the repo write token (`GITHUB_TOKEN`), the SMTP app password and the
    admin phrase are **Cloudflare Worker secrets** (`wrangler secret put`) —
    they are not embedded in the exe;
  - the Worker only ever reads/writes `secret.json` and rate-limits login
    and registration per IP.
- The app embeds a **read-only** GitHub token used to fetch the signed
  update manifest and the package database, plus the Ed25519 public key used
  to verify `version.json.sig`. These remain extractable from the exe and
  must be rotated/scoped appropriately.
- The package database is fetched and SHA-256 verified (against the signed
  manifest) for each login, then kept only in the per-session temporary
  cache and removed when the session ends.
- Runtime settings use `exclusions.json`; `secret.json` is reserved for the
  live server-side account source and must not be used as a local settings
  file.
- Update manifests use an Ed25519 signature and signed SHA-256 data hashes.
- The admin phrase is checked on the Worker, and the admin password is
  verified server-side against the `admin` account's PBKDF2 hash. The
  phrase also remains embedded in the app (needed to unlock the admin
  option on the sign-in screen), so it must be rotated like any embedded
  secret. Destructive operations use additional confirmation/safety gates.
- Release builds are PyArmor-obfuscated, but obfuscation is not a substitute
  for secret rotation or server-side authorization.

## Known Considerations

Anything embedded in a Windows executable can eventually be extracted by a
sufficiently capable local attacker. The read-only fetch token and the admin
phrase are embedded and should be treated as operational secrets and rotated
regularly.

The privileged operations (account writes, password delivery) moved
server-side to the auth proxy Worker in v1.7.3. To rotate any of those
secrets, update them with `wrangler secret put` in `worker/` and redeploy —
no app release is needed (the admin phrase additionally lives in
`tech_common.py` and would require a release if changed).

The Worker's rate limiter is an in-memory per-isolate sliding window; for a
hard guarantee, add Cloudflare dashboard rate-limiting rules on top.
