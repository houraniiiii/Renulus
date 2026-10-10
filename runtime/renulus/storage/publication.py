# SPDX-License-Identifier: MIT
"""Request-bound publication guards also follow explicitly detached tasks."""
from contextlib import contextmanager
from contextvars import ContextVar

_guard = ContextVar('renulus_publication_guard', default=None)


@contextmanager
def bind_publication_guard(database, callback):
    token = _guard.set((database, callback))
    try:
        yield
    finally:
        _guard.reset(token)


def check_publication(database, connection):
    current = _guard.get()
    if current is not None and current[0] is database:
        current[1](connection)
