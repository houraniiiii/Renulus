# SPDX-License-Identifier: MIT
"""Genuine legacy admission survives an owned prelaunch process crash.

The child exits after the original public command commits, before a producer
launches. It creates no partial answer and performs no provider/native work.
"""
import json
import os
from pathlib import Path
import subprocess
import sys

if __name__ != "__main__":
    # The original-only child must not import SDK/model fixture modules.
    from test_harness_model_dispatch_sdk import offline


SOURCE = Path(__file__).resolve().parents[2]
PYTHON = Path("C:/Renulus/dev/python/Scripts/python.exe")
PROMPT = "Synthetic transplant learning: explain rejection and retain this unsent response."
REQUEST_ID = "synthetic-legacy-prelaunch-orphan"
CRASH_EXIT = 86
MAX_RECEIPT_BYTES = 16384


def _admit_then_crash(profile):
    def deny_external_work(event, arguments):
        if event in {"socket.connect", "socket.getaddrinfo", "subprocess.Popen",
                     "os.system", "os.posix_spawn"}:
            raise AssertionError("Legacy admission must not start external work")

    sys.addaudithook(deny_external_work)
    from renulus.learn.conversation_models import NewConversation, Send
    from renulus.server import create_app

    services = create_app(profile, source_root=SOURCE,
        collection_root=profile / "library" / "collection").state.services
    repo = services.get("conversations")
    chat = repo.create(NewConversation(title="Synthetic orphaned transplant discussion"))
    identifier = chat["identity"]["id"]
    request = Send(expected_revision=chat["revision"], text=PROMPT, request_id=REQUEST_ID)
    _, receipt = repo.streaming.begin("learning", identifier, request)
    status = repo.streaming.status("learning", identifier, receipt["run_id"], neutral=True)
    assert status == {"run_id": receipt["run_id"], "state": "running"}
    history = repo.messages("learning", identifier)
    assert [message["role"] for message in history["items"]] == ["user"]
    assert history["items"][0]["content"] == PROMPT
    provider = services.get("provider").status()
    assert provider["selected_provider"] is None
    assert provider["active_runs"] == provider["completed_requests"] == []
    record = {"pid": os.getpid(), "conversation": repo.get("learning", identifier),
        "request": request.model_dump(mode="json"), "receipt": receipt,
        "history": history, "draft": repo.draft("learning", identifier)}
    encoded = json.dumps(record, ensure_ascii=False).encode("utf-8")
    assert len(encoded) <= MAX_RECEIPT_BYTES
    sys.stdout.buffer.write(encoded + b"\n")
    sys.stdout.buffer.flush()
    # Deliberately bypass original lifespan/finalizers: this is process loss,
    # rather than a graceful close that could settle the running command.
    os._exit(CRASH_EXIT)


def _legacy_orphan(profile):
    assert PYTHON.is_file(), "The managed Python cohort is required"
    assert not profile.exists(), "The child must own a fresh synthetic profile"
    environment = {**os.environ, "PYTHONPATH": str(SOURCE / "runtime")}
    result = subprocess.run([str(PYTHON), str(Path(__file__).resolve()),
        "--legacy-orphan-child", str(profile)], cwd=SOURCE, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45, check=False)
    assert result.returncode == CRASH_EXIT, result.stderr.decode("utf-8", errors="replace")
    assert len(result.stdout) <= MAX_RECEIPT_BYTES + 1
    assert result.stderr == b"", result.stderr.decode("utf-8", errors="replace")
    record = json.loads(result.stdout)
    assert record["pid"] != os.getpid()
    return record


