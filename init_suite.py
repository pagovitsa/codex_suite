"""Generate independent API keys once; keep existing credentials on reruns."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import sys


def initialize(directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    directory.chmod(0o700)
    owner = directory.stat()
    keys = {}
    for name in ("internal", "chat", "agent"):
        path = directory / (name + ".key")
        if not path.exists():
            with path.open("x", encoding="utf-8") as output:
                output.write(secrets.token_urlsafe(48) + "\n")
        keys[name] = path.read_text(encoding="utf-8").strip()
        if len(keys[name]) < 32 or any(c.isspace() for c in keys[name]):
            raise ValueError(f"Invalid existing key in {path}; refusing to replace it.")
        path.chmod(0o444)
        if os.name == "posix" and os.geteuid() == 0:
            os.chown(path, owner.st_uid, owner.st_gid)
    if len(set(keys.values())) != 3:
        raise ValueError("The internal, chat and agent keys must be different.")
    bindings = {
        "sha256:" + hashlib.sha256(keys[name].encode()).hexdigest(): {
            "ownerId": "local",
            "profile": "default",
            "configProfile": profile,
            "hostApp": "codex-suite",
            "cwd": "/workspaces/project",
        }
        for name, profile in (("chat", "default"), ("agent", "agent"))
    }
    path = directory / "bindings.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != bindings:
            raise ValueError("Existing bindings differ from the generated keys; review them manually.")
    else:
        with path.open("x", encoding="utf-8") as output:
            json.dump(bindings, output, indent=2)
            output.write("\n")
    path.chmod(0o444)
    if os.name == "posix" and os.geteuid() == 0:
        os.chown(path, owner.st_uid, owner.st_gid)
    print("Keys and bindings are ready. Existing keys were preserved; no keys printed.")


if __name__ == "__main__":
    initialize(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent / "secrets")
