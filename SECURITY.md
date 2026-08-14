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

- **The app contains no credentials.** All GitHub access, SMTP access and
  account management happen server-side in the auth proxy Worker
  (Cloudflare, `worker/`, deployed at `AUTH_WORKER_URL`):
  - login (`POST /login`): the Worker verifies the password with
    PBKDF2-SHA256 (100,000 iterations), checks the account's `blocked`
    flag, and returns a signed session token plus a sanitized user record
    (role/permissions/tabs, never the hash);
  - password requests (`POST /register`): the Worker generates a CSPRNG
    password, hashes it into the repo's `secret.json`, and emails it to
    the user;
  - admin actions (`GET /accounts`, `POST /admin/block`): require a valid
    signed session with `role: "admin"` sent as `Authorization: Bearer`.
    There is no admin secret phrase anywhere.
  - update files (`GET /files/<name>`): the Worker serves the version
    manifest, its Ed25519 signature, the package database and the banking
    list from the public path allowlist; the app verifies the signature
    and the SHA-256 of each file itself.
  - the repo write token (`GITHUB_TOKEN`), the SMTP app password and the
    session-signing key (`SESSION_SECRET`) are **Cloudflare Worker
    secrets** (`wrangler secret put`) — none of them are embedded in the
    exe.
- The Worker keeps **no session state**: sessions are stateless HMAC-SHA256
  tokens (`{sub, role, iat, exp, jti}`, 12 h TTL) verified on every
  privileged call. The client holds the token in memory only and discards
  it on logout/exit.
- Client-side reads are limited to public update files; integrity is
  enforced with the embedded Ed25519 public key (`UPDATE_SIGN_PUBLIC_KEY`),
  which is not a secret.
- The package database is fetched and SHA-256 verified (against the signed
  manifest) for each login, then kept only in the per-session temporary
  cache and removed when the session ends.
- Runtime settings use `exclusions.json`; `secret.json` is reserved for the
  live server-side account source and must not be used as a local settings
  file.
- The Worker only ever reads/writes `secret.json` (path allowlisted in
  code, no user-supplied path) and rate-limits login and registration per
  IP (in-memory sliding window; see the Worker README for the
  Cloudflare-native binding for hard guarantees).
- Release builds are PyArmor-obfuscated, but obfuscation is not a substitute
  for secret rotation or server-side authorization.

## Known Considerations

Anything embedded in a Windows executable can eventually be extracted by a
sufficiently capable local attacker. Today the exe embeds no secret: only
the public Ed25519 verification key and the Worker URL, both safe to ship.

The privileged operations (account writes, password delivery, admin
authorization) moved server-side to the auth proxy Worker in v1.7.3; admin
authorization moved from a shared embedded phrase to server-issued signed
sessions in v2.0.0. To rotate the Worker secrets, update them with
`wrangler secret put` in `worker/` and redeploy — no app release is needed.

The Worker's rate limiter is an in-memory per-isolate sliding window; for a
hard guarantee, add Cloudflare dashboard rate-limiting rules on top (steps
in `worker/README.md`).

## Rotation Checklist (manual, after any exposure)

1. GitHub: revoke the fine-grained PAT in GitHub -> Settings -> Developer
   settings -> Personal access tokens, create a replacement scoped to
   Contents read/write on this repository only, then
   `npx wrangler secret put GITHUB_TOKEN` in `worker/`.
2. Gmail: revoke the app password (Google Account -> Security -> App
   passwords), create a new one, then
   `npx wrangler secret put SMTP_PASSWORD`.
3. Sessions: replace `SESSION_SECRET` with a fresh random value
   (`npx wrangler secret put SESSION_SECRET`); this invalidates all active
   sessions.
4. Redeploy the Worker (`npx wrangler deploy`). No app release required.