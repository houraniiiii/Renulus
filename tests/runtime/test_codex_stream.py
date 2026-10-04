import json
import time

import httpx
import pytest

from renulus.contracts import ContextScope, Scope
from renulus.runtime.manager import ProviderManager


@pytest.mark.asyncio
async def test_codex_real_sdk_stream_and_background_use_same_exact_route(app_paths):
    requests = []
    def serve(request):
        requests.append(request)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "gpt-6-luna"}, {"id": "gpt-6.1-sol"}]})
        assert str(request.url) == "https://api.openai.com/v1/responses"
        body = json.loads(request.content)
        assert body["model"] == "gpt-6.1-sol"
        assert body["store"] is False and body["stream"] is True
        assert "tools" not in body and "context_management" not in body
        events = [{"type": "response.output_text.delta", "delta": "Synthetic dialysis learning principle",
                   "item_id": "synthetic-message", "output_index": 0, "content_index": 0, "sequence_number": 1},
                  {"type": "response.completed", "sequence_number": 2,
                   "response": {"id": "synthetic-response", "object": "response", "created_at": 1,
                                "status": "completed", "model": "gpt-6.1-sol", "output": []}}]
        stream = "".join("data: " + json.dumps(event) + "\n\n" for event in events)
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=stream)
    manager = ProviderManager(app_paths, http_transport=httpx.MockTransport(serve))
    # Synthetic app-owned OAuth record, never an imported application credential.
    manager._settings["connections"]["codex"] = {"client_id": "synthetic-client",
        "access_token": "synthetic-plan-token", "expires_at": time.time() + 600}
    manager._settings["selected_provider"] = "codex"
    await manager.refresh("codex")
    for purpose in ("explain", "memory", "compaction"):
        output = [part async for part in manager.stream(
            [{"role": "user", "content": "Synthetic generic educational evidence"}],
            scope=ContextScope(kind=Scope.STUDY), run_id=purpose,
            system="Keep the renal physiology explanation concise.", purpose=purpose)]
        assert output == ["Synthetic dialysis learning principle"]
    assert len(requests) == 4  # one catalog, three explicitly requested operations
    assert not manager.status()["active_runs"]
    assert not (app_paths.state / "hermes").exists()
    assert "renal physiology" in json.dumps(json.loads(requests[1].content))
