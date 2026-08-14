// GitHub Contents API access. The Worker is the ONLY component that holds
// the write token; it exists solely as the GITHUB_TOKEN Worker secret and
// is never returned to clients or included in errors.
//
// Writes are structurally allowlisted: fetchSecret/putSecret have NO path
// parameter — they can only ever read/write SECRET_FILE, so the Worker can
// never become an arbitrary GitHub-write proxy. Reads of public update
// files go through fetchFile(), which accepts only the PUBLIC_FILES set.

export const SECRET_FILE = "secret.json";

// Files the Worker is allowed to serve to any client (GET /files/<name>).
// The update manifest, its signature and the data files are public content:
// integrity is enforced client-side via the Ed25519 signature + SHA-256.
export const PUBLIC_FILES = new Set([
  "version.json",
  "version.json.sig",
  "gelotech_database_v3.json",
  "banking_apps.json",
]);

export function isPublicFile(name) {
  return typeof name === "string" && PUBLIC_FILES.has(name);
}

export function ghHeaders(env) {
  return {
    Authorization: `Bearer ${env.GITHUB_TOKEN}`,
    Accept: "application/vnd.github+json",
    "User-Agent": "gelotech-auth-proxy",
  };
}

export function ghUrl(env, path = "") {
  return `https://api.github.com/repos/${env.REPO_OWNER}/${env.REPO_NAME}/contents/${path}`;
}

export function ghBlobUrl(env, sha) {
  return `https://api.github.com/repos/${env.REPO_OWNER}/${env.REPO_NAME}/git/blobs/${sha}`;
}

export async function fetchSecret(env, fetchImpl = fetch) {
  const url = `${ghUrl(env, SECRET_FILE)}?ref=${env.REPO_BRANCH}`;
  const res = await fetchImpl(url, { headers: ghHeaders(env) });
  if (!res.ok) throw new Error(`GET secret.json failed: ${res.status}`);
  const meta = await res.json();
  const bytes = Uint8Array.from(atob(meta.content), (c) => c.charCodeAt(0));
  const data = JSON.parse(new TextDecoder().decode(bytes));
  return { data, sha: meta.sha };
}

export async function putSecret(env, data, sha, message, fetchImpl = fetch) {
  const body = JSON.stringify(data, null, 2);
  const payload = {
    message,
    content: btoa(new TextEncoder().encode(body).reduce(
      (s, b) => s + String.fromCharCode(b), ""
    )),
    sha,
    branch: env.REPO_BRANCH,
  };
  const res = await fetchImpl(ghUrl(env, SECRET_FILE), {
    method: "PUT",
    headers: ghHeaders(env),
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw Object.assign(new Error(`PUT secret.json failed: ${res.status}`), { status: res.status });
  return res;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export async function mutateSecret(env, mutator, message, fetchImpl = fetch) {
  for (let attempt = 0; attempt < 4; attempt++) {
    try {
      const { data, sha } = await fetchSecret(env, fetchImpl);
      const next = mutator(data);
      await putSecret(env, next, sha, message, fetchImpl);
      return { ok: true };
    } catch (e) {
      if (e.status === 422 && attempt < 3) {
        await sleep(1500);
        continue;
      }
      return { ok: false, error: e.message || String(e) };
    }
  }
  return { ok: false, error: "Account registry write failed." };
}

// Fetches a file's exact committed bytes (contents API, with the git blobs
// API fallback for files larger than 1 MB where the contents API returns an
// empty `content`). Only names in PUBLIC_FILES are accepted.
export async function fetchFile(env, name, fetchImpl = fetch) {
  if (!isPublicFile(name)) throw new Error(`File not allowed: ${name}`);
  const metaRes = await fetchImpl(`${ghUrl(env, name)}?ref=${env.REPO_BRANCH}`, {
    headers: ghHeaders(env),
  });
  if (!metaRes.ok) throw new Error(`File fetch failed: ${metaRes.status}`);
  const meta = await metaRes.json();
  if (meta.content) {
    return Uint8Array.from(atob(meta.content), (c) => c.charCodeAt(0));
  }
  if (!meta.sha) throw new Error("No blob sha returned");
  const blobRes = await fetchImpl(ghBlobUrl(env, meta.sha), { headers: ghHeaders(env) });
  if (!blobRes.ok) throw new Error(`Blob fetch failed: ${blobRes.status}`);
  const blob = await blobRes.json();
  if (!blob.content) throw new Error("Blob content missing");
  return Uint8Array.from(atob(blob.content), (c) => c.charCodeAt(0));
}
