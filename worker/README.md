# GeloTech-Tool auth proxy (Cloudflare Worker)

The login/account flow no longer talks to GitHub directly from the client.
This Worker is the single component that holds the GitHub token, the SMTP
credentials, the session-signing key and the admin secret phrase (as
Cloudflare secrets), verifies passwords server-side (PBKDF2-SHA256,
compatible with the app's `secret.json` format), issues short-lived signed
admin sessions, and emails generated passwords to users. The app contains
no credentials of any kind.

## Routes

| Method | Path             | Auth                              | Body                        | Purpose                              |
|--------|------------------|-----------------------------------|-----------------------------|--------------------------------------|
| GET    | `/health`        | –                                 | –                           | Liveness                             |
| GET    | `/files/<name>`  | – (public update files only)      | –                           | version.json, version.json.sig, gelotech_database_v3.json, banking_apps.json |
| POST   | `/login`         | –                                 | `{email, password, phrase?}`| Server-side PBKDF2 verify + blocked check; admin additionally REQUIRES the secret phrase; returns `{ok, user{role,...}, session}` |
| POST   | `/register`      | – (rate limited)                  | `{email}`                   | Create/reset account, email the new password |
| GET    | `/accounts`      | `Authorization: Bearer <session>` | –                           | Sanitized account list (admin role only; no hashes) |
| POST   | `/admin/block`   | `Authorization: Bearer <session>` | `{email, blocked}`          | Block/unblock (admin role only; no phrase) |
| POST   | `/admin/password`| `Authorization: Bearer <session>` | `{email, password}`         | Set a new password for an account; hashed server-side, never logged |

Sessions are signed with HMAC-SHA256 using the `SESSION_SECRET` Worker
secret, carry `{sub, role, iat, exp, jti}` and expire after 12 hours. The
client keeps the token in memory only.

**Admin login is two-factor server-side**: the admin account's password
(PBKDF2) AND the admin secret phrase, which exists ONLY as the
`ADMIN_SECRET_PHRASE` Worker secret — never embedded in the client.
Missing or wrong phrase yields the same generic `invalid-credentials` and
no session; if the secret is not configured, admin login fails closed.

**Session revocation**: every privileged call (`/accounts`,
`/admin/block`, `/admin/password`) revalidates the session against the
live account registry — the account must still exist and must not be
blocked. Blocking an account therefore invalidates all of its sessions
immediately, regardless of the 12 h TTL.

All responses are JSON. Writes are structurally path-allowlisted to
`secret.json` only (`fetchSecret`/`putSecret` take no path), and retried on
concurrent-write (422) conflicts. Errors are generic: no stack traces, no
GitHub API details, no secret material ever reaches clients.

## Deploy

```powershell
cd worker
npm install

# secrets (one command each — these never appear in code):
npx wrangler secret put GITHUB_TOKEN      # fine-grained PAT, Contents read/write, this repo only
npx wrangler secret put SMTP_PASSWORD     # Gmail app password
npx wrangler secret put SESSION_SECRET    # random key for signing login sessions
npx wrangler secret put ADMIN_SECRET_PHRASE  # admin second factor; WITHOUT it admin login fails closed

npx wrangler deploy
```

The deploy output prints the Worker URL, e.g.
`https://gelotech-auth-proxy.angeloespinosa985.workers.dev`. Put that exact
URL in `AUTH_WORKER_URL` in `tech_common.py` and rebuild/release the app.

Live deployment: <https://gelotech-auth-proxy.angeloespinosa985.workers.dev>

## Rate limiting

The Worker keeps an in-memory sliding-window limiter (per IP, per route) as
a first line of defense, but Workers isolates do not share state, so that is
NOT a global counter. `handlers.js` supports the Cloudflare-native
`ratelimit` binding (`AUTH_RATE`): when bound, it becomes the global,
platform-level limiter (keys are per route + IP, sanitized to
`[a-zA-Z0-9_-]`) and the in-memory Map is bypassed.

To activate it (one-time, dashboard):

1. Cloudflare dashboard -> Workers & Pages -> `gelotech-auth-proxy` ->
   **Settings -> Rate limiting** -> create a namespace.
2. Uncomment the `ratelimit` block in `wrangler.jsonc` and paste the
   namespace id into it.
3. Redeploy (`npx wrangler deploy`). Done — no code changes needed.

Per-route in-Worker limits can still be tuned with vars
(`LOGIN_RATE_LIMIT`, `REGISTER_IP_RATE_LIMIT`, `REGISTER_EMAIL_RATE_LIMIT`,
`ACCOUNTS_RATE_LIMIT`, `ADMIN_BLOCK_RATE_LIMIT`, `FILES_RATE_LIMIT`).

## Local tests

`node --test src/` runs crypto (incl. vectors generated with the same Python
code the app uses), session signing/verification (expiry, tamper, malformed
tokens), the route handlers against a fake GitHub + fake SMTP (401/403
authz matrix, sanitized `/accounts`, rate limits, no secret leaks), the
GitHub contents mutation path (path allowlist, blob fallback) and the full
SMTP conversation (scripted fake socket).

## Caveats

- The in-memory rate limiter is per-isolate: a deterrent, not a hard limit.
  Configure the Cloudflare-native rate limiting binding (above) for hard
  guarantees.
- A new Gmail password is generated and sent by the Worker; the app never
  sees it and cannot send email anymore.
- Sessions are validated by signature + expiry server-side on every
  privileged call; there is no client-side trust.