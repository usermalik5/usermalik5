"""Bump the version.json update manifest, sign it, and push to GitHub.

Usage:
    python bump_version.py             # bump database and banking
    python bump_version.py db          # bump database only
    python bump_version.py banking     # bump banking apps list only
    python bump_version.py db 5        # set database to 5
    python bump_version.py sign        # re-hash + re-sign without bumping
    python bump_version.py --no-commit # write files but do NOT commit/push

Every release is SHA-256-hashed and signed with the Ed25519 private key the
app's embedded public key (tech_common.py::UPDATE_SIGN_PUBLIC_KEY) verifies.
The signature lives in version.json.sig (base64), signed over the exact bytes
of version.json, and the data file hashes are inside version.json.

NOTE: the "settings" version counter was removed: secret.json is no longer
distributed (login accounts are fetched and signature-verified fresh on every
login; runtime state stays on the local disk). secret.json is still hashed in
the manifest so the login fetch verifies it.

The private key is loaded from the GELOTECH_SIGN_KEY environment variable,
or defaults to %USERPROFILE%\\.gelotech_signing\\update_ed25519.pem (never
committed to the repo).
"""

import base64
import hashlib
import json
import os
import subprocess
import sys
import time

DATA_FILES = ("gelotech_database_v3.json", "secret.json", "banking_apps.json")


def load():
    with open("version.json", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with open("version.json", "w", encoding="utf-8", newline="") as f:
        json.dump(data, f, indent=2)


def file_sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def load_signing_key():
    path = os.environ.get("GELOTECH_SIGN_KEY") or os.path.join(
        os.path.expanduser("~"), ".gelotech_signing", "update_ed25519.pem")
    if not os.path.isfile(path):
        print(f"ERROR: signing key not found at {path}")
        print("Generate it once with:")
        print("  python -c \"from cryptography.hazmat.primitives.asymmetric import ed25519; "
              "from cryptography.hazmat.primitives import serialization; "
              "import os; k = ed25519.Ed25519PrivateKey.generate(); "
              "os.makedirs(os.path.dirname(r'%s'), exist_ok=True); "
              "open(r'%s', 'wb').write(k.private_bytes(serialization.Encoding.PEM, "
              "serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))\"" % (path, path))
        sys.exit(1)
    from cryptography.hazmat.primitives import serialization
    with open(path, "rb") as f:
        key = serialization.load_pem_private_key(f.read(), password=None)
    return key


def sign_manifest(data):
    """Write version.json (with data-file sha256 hashes), sign its exact bytes,
    and write version.json.sig. Returns the sha256 of version.json."""
    data["sha256"] = {f: file_sha256(f) for f in DATA_FILES}
    text = json.dumps(data, indent=2)
    with open("version.json", "w", encoding="utf-8", newline="") as f:
        f.write(text)
    sig = load_signing_key().sign(text.encode("utf-8"))
    with open("version.json.sig", "w", encoding="utf-8", newline="") as f:
        f.write(base64.b64encode(sig).decode("ascii"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True)


def main():
    args = sys.argv[1:]
    no_commit = "--no-commit" in args
    args = [a for a in args if a != "--no-commit"]
    data = load()

    def bump(key):
        if args and args[-1].isdigit() and len(args) >= 2:
            data[key] = int(args[-1])
        else:
            data[key] = data.get(key, 0) + 1

    if not args:
        bump("database")
        bump("banking")
    elif args[0] == "db":
        bump("database")
    elif args[0] == "banking":
        bump("banking")
    elif args[0] == "sign":
        pass
    else:
        print("Unknown target:", args[0])
        print(__doc__)
        sys.exit(1)

    manifest_hash = sign_manifest(data)
    print(f"version.json -> {json.dumps(data)}")
    print(f"version.json.sig written (manifest sha256 {manifest_hash[:16]}...)")

    if no_commit:
        print("--no-commit: files written locally, not committed or pushed.")
        return

    run(["git", "add", "version.json", "version.json.sig"])
    run(["git", "commit", "-m",
         f"Bump update versions (database={data.get('database')}, "
         f"banking={data.get('banking')}) - signed release"])
    run(["git", "push", "origin", "main"])
    print("Pushed to origin/main.")


if __name__ == "__main__":
    main()
