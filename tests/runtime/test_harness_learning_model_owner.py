"""Public saved-owner model pins; native observation is explicitly synthetic."""
from pathlib import Path

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_domain import DomainBinding, DomainRequest
from renulus.runtime.harness_learning import HarnessLearningOwner
from renulus.runtime.harness_process import HarnessProcessConfig
from tests.runtime.test_harness_learning_admission import saved_admission
from tests.runtime.test_harness_learning_current import AdmissionTransport
from tests.learn.test_harness_bridge import active_shape


async def test_model_authority_exists_only_for_the_admitted_native_input(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    unknown = DomainBinding(receipt["run_id"], "1", "ses_unknown", "msg_unknown", receipt["run_id"])
    assert owner.resolve_model_run(unknown) is None
    stream = owner.bridge.answer(entry)
    try:
        assert (await anext(stream)).type == "started"
        assert (await anext(stream)).type == "progress"
        bound = owner.resolve_model_run(transport.binding)
        assert bound.binding == transport.binding
        assert bound.configuration_version == version
        assert bound.operation_model == "mimo-v2.6-pro"
        assert bound.purpose == "explain" and bound.required_capabilities == ("tools",)
        assert owner.resolve_model_run(transport.binding).cancellation is bound.cancellation
        with services.db.transaction() as conn:
            assert bound.current(conn=conn) is None
        assert owner.resolve_model_run(unknown) is None
    finally:
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()


async def test_admitted_learning_callback_rechecks_required_capability_revocation(saved_admission):
    services, authority, _, repo, chat, request, version = saved_admission
    config = HarnessProcessConfig(node_executable=Path("G:/unused-node.exe"),
        host_entry=Path("G:/unused-host.mjs"), profile_root=services.paths.root,
        profile_id="synthetic-profile", store_id="synthetic-runtime",
        domain_store_id="synthetic-domain", domain_path="state/renulus.sqlite3")
    owner = HarnessLearningOwner(services, config, configuration_id=version,
        configuration_authority=authority)
    owner.bridge.active_manifest = active_shape
    transport = AdmissionTransport(owner)
    owner.bridge.transport = transport
    services.registry["learning_harness"] = owner.bridge
    entry, receipt = repo.streaming.begin("learning", chat["identity"]["id"], request)
    stream = owner.bridge.answer(entry)
    try:
        await anext(stream)
        await anext(stream)
        grant = await owner.authorize(DomainRequest("capability-check", transport.binding, "learning.check", {}))
        assert grant.check_current() is True
        authority.revoke("tools")
        with pytest.raises(ApiError) as failure:
            grant.check_current()
        assert failure.value.code == "capability_revoked"
    finally:
        await owner.bridge.cancel(receipt["run_id"])
        await stream.aclose()
        await repo.streaming.close()
