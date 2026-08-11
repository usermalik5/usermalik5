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
(such as an embedded update token, SMTP credential, authentication flaw, or
credential-handling problem), report it to the repository owner directly
rather than opening a public issue.

## Current Security Model

- User accounts live in the GitHub `secret.json` source and are fetched at
  login. Passwords are stored as salted PBKDF2 hashes and are not written to
  users' PCs as local login credentials.
- The package database is fetched and SHA-256 verified for each login, then
  kept only in the per-session temporary cache and removed when the session
  ends.
- Runtime settings use `exclusions.json`; `secret.json` is reserved for the
  live server-side account source and must not be used as a local settings
  file.
- Update manifests use an Ed25519 signature and signed SHA-256 data hashes.
- The application contains embedded GitHub update credentials. The read
  credential should be fine-grained and repo-scoped; the account-write
  credential must be fine-grained, Contents Read+Write, and limited to this
  repository only. Both are extractable from a distributed executable and
  therefore must be rotated/scoped appropriately.
- The application also uses an embedded SMTP sender credential for account
  password delivery. It must be a dedicated low-privilege sender account and
  app password, never a personal mailbox credential.
- Admin access requires the maintainer access phrase plus the admin PBKDF2
  password. Destructive operations use additional confirmation/safety gates.
- Release builds are PyArmor-obfuscated, but obfuscation is not a substitute
  for secret rotation or server-side authorization.

## Known Considerations

Anything embedded in a Windows executable can eventually be extracted by a
sufficiently capable local attacker. In particular, GitHub write access and
SMTP credentials should be treated as operational secrets and rotated before
public distribution. Moving privileged operations behind a server-side API
would provide stronger protection in a future security pass.
