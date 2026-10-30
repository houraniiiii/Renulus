from threading import Event
import threading

from renulus.worker_contracts import Capacity, COMMAND
from renulus.workers.runtime import Worker
from renulus.workers.derived import UnsettledEngine
from .support import REVISIONS, command, config, output, target


class BlockingEngines:
    def __init__(self):
        self.entered, self.finish = Event(), Event()
        self.calls = 0

    def embed(self, texts, *, query):
        self.calls += 1
        self.entered.set()
        assert self.finish.wait(timeout=10)
        return {"vectors":[[0.0] * 384]}


def invoke(worker, value):
    worker.handle(COMMAND.validate_python(value), value["input"])


def test_cancel_ack_is_not_settlement_and_control_survives_full_data_capacity():
    replies = []
    engine = BlockingEngines()
    capacity = Capacity(data_in_flight=1, data_queued=1)
    worker = Worker(config(capacity=capacity), capacity, lambda r: replies.append(r.model_dump()), engines=engine)
    try:
        first = command("embedding.embed", {"texts":["synthetic transplant"],"query":False,"output":output()})
        invoke(worker, first)
        pending = replies[-1]
        assert pending["outcome"] == "accepted_pending"
        assert engine.entered.wait(timeout=2)
        second = command("embedding.embed", {"texts":["synthetic AKI"],"query":False,"output":output()})
        invoke(worker, second)
        queued = replies[-1]
        third = command("embedding.embed", {"texts":["synthetic CKD"],"query":False,"output":output()})
        invoke(worker, third)
        assert replies[-1]["result"]["code"] == "overloaded"
        invoke(worker, command("worker.settle", {"action":"cancel","target":target(pending)}))
        assert replies[-1]["settlement"]["state"] == "pending"
        assert worker.artifacts.used > 0
        assert not worker.jobs[first["request_id"]].settled
        invoke(worker, command("worker.settle", {"action":"query"}))
        assert replies[-1]["settlement"]["state"] == "pending"
        assert replies[-1]["result"]["active"] == 2
        # Queue cancellation actually settles immediately, without calling engine.
        invoke(worker, command("worker.settle", {"action":"cancel","target":target(queued)}))
        assert second["request_id"] not in worker.jobs
        assert engine.calls == 1
        invoke(worker, command("worker.settle", {"action":"query","target":target(pending)}))
        assert replies[-1]["settlement"]["state"] == "pending"
        # A lease with the wrong digest/generation can never cancel another job.
        wrong = target(pending)
        wrong["request_sha256"] = "0" * 64
        invoke(worker, command("worker.settle", {"action":"cancel","target":wrong}))
        assert replies[-1]["result"]["code"] == "stale_target"
    finally:
        engine.finish.set()
        worker.disconnect()
    terminals = [r for r in replies if r["identity"]["request_id"] == first["request_id"]]
    assert [r["outcome"] for r in terminals] == ["accepted_pending", "cancelled_settled"]
    assert worker.artifacts.used == 0
    assert worker.jobs == {}
    assert worker.completed[first["request_id"]][0].request_id == first["request_id"]


def test_revocation_while_running_retains_lease_and_fences_late_output():
    replies = []
    engine = BlockingEngines()
    worker = Worker(config(), Capacity(), lambda r: replies.append(r.model_dump()), engines=engine)
    first = command("embedding.embed", {"texts":["temporary private synthetic sentinel"],"query":False,"output":output()})
    try:
        invoke(worker, first)
        pending = replies[-1]
        assert engine.entered.wait(timeout=2)
        revisions = REVISIONS.model_copy(update={"grant":13, "deletion":7})
        invoke(worker, command("worker.settle", {"action":"revoke","revisions":revisions.model_dump()}))
        assert replies[-1]["settlement"]["state"] == "pending"
        # Output reservation still belongs to the actual running task.
        assert worker.artifacts.used > 0
        engine.finish.set()
        worker.pool.shutdown(wait=True)
        terminal = [r for r in replies if r["identity"]["request_id"] == first["request_id"]][-1]
        assert terminal["outcome"] == "cancelled_settled"
        assert terminal["revisions"] == REVISIONS.model_dump()
        assert terminal["settlement"]["worker_lease"] == pending["settlement"]["worker_lease"]
        assert worker.artifacts.used == 0
        # Completion query binds the exact old lease, but uses current authority.
        invoke(worker, command("worker.settle", {"action":"query","target":target(pending)}, revisions=revisions))
        assert replies[-1]["settlement"]["state"] == "settled"
        assert replies[-1]["settlement"]["worker_lease"] == pending["settlement"]["worker_lease"]
    finally:
        engine.finish.set()
        worker.disconnect()


def test_memory_lane_keeps_one_thread_through_cancel_and_allows_other_lanes():
    replies, threads = [], []
    entered, finish, second_done, embedding_done = Event(), Event(), Event(), Event()

    class Derived:
        def execute(self, command, body, current, capture):
            threads.append(threading.get_ident())
            if len(threads) == 1:
                entered.set()
                assert finish.wait(5)
            return {"tag": "memory_candidates", "rows": []}

    class Engines:
        def embed(self, texts, *, query):
            embedding_done.set()
            return {"vectors": [[0.0] * 384]}

    def emit(reply):
        value = reply.model_dump()
        replies.append(value)
        if value["identity"]["request_id"] == second["request_id"] and value["settlement"]["state"] == "settled":
            second_done.set()

    first = command("memory.recall", dict(query="AKI", accepted=[], limit=1, output=output()))
    second = command("memory.recall", dict(query="CKD", accepted=[], limit=1, output=output()))
    worker = Worker(config(), Capacity(), emit, engines=Engines())
    worker.derived = Derived()
    try:
        invoke(worker, first)
        pending = replies[0]
        assert entered.wait(2)
        invoke(worker, second)
        invoke(worker, command("worker.settle", dict(action="cancel", target=target(pending))))
        assert replies[-1]["settlement"]["state"] == "pending"
        assert len(threads) == 1
        invoke(worker, command("embedding.embed", dict(texts=["transplant"], query=False, output=output())))
        assert embedding_done.wait(2)
        finish.set()
        assert second_done.wait(5)
        assert len(threads) == 2 and threads[0] == threads[1]
        terminals = [r for r in replies if r["identity"]["request_id"] == first["request_id"]]
        assert terminals[-1]["outcome"] == "cancelled_settled"
    finally:
        finish.set()
        worker.disconnect()


def test_uncertain_native_constructor_cannot_acknowledge_settlement_on_cancel():
    replies, entered = [], Event()

    class Derived:
        def execute(self, *args):
            entered.set()
            raise UnsettledEngine()

    worker = Worker(config(), Capacity(), lambda r: replies.append(r.model_dump()))
    worker.derived = Derived()
    first = command("memory.recall", dict(query="AKI", accepted=[], limit=1, output=output()))
    invoke(worker, first)
    pending = replies[0]
    try:
        assert entered.wait(2)
        invoke(worker, command("worker.settle", dict(action="cancel", target=target(pending))))
        assert replies[-1]["settlement"]["state"] == "pending"
        assert first["request_id"] in worker.jobs
    finally:
        worker.disconnect()
    terminal = [r for r in replies if r["identity"]["request_id"] == first["request_id"]][-1]
    assert terminal["outcome"] == "uncertain_after_disconnect"
    assert terminal["settlement"]["state"] == "uncertain"
