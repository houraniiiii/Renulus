"""Inert JSONL peer for transport tests only; never an OpenCode substitute."""
import json
import os
from pathlib import Path
import sys
import threading
import time


boot = json.loads(os.environ["RENULUS_HARNESS_BOOT"])
identity = {key: boot[key] for key in
            ("protocol", "profile_id", "store_id", "generation", "token")}
output_lock = threading.Lock()
received = {}
held = []
closing = False


def finish_close(request):
    time.sleep(boot.get("test", {}).get("close_delay", 0))
    for pending in held:
        reply(pending, {"cancelled": True}, "cancelled_settled")
    held.clear()
    reply(request, {"state": "closed"}, "cancelled_settled")
    os._exit(0)


def emit(frame):
    with output_lock:
        sys.stdout.buffer.write(json.dumps(frame).encode("utf-8") + b"\n")
        sys.stdout.buffer.flush()


def reply(request, result=None, outcome="committed_reference"):
    emit({**identity, **{key: request[key] for key in
          ("operation_id", "attempt_id", "request_id")},
          "kind": "reply", "outcome": outcome, "result": result})


# A faulty test cannot strand this synthetic child indefinitely.
watchdog = threading.Timer(15, lambda: os._exit(98))
watchdog.daemon = True
watchdog.start()
def ready():
    emit({**identity, "kind": "ready", "state": boot.get("test", {}).get("ready_state", "ready")})


if delay := boot.get("test", {}).get("ready_delay", 0):
    emit({**identity, "generation": "old", "kind": "ready", "state": "ready"})
    if boot.get("test", {}).get("malformed_ready"):
        emit({**identity, "kind": "ready"})
    threading.Timer(delay, ready).start()
else:
    ready()
time.sleep(boot.get("test", {}).get("read_delay", 0))
for line in sys.stdin.buffer:
    request = json.loads(line)
    command = request["command"]
    received[command] = received.get(command, 0) + 1
    if request["payload"].get("exit"):
        os._exit(23)
    if malformed := request["payload"].get("bad_frame"):
        frames = {"oversized": b"x" * 8192 + b"\n", "utf8": b"\xff\n",
                  "json": b"{broken}\n", "truncated": json.dumps({**identity,
                  **{key: request[key] for key in ("operation_id", "attempt_id", "request_id")},
                  "kind": "reply", "outcome": "committed_reference", "result": {}}).encode()}
        frames["nan"] = json.dumps({**identity,
            **{key: request[key] for key in ("operation_id", "attempt_id", "request_id")},
            "kind": "reply", "outcome": "committed_reference", "result": {"value": float("nan")}}).encode() + b"\n"
        frames["surrogate"] = frames["nan"].replace(b"NaN", b'"\\ud800"')
        frames["overflow"] = frames["nan"].replace(b"NaN", b"1e309")
        sys.stdout.buffer.write(frames[malformed])
        sys.stdout.buffer.flush()
        os._exit(0)
    if request["command"] == "host.close":
        if not closing:
            closing = True
            threading.Thread(target=finish_close, args=(request,), daemon=True).start()
        continue
    if command == "host.status":
        reply(request, {"received": received})
        continue
    if command == "session.cancel":
        for pending in held:
            reply(pending, {"cancelled": True}, "cancelled_settled")
        held.clear()
        reply(request, {"settled": True}, "cancelled_settled")
        continue
    if request["payload"].get("hold"):
        if request["payload"].get("acknowledge"):
            reply(request, {"state": "running"}, "accepted_pending")
        held.append(request)
        continue
    if request["payload"].get("environment"):
        import ctypes
        reply(request, {"names": sorted(os.environ),
              "paths": {key: os.environ.get(key) for key in
                        ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA", "XDG_CONFIG_HOME",
                         "XDG_DATA_HOME", "XDG_CACHE_HOME", "XDG_STATE_HOME", "XDG_RUNTIME_DIR",
                         "TEMP", "TMP")},
              "path": os.environ["PATH"], "root": boot["root"], "cwd": os.getcwd(),
              "explicit_setting": boot.get("test", {}).get("explicit_setting"),
              "console": bool(ctypes.windll.kernel32.GetConsoleWindow()) if os.name == "nt" else False})
        continue
    if request["payload"].get("prepared_manifest"):
        manifest = json.loads((Path(boot["root"]) / "state/harness/manifest.json").read_bytes())
        reply(request, {"manifest": manifest, "domain_store_id": boot["domain_store_id"],
                        "domain_path": boot["domain_path"]})
        continue
    if request["payload"].get("compact_numbers"):
        frame = {**identity,
                 **{key: request[key] for key in ("operation_id", "attempt_id", "request_id")},
                 "kind": "reply", "outcome": "committed_reference", "result": {"values": []}}
        encoded = json.dumps(frame, separators=(",", ":")).encode().replace(
            b"[]", b"[" + b",".join([b"1e15"] * 100) + b"]")
        sys.stdout.buffer.write(encoded + b"\n")
        sys.stdout.buffer.flush()
        continue
    result = {"command": command, "payload": request["payload"]}
    if variant := request["payload"].get("valid_reply_variant"):
        response = {**identity, **{key: request[key] for key in
                    ("operation_id", "attempt_id", "request_id")}, "kind": "reply"}
        if variant == "bodyless_ack":
            emit({**response, "outcome": "accepted_pending"})
        elif variant == "nullable_error":
            emit({**response, "outcome": "committed_reference", "result": result, "error": None})
            continue
    if request["payload"].get("empty_error_code"):
        emit({**identity, **{key: request[key] for key in
              ("operation_id", "attempt_id", "request_id")},
              "kind": "reply", "outcome": "cancelled_settled", "error": {"code": ""}})
    if request["payload"].get("poison_replies"):
        poisoned = {**identity, **{key: request[key] for key in
                    ("operation_id", "attempt_id", "request_id")},
                    "kind": "reply", "outcome": "committed_reference",
                    "result": {"poisoned": True}}
        for key in (*identity, "operation_id", "attempt_id", "request_id"):
            emit({**poisoned, key: "stale-or-foreign"})
        emit({**poisoned, "outcome": "made_up_success"})
        emit({**poisoned, "request_id": []})
        emit({**poisoned, "error": "unstructured"})
    delay = request["payload"].get("delay", 0)
    if delay:
        threading.Timer(delay, reply, (request, result)).start()
    else:
        reply(request, result)
        if request["payload"].get("duplicate_reply"):
            reply(request, {"state": "running"}, "accepted_pending")
            reply(request, {"incorrect_duplicate": True})
