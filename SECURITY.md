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

