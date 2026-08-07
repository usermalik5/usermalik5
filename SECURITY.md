# Security Policy

## Supported Versions

Only the latest distributed build is supported. Data-only updates (database /
settings pushed to the repo) are supported for any build that includes the
embedded update system (commit `d382477` and later).

| Build | Supported |
|---|---|
| Latest exe (with embedded update system) | :white_check_mark: |
| Older exes | :x: |

## Reporting a Vulnerability

This is a private repository. If you have access and find a security issue
(such as the embedded update token or credential handling), report it to the
repository owner directly rather than opening a public issue.

## Known considerations

- The app embeds a GitHub token in `tech_common.py` for read-only update
  pulls from this private repo. Anyone with the exe can extract it. Before
  any public distribution, replace it with a fine-grained, read-only,
  repo-scoped token.
- User password hashes are salted PBKDF2 and stored in the settings file,
  which is marked hidden on disk. They are not plaintext, but the exe is
  local — treat the settings file as sensitive.
