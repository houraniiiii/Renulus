"""Public saved observation lifetime; frame accounting is explicitly synthetic."""
from renulus.contracts import ApiError
from renulus.learn.conversation_models import NewConversation, Send
from renulus.learn.harness_bridge import HarnessLearningBridge
from renulus.server import create_app
from tests.learn.test_harness_bridge import ScriptedTransport, active_shape, collect


class ReadBoundedTransport(ScriptedTransport):
    def __init__(self):
        super().__init__()
        self.retained_reads = set()
        self.released = []

    async def request(self, command, *args):
        read = command in {"session.get", "session.messages"}
        if read and len(self.retained_reads) >= 2:
            raise ApiError("synthetic_observation_capacity", "Terminal reads exhausted the synthetic frame cap.", 409)
        result = await super().request(command, *args)
        if read:
            self.retained_reads.add(result["request_id"])
        return result

    async def release_observation(self, request_id):
        assert request_id in self.retained_reads  # No write receipt may reach this port.
        self.retained_reads.remove(request_id)
        self.released.append(request_id)
        return True


async def test_saved_answer_and_reopened_history_retire_observed_reads_only(tmp_path):
    services = create_app(tmp_path / "synthetic-observation-profile").state.services
    repo = services.get("conversations")
    transport = ReadBoundedTransport()
    bridge = HarnessLearningBridge(repo, transport, active_manifest=active_shape,
        configuration_id="synthetic-observation-configuration")
    services.registry["learning_harness"] = bridge
    chat = repo.create(NewConversation())
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"],
        Send(expected_revision=chat["revision"], text="Explain synthetic glomerular disease.",
            request_id="synthetic-observation-request"))
    try:
        events = await collect(repo.streaming, entry, receipt)
        assert events[-1]["type"] == "completed", events
        for _ in range(8):
            history = await bridge.messages(chat["identity"]["id"])
            assert history["items"][-1]["content"] == transport.answer_text
        assert len(transport.released) > 2 and not transport.retained_reads
        assert transport.calls.count("session.create") == transport.calls.count("session.prompt") == 1
    finally:
        await repo.streaming.close()
        services.get("helpers").startup.close()
