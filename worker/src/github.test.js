import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchSecret, putSecret, mutateSecret, fetchFile, isPublicFile, SECRET_FILE } from "./github.js";

const env = {
  REPO_OWNER: "usermalik5",
  REPO_NAME: "GeloTech-Tool",
  REPO_BRANCH: "main",
  GITHUB_TOKEN: "REDACTED",
};

const SECRET = JSON.stringify(
  { users: { "a@b.c": { hash: "h1", permissions: ["basic"], blocked: false } } },
  null,
  2
);

function contentsResponse(content) {
  return {
    ok: true,
    status: 200,
    json: async () => ({ content: btoa(content), sha: "sha-123" }),
  };
}

function failResponse(status) {
  return { ok: false, status, json: async () => ({ message: `err ${status}` }) };
}

test("fetchSecret GETs contents API and decodes base64", async () => {
  const calls = [];
  const fakeFetch = async (url, opts) => {
    calls.push({ url, opts });
    return contentsResponse(SECRET);
  };
  const { data, sha } = await fetchSecret(env, fakeFetch);
  assert.equal(sha, "sha-123");
  assert.deepEqual(data, JSON.parse(SECRET));
  assert.ok(calls[0].url.includes("/contents/secret.json?ref=main"));
  assert.equal(calls[0].opts.headers.Authorization, "Bearer REDACTED");
});

test("fetchSecret propagates failure", async () => {
  await assert.rejects(() => fetchSecret(env, async () => failResponse(404)));
});

test("putSecret PUTs with base64 content, message and sha", async () => {
  let called = null;
  const fakeFetch = async (url, opts) => {
    called = { url, opts };
    return { ok: true, status: 200, json: async () => ({}) };
  };
  await putSecret(env, JSON.parse(SECRET), "sha-123", "test commit", fakeFetch);
  assert.equal(called.opts.method, "PUT");
  const payload = JSON.parse(called.opts.body);
  assert.equal(payload.message, "test commit");
  assert.equal(payload.sha, "sha-123");
  assert.equal(payload.branch, "main");
  assert.equal(atob(payload.content), SECRET);
});

test("mutateSecret retries on 422 then succeeds", async () => {
  let putCount = 0;
  const fakeFetch = async (url, opts) => {
    if (opts.method === "PUT") {
      putCount++;
      return putCount === 1 ? failResponse(422) : { ok: true, status: 200, json: async () => ({}) };
    }
    return contentsResponse(SECRET);
  };
  const result = await mutateSecret(env, (d) => d, "msg", fakeFetch);
  assert.deepEqual(result, { ok: true });
  assert.equal(putCount, 2);
});

test("mutateSecret gives up after repeated 422", async () => {
  const fakeFetch = async (url, opts) =>
    opts.method === "PUT" ? failResponse(422) : contentsResponse(SECRET);
  const result = await mutateSecret(env, (d) => d, "msg", fakeFetch);
  assert.equal(result.ok, false);
  assert.ok(result.error.includes("422"));
});

test("SECRET_FILE is fixed: writes can never target other paths", () => {
  assert.equal(SECRET_FILE, "secret.json");
});

test("fetchFile only accepts the public allowlist", async () => {
  assert.ok(isPublicFile("version.json"));
  assert.ok(isPublicFile("version.json.sig"));
  assert.ok(isPublicFile("gelotech_database_v3.json"));
  assert.ok(isPublicFile("banking_apps.json"));
  assert.ok(!isPublicFile("secret.json"));
  assert.ok(!isPublicFile("../secret.json"));
  assert.ok(!isPublicFile(""));
  await assert.rejects(() => fetchFile(env, "secret.json", async () => contentsResponse("x")));
});

test("fetchFile falls back to the blobs API for large files", async () => {
  const big = JSON.stringify({ packages: { "com.example": {} } });
  let blobCalled = false;
  const fakeFetch = async (url) => {
    if (url.includes("/git/blobs/")) {
      blobCalled = true;
      return { ok: true, status: 200, json: async () => ({ content: btoa(big), sha: "sha-blob" }) };
    }
    // contents API returns no content for >1MB files
    return { ok: true, status: 200, json: async () => ({ sha: "sha-meta" }) };
  };
  const bytes = await fetchFile(env, "gelotech_database_v3.json", fakeFetch);
  assert.equal(new TextDecoder().decode(bytes), big);
  assert.ok(blobCalled);
});