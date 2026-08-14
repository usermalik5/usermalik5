// GitHub Contents API access for secret.json. The Worker is the ONLY
// component that holds the write token; every mutation is path-allowlisted
// to secret.json and retries on concurrent-write (422) conflicts.

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

export async function fetchSecret(env, fetchImpl = fetch) {
  const url = `${ghUrl(env, "secret.json")}?ref=${env.REPO_BRANCH}`;
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
  const res = await fetchImpl(ghUrl(env, "secret.json"), {
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