async def test_prelaunch_legacy_child_crash_migrates_original_without_reviving_terminal_receipt(tmp_path, offline):
    from renulus.learn.conversation_models import Send
    from renulus.server import create_app

    profile = tmp_path / "profile"
    original = _legacy_orphan(profile)
    # subprocess.run has joined the actual child before any canonical reopen.
    services = create_app(profile, source_root=SOURCE,
        collection_root=profile / "library" / "collection").state.services
    try:
        repo = services.get("conversations")
        identifier = original["conversation"]["identity"]["id"]
        run_id = original["receipt"]["run_id"]
        assert repo.streaming.status("learning", identifier, run_id, neutral=True) == {
            "run_id": run_id, "state": "interrupted"}
        assert repo.messages("learning", identifier) == original["history"]
        assert repo.draft("learning", identifier) == original["draft"]
        legacy = repo.learn.get_thread(identifier)
        assert len(legacy["runs"]) == 1
        assert legacy["runs"][0]["id"] == run_id
        assert legacy["runs"][0]["state"] == "interrupted"
        entry, receipt = repo.streaming.begin("learning", identifier, Send.model_validate(original["request"]))
        assert entry is None
        assert receipt["run_id"] == run_id and receipt["state"] == "interrupted"
        replay = [json.loads(encoded.split("data: ", 1)[1])
            async for encoded in repo.streaming.events(entry, receipt)]
        assert len(replay) == 1 and replay[0]["type"] == "error"
        assert replay[0]["payload"]["replayed"] is True
        assert replay[0]["payload"]["state"] == "interrupted"
        assert services.get("provider").status()["completed_requests"] == []
    finally:
        await services.finish_shutdown()

    from test_harness_learning_models import command, learning_models

    async with learning_models(tmp_path) as (services, owner, authority, registries, transports,
            admissions, counter, observer):
        repo = services.get("conversations")
        status = {"run_id": run_id, "state": "interrupted"}
        assert repo.streaming.status("learning", identifier, run_id, neutral=True) == status
        result = await owner.migrate_saved(identifier,
            expected_revision=original["conversation"]["revision"])
        assert result.state == "active" and result.retirement == "retired"
        assert result.mapping.conversation.id == identifier
        assert len(result.message_refs) == 1
        reference = result.message_refs[0]
        user = original["history"]["items"][0]
        assert reference.legacy_id == user["id"] and reference.run_id == run_id
        assert reference.role == "user" and reference.ordinal == 0
        assert reference.lineage == "unknown"
        assert reference.context_eligible is False and reference.capture_eligible is False
        assert await owner.bridge.messages(identifier) == original["history"]
        assert repo.messages("learning", identifier) == original["history"]
        assert repo.draft("learning", identifier) == original["draft"]
        native = await command(owner.process, "session.messages",
            {"session_id": result.mapping.runtime.session_id, "limit": 20})
        assert len(native["messages"]) == 1
        imported = native["messages"][0]
        assert imported["id"] == reference.native_id and imported["type"] == "user"
        assert imported["text"] == user["content"]
        assert (await command(owner.process, "session.get",
            {"session_id": result.mapping.runtime.session_id}))["execution"] == "settled"
        assert repo.streaming.status("learning", identifier, run_id, neutral=True) == status
        assert repo.learn.get_thread(identifier)["runs"][0]["state"] == "interrupted"
        assert owner.bridge.completed(run_id) is None
        entry, receipt = repo.streaming.begin("learning", identifier, Send.model_validate(original["request"]))
        assert entry is None and receipt["run_id"] == run_id
        assert receipt["state"] == "interrupted"
        replay = [json.loads(encoded.split("data: ", 1)[1])
            async for encoded in repo.streaming.events(entry, receipt)]
        assert len(replay) == 1 and replay[0]["type"] == "error"
        assert replay[0]["payload"]["replayed"] is True
        assert replay[0]["payload"]["state"] == "interrupted"
        assert counter.calls == observer.calls == transports == admissions == []
        assert all(registry.requests == [] and registry.publications == [] for registry in registries)
        assert registries[-1].status().owned == 0
        assert owner.process.domain_status()["active"] == 0


if __name__ == "__main__":
    assert len(sys.argv) == 3 and sys.argv[1] == "--legacy-orphan-child"
    _admit_then_crash(Path(sys.argv[2]).resolve())
