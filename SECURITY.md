# Security Policy

## Supported Versions

Only the latest distributed build is supported. Data-only updates (database /
settings pushed to the repo) are supported for builds that include the
embedded update system.

| Build | Supported |
|---|---|
| Latest exe (with embedded update system) | :white_check_mark: |
| Older exes | :x: |

## Current desktop architecture

The current Windows client uses **PySide6 / Qt6** and starts from
`tech_qt_app.py`. The Qt6 migration changed the desktop UI architecture but
did **not** move authentication, account secrets, update signing, or other
privileged security responsibilities into the client. The security model
below remains server-side and applies to the Qt client as well as the packaged
Qt executable.

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
    (role/permissions/tabs, never the hash). **Admin login additionally
    requires the admin secret phrase** (`ADMIN_SECRET_PHRASE`), which
    exists only as a Worker secret — never embedded in the client. A
    missing or wrong phrase returns the same generic
    `invalid-credentials` and no session; if the secret is not configured,
    admin login fails closed;
  - password requests (`POST /register`): the Worker generates a CSPRNG
    password, hashes it into the repo's `secret.json`, and emails it to
    the user;
  - admin actions (`GET /accounts`, `POST /admin/block`,
    `POST /admin/password`): require a valid signed session with
    `role: "admin"` sent as `Authorization: Bearer`. Every privileged call
    revalidates the session against the live account registry, so a blocked
    account (or a deleted one) loses access immediately —
    sessions are effectively revocable;
  - password changes (`POST /admin/password`): the maintainer sets a new
    password for any account; hashing happens server-side, the value is never
    logged;
  - update files (`GET /files/<name>`): the Worker serves the version
    manifest, its Ed25519 signature, the package database and the banking
    list from the public path allowlist; the app verifies the signature
    and the SHA-256 of each file itself.
  - the repo write token (`GITHUB_TOKEN`), the SMTP app password, the
    session-signing key (`SESSION_SECRET`) and the admin secret phrase
    (`ADMIN_SECRET_PHRASE`) are **Cloudflare Worker secrets**
    (`wrangler secret put`) — none of them are embedded in the exe.
- The Worker keeps **no session state**: sessions are stateless HMAC-SHA256
  tokens (`{sub, role, iat, exp, jti}`, 12 h TTL) verified on every
  privileged call. The client holds the token in memory only and discards
  it on logout/exit.
- Client-side reads are limited to public update files; integrity is
  enforced with the embedded Ed25519 public key (`UPDATE_SIGN_PUBLIC_KEY`),
  which is not a secret.
- The package database is fetched and SHA-256 verified against the signed
  manifest for each login, then kept only in the per-session temporary cache
  and removed when the session ends.
- Runtime settings use `exclusions.json`; `secret.json` is reserved for the
  live server-side account source and must not be used as a local settings
  file.
- The Worker only ever reads/writes `secret.json` using its code-level path
  allowlist and applies route rate limiting. See [`worker/README.md`](worker/README.md)
  for deployment and Cloudflare-native rate limiting.
- Release builds are PyArmor-obfuscated, but obfuscation is not a substitute
  for secret rotation or server-side authorization.

## Known Considerations

Anything embedded in a Windows executable can eventually be extracted by a
sufficiently capable local attacker. Today the exe embeds no secret: only the
public Ed25519 verification key, Worker URL, Qt resources and application
logic are shipped.

The Qt6 migration does not change the Worker authentication contract. Keep the
client, `worker/README.md`, and this document synchronized whenever the auth
routes, session model, update verification, or secret handling changes.

## Rotation Checklist (manual, after any exposure)

1. GitHub: revoke the fine-grained PAT, create a replacement scoped to the
   required repository contents, then run `npx wrangler secret put GITHUB_TOKEN`
   in `worker/`.
2. Gmail: revoke the app password, create a new one, then run
   `npx wrangler secret put SMTP_PASSWORD`.
3. Sessions: replace `SESSION_SECRET` with a fresh random value; this
   invalidates all active sessions.
4. Admin secret phrase: replace `ADMIN_SECRET_PHRASE` with a fresh value and
   redeploy it. Until the new value is deployed, admin logins fail closed.
5. Redeploy the Worker (`npx wrangler deploy`). No desktop code release is
   required for a Worker-secret-only rotation.
