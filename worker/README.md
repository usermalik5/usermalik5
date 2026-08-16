# GeloTech-Tool Auth Proxy (Cloudflare Worker)

The login/account flow is server-side. The current desktop client is the
**PySide6 / Qt6** application launched by `tech_qt_app.py`; the Qt6 migration
changed the UI layer but does not change the Worker API or the security model.

The Worker is the single component that holds the GitHub token, SMTP
credentials, session-signing key and admin secret phrase as Cloudflare
secrets. It verifies passwords server-side, issues short-lived signed admin
sessions, serves verified update files, and emails generated passwords.

## Qt6 client integration

The Qt desktop client uses the same routes and contracts as the previous UI:

- `POST /login` — sign in and receive the signed session/user response.
- `POST /register` — request/create/reset an account password.
- `GET /accounts` — admin-only sanitized account list.
- `POST /admin/block` — admin block/unblock.
- `POST /admin/password` — admin password change.
- `POST /admin/role` — admin role change.
- `GET /files/<name>` — verified update/data files.

The Qt6 client must never receive, embed or persist the Worker secrets. Changes
to these routes must update the desktop client, `SECURITY.md`, `README.md` and
relevant tests together.

## Routes

| Method | Path | Auth | Body | Purpose |
|---|---|---|---|---|
| GET | `/health` | – | – | Liveness |
| GET | `/files/<name>` | public update files only | – | `version.json`, signature, package database, banking list |
| POST | `/login` | – | `{email, password, phrase?}` | Server-side password/blocked verification; admin also requires the Worker secret phrase |
| POST | `/register` | rate limited | `{email}` | Create/reset account and email password |
| GET | `/accounts` | admin session | – | Sanitized account list |
| POST | `/admin/block` | admin session | `{email, blocked}` | Block/unblock account |
| POST | `/admin/password` | admin session | `{email, password}` | Change account password |
| POST | `/admin/role` | admin session | `{email, role}` | Set `admin` or `user` role |

Sessions are HMAC-SHA256 signed with `SESSION_SECRET`, contain `{sub, role,
iat, exp, jti}` and expire after 12 hours. The desktop client keeps the
session token in memory only.

## Deploy

```powershell
cd worker
npm install

npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put SMTP_PASSWORD
npx wrangler secret put SESSION_SECRET
npx wrangler secret put ADMIN_SECRET_PHRASE

npx wrangler deploy
```

Put the deployed Worker URL into `AUTH_WORKER_URL` in the shared client
configuration and rebuild the desktop application when the URL itself changes.

## Rate limiting

The Worker has an in-memory per-isolate limiter and supports the Cloudflare
native `AUTH_RATE` binding for global/platform-level limiting. Follow the
Cloudflare setup in `wrangler.jsonc` before relying on the native binding.

## Local tests

```bash
node --test src/
```

Tests cover cryptographic verification, sessions, authz, rate limits, account
sanitization, GitHub contents access, and SMTP behavior.

## Security coordination

Keep [`../SECURITY.md`](../SECURITY.md), [`../README.md`](../README.md),
[`../AGENTS.md`](../AGENTS.md), and this file synchronized. The desktop Qt6
migration should not move server-side credentials into the client or weaken
route/session verification.
