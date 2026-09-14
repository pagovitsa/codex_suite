"""Small, stdlib-only command line client. The broker provides the HTTP API."""
import argparse
import getpass
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "Redirect refused", headers, fp)


def request(path, payload=None, key="internal", stream=False):
    directory = Path(os.environ.get("SUITE_SECRETS", Path(__file__).parent / "secrets"))
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = "Bearer " + (directory / (key + ".key")).read_text().strip()
    url = os.environ.get("BROKER_URL", "http://127.0.0.1:3400").rstrip("/") + path
    data = None if payload is None else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.build_opener(NoRedirect).open(req, timeout=1800) as response:
        if stream:
            for line in response:
                print(line.decode("utf-8").rstrip("\r\n"), flush=True)
            return None
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "login", "api-key", "status", "models"):
        commands.add_parser(name)
    chat = commands.add_parser("chat")
    chat.add_argument("prompt")
    chat.add_argument("--model", required=True, help="Use a model id returned by models")
    chat.add_argument("--agent", action="store_true", help="Permit edits in the mounted project")
    chat.add_argument("--stream", action="store_true")
    task = commands.add_parser("task")
    task.add_argument("prompt")
    task.add_argument("--thread", help="Continue this thread instead of creating one")
    task.add_argument("--model")
    for name in ("turn", "events", "interrupt"):
        command = commands.add_parser(name)
        command.add_argument("thread")
        command.add_argument("turn")
    args = parser.parse_args()
    owner = "/v1/owners/local"
    result = None
    if args.command == "check":
        result = request("/readyz", key=None)
        for path, key in (("/v1/models", None), ("/v1/models", "internal"),
                          ("/openapi.json", "chat")):
            try:
                request(path, key=key)
            except urllib.error.HTTPError as error:
                if error.code != 401:
                    raise
            else:
                raise RuntimeError("Authentication boundary failed: " + path)
        request("/openapi.json")
        print("HTTP readiness and authentication boundaries passed. No model request sent.")
    elif args.command == "login":
        result = request(owner + "/auth/device/start", {})
        deadline = time.monotonic() + 30
        while not result.get("loginUrl") and result.get("state") not in ("failed", "authenticated", "completed"):
            if time.monotonic() >= deadline:
                break
            time.sleep(1)
            status = request(owner + "/auth/status")
            result = status.get("deviceAuth") or status
        print("Open loginUrl and enter userCode in your browser, then run status.")
    elif args.command == "api-key":
        api_key = getpass.getpass("OpenAI API key (hidden): ")
        if not api_key.strip():
            raise ValueError("API key cannot be empty")
        result = request(owner + "/auth/api-key", {"apiKey": api_key})
    elif args.command == "status":
        result = request(owner + "/auth/status")
    elif args.command == "models":
        result = request("/v1/models", key="chat")
    elif args.command == "chat":
        result = request("/v1/responses", {"model": args.model, "input": args.prompt,
                         "stream": args.stream}, key="agent" if args.agent else "chat", stream=args.stream)
    elif args.command == "task":
        thread = args.thread or "task-" + uuid.uuid4().hex
        path = owner + "/threads/" + urllib.parse.quote(thread, safe="")
        if not args.thread:
            request(owner + "/threads", {"threadId": thread, "profile": "default",
                    "configProfile": "agent", "cwd": "/workspaces/project", "hostApp": "codex-suite"})
        payload = {"input": [{"type": "text", "text": args.prompt}], "mode": "queue"}
        if args.model:
            payload["codexOptions"] = {"model": args.model}
        result = request(path + "/turns", payload)
    else:
        path = owner + "/threads/" + urllib.parse.quote(args.thread, safe="")
        turn = urllib.parse.quote(args.turn, safe="")
        if args.command == "events":
            result = request(path + "/events?" + urllib.parse.urlencode({"turnId": args.turn, "after": 0}), stream=True)
        elif args.command == "interrupt":
            result = request(path + "/turns/" + turn + "/interrupt", {})
        else:
            result = request(path + "/turns/" + turn)
    if result is not None:
        print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as error:
        # Avoid printing request headers, credentials or raw upstream error bodies.
        print(f"Request failed: {error}", file=sys.stderr)
        sys.exit(1)
