"""Updates tests use real content/updates APIs and migrations, isolated from engines."""
import pytest


@pytest.fixture(autouse=True)
def updates_modules(monkeypatch):
    # Full-app integration belongs to the integrator. No knowledge engines,
    # native helpers, patient collections or provider calls are started here.
    monkeypatch.setattr("renulus.server.MODULE_ORDER", ("content", "updates"))
