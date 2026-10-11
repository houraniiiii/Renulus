"""Synthetic reverse-callback peer; owns only its explicit subprocess pipes."""
import json
import os
import sys
import time

boot = json.loads(os.environ["RENULUS_HARNESS_BOOT"])
identity = {key: boot[key] for key in
            ("protocol", "profile_id", "store_id", "generation", "token")}
pending = {}
domain_results = []


def emit(frame):
    print(json.dumps(frame, allow_nan=False), flush=True)


def reply(request, result, outcome="committed_reference"):
    emit({**identity, **{key: request[key] for key in
          ("request_id", "operation_id", "attempt_id")},
          "kind": "reply", "outcome": outcome, "result": result})


emit({**identity, "kind": "ready", "state": "ready"})
for line in sys.stdin:
    frame = json.loads(line)
    if frame["kind"] == "domain_result":
        domain_results.append({key: value for key, value in frame.items() if key != "token"})
        if request := pending.pop(frame["callback_id"], None):
            reply(request, {"domain": {key: value for key, value in frame.items()
                                       if key != "token"}})
        continue
    if frame["command"] == "session.get":
        callback = {**identity, "kind": "domain_request",
                    "callback_id": frame["payload"].get("callback_id", "callback-1"),
                    "operation_id": "learning-1", "attempt_id": "attempt-1",
                    "session_id": "native-session", "input_id": "native-input",
                    "cancellation_id": "parent-cancel-1",
                    "command": "synthetic.extract", "payload": {"topic": "CKD"}}
        if not frame["payload"].get("emit_only"):
            pending[callback["callback_id"]] = frame
        for overrides in frame["payload"].get("callbacks", [{}]):
            emit({**callback, **overrides})
        time.sleep(boot.get("test", {}).get("read_pause", 0))
        if frame["payload"].get("emit_only"):
            reply(frame, {"emitted": True})
    elif frame["command"] == "host.status":
        reply(frame, {"domain_results": domain_results})
    elif frame["command"] == "host.close":
        reply(frame, {"state": "closed"}, "cancelled_settled")
        break
    else:
        reply(frame, {"text": "Synthetic extraction result."})
