# Security Policy

## Supported Versions

Only the latest distributed build is supported. Data-only updates (database /
settings pushed to the Cloudflare DB/KV environments) are supported for builds that include the
embedded update system.

| Build | Supported |
|---|---|
| Latest exe (with embedded update system) | :white_check_mark: |
| Older exes | :x: |

## Current desktop architecture

The Qt6 migration changed the desktop UI architecture but
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
  (Cloudflare, `worker/`, the Worker verifies the password with
  PBKDF2-SHA256 (100,000 iterations), checks the account's `blocked`
  flag, and returns a signed session token plus a sanitized user record
  (role/permissions/tabs, never the hash). 

