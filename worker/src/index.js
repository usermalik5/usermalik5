// GeloTech-Tool auth proxy Worker — entry point.
//
// All route logic lives in src/handlers.js (testable in plain Node); this
// module only supplies the cloudflare-specific dependencies (sockets for
// SMTP, the global fetch) and the Request/Env plumbing.
//
// Secret bindings (wrangler secret put):
//   GITHUB_TOKEN        fine-grained PAT with Contents read/write on the repo
//   SMTP_PASSWORD       SMTP app password
//   SESSION_SECRET      HMAC key for signed login sessions
// Plain vars (wrangler.jsonc):
//   REPO_OWNER, REPO_NAME, REPO_BRANCH, SMTP_HOST, SMTP_PORT, SMTP_USER,
//   SMTP_FROM, ENABLE_RATE_LIMIT

import { connect } from "cloudflare:sockets";
import { handleRequest } from "./handlers.js";

export default {
  async fetch(request, env) {
    return handleRequest(request, env, { fetchImpl: fetch, io: { connect } });
  },
};