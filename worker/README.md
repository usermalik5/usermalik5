# GeloTech-Tool auth proxy (Cloudflare Worker)

The login/account flow no longer talks to GitHub directly from the client.
This Worker is the single component that holds the write token, the SMTP
credentials and the admin phrase (as Cloudflare secrets), verifies passwords
server-side (PBKDF2-SHA256, compatible with the app's `secret.json` format),
and emails generated passwords to users.

## Routes

| Method | Path             | Body                        | Purpose                              |
|--------|------------------|-----------------------------|--------------------------------------|
| GET    | `/health`        | –                           | Liveness                             |
| GET    | `/accounts`      | –                           | Full user registry (parity with the old client-side GitHub fetch) |
| POST   | `/login`         | `{email, password}`         | Server-side PBKDF2 verify + blocked check; returns `{ok, user, reason}` |
| POST   | `/register`      | `{email}`                   | Create/reset account, email the new password |
| POST   | `/admin/block`   | `{phrase, email, blocked}`  | Maintainer block/unblock (admin phrase checked here) |

All responses are JSON. Writes are path-allowlisted to `secret.json` only,
and retried on concurrent-write (422) conflicts. The Worker never returns the
token. Rate limiting is per-IP in-memory (sliding window); add Cloudflare
dashboard rate-limiting rules for hard guarantees.

## Deploy

```powershell
cd worker
npm install

# secrets (one command each — these never appear in code):
npx wrangler secret put GITHUB_TOKEN
npx wrangler secret put SMTP_PASSWORD
npx wrangler secret put ADMIN_SECRET_PHRASE

npx wrangler deploy
```

`GITHUB_TOKEN`: fine-grained PAT with Contents read/write on
`usermalik5/GeloTech-Tool` (the existing `EMBEDDED_UPDATE_WRITE_TOKEN` value
works). `SMTP_PASSWORD`: the Gmail app password. `ADMIN_SECRET_PHRASE`: the
same phrase embedded in the app (`ADMIN_SECRET_PHRASE` in `tech_common.py`).

The deploy output prints the Worker URL, e.g.
`https://gelotech-auth-proxy.angeloespinosa985.workers.dev`. Put that exact
URL in `AUTH_WORKER_URL` in `tech_common.py` and rebuild/release the app.

Live deployment: <https://gelotech-auth-proxy.angeloespinosa985.workers.dev>
(secrets set via `wrangler secret put`; redeploy after changes with
`npx wrangler deploy`).

## Local tests

`node --test src/` runs crypto (incl. vectors generated with the same Python
code the app uses), the GitHub contents mutation path (fake fetch) and the
full SMTP conversation (scripted fake socket).

## Caveats

- The in-memory rate limiter is per-isolate: each of the ~dozens of isolates
  keeps its own counter, so it is a deterrent, not a hard limit.
- A new Gmail password is generated and sent by the Worker; the app never
  sees it and cannot send email anymore.
