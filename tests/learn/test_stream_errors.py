import pytest

from renulus.contracts import ApiError, ContextScope, Scope
from renulus.server import create_app


@pytest.mark.asyncio
@pytest.mark.parametrize("error,code,retryable", [
    (ApiError("model_not_allowed", "Choose an approved model", 400, False), "model_not_allowed", False),
    (ApiError("provider_unavailable", "Provider unavailable", 503, True), "provider_unavailable", True),
    (RuntimeError("PRIVATE_SYNTHETIC_EXCEPTION"), "explain_failed", True),
])
async def test_stream_preserves_public_retryability_and_redacts_unknown_failures(tmp_path, error, code, retryable):
    app = create_app(tmp_path)
    services = app.state.services
    services.registry["knowledge"] = None

    class ControlledProvider:
        async def stream(self, messages, **kwargs):
            raise error
            yield

    services.registry["provider"] = ControlledProvider()
    learn = services.registry["learn"]
    _, run = learn.prepare("Synthetic temporary learning", ContextScope(kind=Scope.TEMPORARY_CASE),
                           None, None, "direct", None)
    events = [event async for event in learn.answer(run, "Synthetic temporary learning", "direct", None)]
    assert events[-1].type == "error"
    payload = events[-1].payload
    assert payload["code"] == code and payload["retryable"] is retryable
    assert "PRIVATE_SYNTHETIC_EXCEPTION" not in payload["message"]
    assert learn.active == {}
    assert services.db.fetch_all("SELECT * FROM learn_threads") == []
