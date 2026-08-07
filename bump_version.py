"""Bump the version.json update manifest and push to GitHub.

Usage:
    python bump_version.py            # bump database, settings, and banking
    python bump_version.py db         # bump database only
    python bump_version.py settings   # bump settings only
    python bump_version.py banking    # bump banking apps list only
    python bump_version.py db 5       # set database to 5

Bumps the numbers, commits version.json, and pushes to origin/main.
"""

import json
import subprocess
import sys


def load():
    with open("version.json", encoding="utf-8") as f:
        return json.load(f)


def save(data):
    with open("version.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def run(args):
    return subprocess.run(args, capture_output=True, text=True, check=True)


def main():
    args = sys.argv[1:]
    data = load()

    def bump(key):
        if args and args[-1].isdigit() and len(args) >= 2:
            data[key] = int(args[-1])
        else:
            data[key] = data.get(key, 0) + 1

    if not args:
        bump("database")
        bump("settings")
        bump("banking")
    elif args[0] == "db":
        bump("database")
    elif args[0] == "settings":
        bump("settings")
    elif args[0] == "banking":
        bump("banking")
    else:
        print("Unknown target:", args[0])
        print(__doc__)
        sys.exit(1)

    save(data)
    print(f"version.json -> {json.dumps(data)}")

    run(["git", "add", "version.json"])
    run(["git", "commit", "-m",
         f"Bump update versions (database={data.get('database')}, "
         f"settings={data.get('settings')})"])
    run(["git", "push", "origin", "main"])
    print("Pushed to origin/main.")


if __name__ == "__main__":
    main()
