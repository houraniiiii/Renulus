"""Updates tests use real content/updates APIs and migrations, isolated from engines."""
import pytest


@pytest.fixture(autouse=True)
def updates_modules(monkeypatch):
    # Full-app integration belongs to the integrator. No knowledge engines,
    # native helpers, patient collections or provider calls are started here.
    # Design C requires Learn/Cases for conversations and Assessment migrations
    # for startup and request-time attempt reconciliation.
    monkeypatch.setattr("renulus.server.MODULE_ORDER",
                        ("content", "updates", "learn", "cases", "assessment"))
