"""Public deployment-proof seams; synthetic evidence is never account evidence."""
from dataclasses import FrozenInstanceError, replace
import asyncio
import base64
import json
import threading

import pytest

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import ConnectionReference, RoleBinding, RouteLimits
from renulus.runtime.harness_domain import DomainBinding, DomainCancelled
from renulus.runtime.harness_deployment import (
    DeploymentBinding, DeploymentEvidence, HarnessDeployment, NativeManifest,
)
from renulus.runtime.provider_adapter import subscription_route


PNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAAAAAA6fptVAAAACklEQVR4nGNgAAAAAgABSK+kcQAAAABJRU5ErkJggg=="
PNG_SHA = "eaa4a94ea300e0d2c775968cbe42f0b5b51ceafdeb73d64e9efddf6d4e880865"


@pytest.fixture
def admitted():
    binding = DomainBinding("operation-1", "attempt-1", "session-1", "input-1", "operation-1")
    route = subscription_route("codex", "gpt-6.1-sol", credential_ref="synthetic-account",
                               credential_epoch=7, catalogue=None)
    role = RoleBinding("a" * 64, "explain", ConnectionReference(provider="codex",
        credential_reference="synthetic-account", credential_revision=7), route.catalog_model_id,
        output_tokens=32, dispatch_limit=1)
    owner = DeploymentBinding(binding, "run-1", role, route)
    manifest = NativeManifest.from_payload({"version": 1, "system": "Synthetic system instruction",
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": "Explain synthetic dialysis"},
            {"type": "image", "media_type": "image/png", "sha256": PNG_SHA,
             "bytes": 67, "detail": None}]}],
        "tools": [{"name": "library_passage", "description": "Synthetic teaching",
                   "parameters_json": '{"type":"object","properties":{}}'}]})
    body = json.dumps({"model": route.wire_model_id, "stream": True, "store": False,
        "instructions": manifest.system, "input": [{"type": "message", "role": "user",
            "content": [{"type": "input_text", "text": "Explain synthetic dialysis"},
                        {"type": "input_image", "image_url": "data:image/png;base64," + PNG}]}],
        "tools": [{"type": "function", "name": "library_passage",
                   "description": "Synthetic teaching", "parameters": {"type": "object",
                   "properties": {}}, "strict": False}], "max_output_tokens": 32},
        ensure_ascii=False, indent=2).encode()
    request = {"method": "POST", "url": route.endpoint, "headers": {"content-type": "application/json"},
               "body_base64": base64.b64encode(body).decode()}

    async def resolve(actual):
        assert actual == binding
        return owner

    async def count(actual_body, actual_manifest):
        assert actual_manifest == manifest
        state.setdefault("counted_bodies", []).append(actual_body)
        # Explicit synthetic total; no inference/tokenizer/account claim.
        return 23

    evidence = DeploymentEvidence("synthetic-evidence-1", route,
        RouteLimits(input_tokens=100, output_tokens=32, window_tokens=132),
        ("text", "tools", "image"), "synthetic-limits-1", "synthetic-capabilities-1",
        "synthetic-tokenizer-framing-tools-images-1", count)
    state = {"owner": owner, "evidence": evidence, "current": True}

    def check(preparation):
        assert preparation.binding == binding
        if state.get("guard_error"):
            raise state["guard_error"]
        assert state["current"]

    module = HarnessDeployment(resolve=resolve, evidence=lambda _: state["evidence"],
                               check_current=check, max_request_bytes=16384)
    return module, binding, manifest, request, body, state


async def test_proof_preserves_exact_native_bytes_and_trusted_input_accounting(admitted):
    module, binding, manifest, request, body, _ = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    assert proof.body == body
    assert proof.body_bytes == len(body)
    assert proof.input_tokens == 23 and proof.output_tokens == 32
    assert proof.preparation.route.credential_epoch == 7
    assert proof.preparation.role.purpose == "explain"
    module.require_current(proof, body=body)
    with pytest.raises(FrozenInstanceError):
        proof.input_tokens = 0


@pytest.mark.parametrize("omitted", ["system", "tool", "image"])
async def test_final_wire_cannot_omit_admitted_system_tool_or_image(admitted, omitted):
    module, binding, manifest, request, body, state = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    changed = json.loads(body)
    if omitted == "system":
        changed.pop("instructions")
    elif omitted == "tool":
        changed["tools"] = []
    else:
        changed["input"][0]["content"].pop()
    request = {**request, "body_base64": base64.b64encode(json.dumps(changed).encode()).decode()}
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_manifest_mismatch"
    assert not state.get("counted_bodies")


async def test_final_guard_rejects_equal_length_body_mutation(admitted):
    module, binding, manifest, request, body, _ = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    changed = body.replace(b"dialysis", b"training")
    assert len(changed) == len(body) and changed != body
    with pytest.raises(ApiError) as caught:
        module.require_current(proof, body=changed)
    assert caught.value.code == "deployment_body_changed"


@pytest.mark.parametrize("missing", ["limits_revision", "capabilities_revision", "counter_revision", "counter",
                                    "input_tokens", "output_tokens", "window_tokens"])
async def test_preparation_denies_unknown_deployment_evidence_before_counting(admitted, missing):
    module, binding, _, _, _, state = admitted
    evidence = state["evidence"]
    if missing.endswith("tokens"):
        limits = evidence.limits.model_copy(update={missing: None})
        state["evidence"] = replace(evidence, limits=limits)
    else:
        state["evidence"] = replace(evidence, **{missing: None})
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code in {"deployment_evidence_unknown", "deployment_counter_unknown", "route_limits_unknown"}
    assert not state.get("counted_bodies")


async def test_evidence_cannot_be_borrowed_from_another_credential_revision(admitted):
    module, binding, _, _, _, state = admitted
    state["evidence"] = replace(state["evidence"],
        route=replace(state["evidence"].route, credential_epoch=8))
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code == "deployment_evidence_mismatch"


async def test_unknown_image_capability_cannot_enter_native_preparation(admitted):
    module, binding, _, _, _, state = admitted
    state["evidence"] = replace(state["evidence"], capabilities=("text", "tools"))
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code == "deployment_capability_unknown"


@pytest.mark.parametrize("count", [None, True, -1, "23", 101])
async def test_counter_must_supply_a_known_inclusive_count_within_input_limit(admitted, count):
    module, binding, manifest, request, _, state = admitted

    async def counter(body, snapshot):
        return count

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == ("deployment_input_exceeds_limit" if count == 101 else "deployment_counter_unknown")


async def test_evidence_is_rechecked_after_awaited_counting(admitted):
    module, binding, manifest, request, _, state = admitted

    async def counter(body, snapshot):
        state["evidence"] = replace(state["evidence"], counter_revision="synthetic-revised-rules")
        return 23

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_evidence_stale"


@pytest.mark.parametrize("during", ["before_count", "after_await", "final_guard"])
async def test_current_credential_guard_preserves_sanitized_trusted_error(admitted, during):
    module, binding, manifest, request, body, state = admitted
    error = ApiError("connection_changed", "PRIVATE credential-canary", 409, True)

    async def counter(actual_body, snapshot):
        if during == "after_await":
            state["guard_error"] = error
        return 23

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    if during == "before_count":
        state["guard_error"] = error
    if during != "final_guard":
        with pytest.raises(ApiError) as caught:
            await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    else:
        proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                                   serialized_request=request, manifest=manifest)
        state["guard_error"] = error
        with pytest.raises(ApiError) as caught:
            module.require_current(proof, body=body)
    assert (caught.value.code, caught.value.status, caught.value.retryable) == ("connection_changed", 409, True)
    assert "PRIVATE" not in str(caught.value)


async def test_counter_internal_failure_is_sanitized_without_becoming_cancellation(admitted):
    module, binding, manifest, request, _, state = admitted

    async def counter(body, snapshot):
        raise ApiError("memory_support_budget", "PRIVATE body-canary", 409, False)

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert (caught.value.code, caught.value.status, caught.value.retryable) == ("memory_support_budget", 409, False)
    assert "PRIVATE" not in str(caught.value)


async def test_cancellation_retains_real_counter_and_finalizer_until_settlement(admitted):
    module, binding, manifest, request, _, state = admitted
    entered, finish, settled = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def counter(body, snapshot):
        entered.set()
        try:
            await finish.wait()
            return 23
        finally:
            settled.set()

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    task = asyncio.create_task(module.prove(preparation, step_id="step-1", request_kind="primary",
                             serialized_request=request, manifest=manifest))
    try:
        await entered.wait()
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not settled.is_set()
    finally:
        finish.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert settled.is_set()


async def test_domain_cancellation_is_distinct_and_blocks_proof_after_count(admitted):
    module, binding, manifest, request, _, state = admitted

    async def counter(body, snapshot):
        state["guard_error"] = DomainCancelled("PRIVATE cancellation-canary")
        return 23

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(DomainCancelled, match="^domain_cancelled$"):
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)


def replay_case(admitted, provider):
    _, binding, manifest, _, _, state = admitted
    route = subscription_route(provider, "gpt-6.1-sol" if provider == "codex" else "mimo-v2.6-pro",
                               credential_ref="synthetic-account", credential_epoch=7, catalogue=None)
    role = replace(state["owner"].role, model_id=route.catalog_model_id,
        connection=ConnectionReference(provider=provider, credential_reference=route.credential_ref,
                                       credential_revision=route.credential_epoch))
    owner = DeploymentBinding(binding, "run-1", role, route)
    snapshot = manifest.model_dump(mode="json")
    snapshot["messages"] = [{"role": "user", "content": [{"type": "text", "text": "Earlier prompt"}]},
        {"role": "assistant", "content": [{"type": "tool-call", "id": "call-1", "name": "library_passage",
            "arguments_json": '{"query":"dialysis","limit":1}'}]},
        {"role": "tool", "content": [{"type": "tool-result", "id": "call-1", "output_text": "Exact passage"}]}]
    snapshot["messages"].extend(manifest.model_dump(mode="json")["messages"])
    manifest = NativeManifest.from_payload(snapshot)
    common = {"model": route.wire_model_id, "stream": True}
    function = {"name": "library_passage", "description": "Synthetic teaching",
                "parameters": {"properties": {}, "type": "object"}, "strict": False}
    if provider == "codex":
        payload = {**common, "instructions": manifest.system, "input": [
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Earlier prompt"}]},
            {"type": "function_call", "call_id": "call-1", "name": "library_passage",
             "arguments": '{"limit":1,"query":"dialysis"}'},
            {"type": "function_call_output", "call_id": "call-1", "output": "Exact passage"},
            {"role": "user", "content": [{"type": "input_text", "text": "Explain synthetic dialysis"},
                {"type": "input_image", "image_url": "data:image/png;base64," + PNG}]}],
            "tools": [{"type": "function", **function}], "max_output_tokens": 32}
    else:
        payload = {**common, "messages": [{"role": "system", "content": manifest.system},
            {"role": "user", "content": "Earlier prompt"}, {"role": "assistant", "content": None,
                "tool_calls": [{"id": "call-1", "type": "function", "function": {
                    "name": "library_passage", "arguments": '{"limit":1,"query":"dialysis"}'}}]},
            {"role": "tool", "tool_call_id": "call-1", "content": "Exact passage"},
            {"role": "user", "content": [{"type": "text", "text": "Explain synthetic dialysis"},
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + PNG}}]}],
            "tools": [{"type": "function", "function": function}], "max_completion_tokens": 32}

    async def resolve(actual):
        return owner

    async def counter(body, actual_manifest):
        assert actual_manifest == manifest
        assert b"Exact passage" in body and b"Earlier prompt" in body
        # Inclusive synthetic count for system+history+tools+image. No tokenizer claim.
        return 57

    evidence = replace(state["evidence"], route=route, counter=counter)
    module = HarnessDeployment(resolve=resolve, evidence=lambda _: evidence,
                               check_current=lambda _: None, max_request_bytes=16384)
    body = json.dumps(payload, indent=2).encode()
    request = {"method": "POST", "url": route.endpoint, "headers": {"content-type": "application/json"},
               "body_base64": base64.b64encode(body).decode()}
    return module, binding, manifest, payload, request, body


@pytest.mark.parametrize("provider", ["codex", "opencode-go"])
async def test_both_native_protocols_preserve_tool_replay_and_json_semantics(admitted, provider):
    module, binding, manifest, _, request, body = replay_case(admitted, provider)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    assert proof.body == body and proof.input_tokens == 57
    module.require_current(proof, body=body)


@pytest.mark.parametrize("provider", ["codex", "opencode-go"])
@pytest.mark.parametrize("control,value", [
    ("previous_response_id", "PRIVATE hidden-history-canary"),
    ("previous_response_id", None),
    ("conversation", {"id": "PRIVATE conversation-canary"}),
    ("conversation", None),
    ("context_management", [{"type": "compaction", "compact_threshold": 1}]),
    ("context_management", []),
    ("truncation", "auto"),
    ("truncation", "unknown"),
    ("truncation", True),
    ("truncation", None),
    ("thread_id", "PRIVATE hidden-thread-canary"),
    ("unreviewed_context_control", {"encrypted_content": "PRIVATE opaque-canary"}),
])
async def test_proof_denies_hidden_context_controls_before_counter(admitted, provider, control, value):
    original, binding, manifest, payload, request, _ = replay_case(admitted, provider)
    counted = []
    initial = await original.prepare(binding, required_capabilities=("text", "tools", "image"))
    evidence = initial.evidence

    async def counter(body, snapshot):
        counted.append(body)
        return await evidence.counter(body, snapshot)

    # The public evidence injection observes whether accounting was reached.
    guarded_evidence = replace(evidence, counter=counter)
    module = HarnessDeployment(resolve=original.resolve, evidence=lambda _: guarded_evidence,
                               check_current=lambda _: None, max_request_bytes=16384)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    changed = {**payload, control: value}
    request = {**request, "body_base64": base64.b64encode(json.dumps(changed).encode()).decode()}
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_manifest_mismatch"
    assert "PRIVATE" not in str(caught.value)
    assert not counted


@pytest.mark.parametrize("provider", ["codex", "opencode-go"])
async def test_proof_counts_exact_body_with_reviewed_route_framing(admitted, provider):
    original, binding, manifest, payload, request, _ = replay_case(admitted, provider)
    initial = await original.prepare(binding, required_capabilities=("text", "tools", "image"))
    evidence = initial.evidence
    counted = []

    async def counter(body, snapshot):
        counted.append((body, snapshot))
        return await evidence.counter(body, snapshot)

    guarded_evidence = replace(evidence, counter=counter)
    module = HarnessDeployment(resolve=original.resolve, evidence=lambda _: guarded_evidence,
                               check_current=lambda _: None, max_request_bytes=16384)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    payload.update({"store": False, "temperature": 0, "stream_options":
        {"include_obfuscation": False} if provider == "codex" else {"include_usage": True}})
    if provider == "codex":
        payload["truncation"] = "disabled"
    body = json.dumps(payload, indent=3).encode()
    request = {**request, "body_base64": base64.b64encode(body).decode()}
    proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    assert counted == [(body, manifest)]
    assert proof.body == body and proof.input_tokens == 57


@pytest.mark.parametrize("provider", ["codex", "opencode-go"])
@pytest.mark.parametrize("mutation", ["tool_result", "tool_id", "arguments", "schema", "image_hash", "image_detail"])
async def test_native_replay_proof_rejects_changed_refs_schemas_and_image_identity(admitted, provider, mutation):
    module, binding, manifest, payload, request, _ = replay_case(admitted, provider)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    responses = provider == "codex"
    if mutation == "tool_result":
        (payload["input"] if responses else payload["messages"]).pop(2 if responses else 3)
    elif mutation == "tool_id":
        (payload["input"][2] if responses else payload["messages"][3])["call_id" if responses else "tool_call_id"] = "call-other"
    elif mutation == "arguments":
        (payload["input"][1] if responses else payload["messages"][2]["tool_calls"][0]["function"])["arguments"] = '{"limit":2,"query":"dialysis"}'
    elif mutation == "schema":
        (payload["tools"][0] if responses else payload["tools"][0]["function"])["parameters"]["properties"] = {"different": {"type": "string"}}
    else:
        image = (payload["input"] if responses else payload["messages"])[-1]["content"][-1]
        if mutation == "image_hash":
            image["image_url"] = "data:image/png;base64,Y2hhbmdlZA==" if responses else {"url": "data:image/png;base64,Y2hhbmdlZA=="}
        else:
            (image if responses else image["image_url"])["detail"] = "high"
    request = {**request, "body_base64": base64.b64encode(json.dumps(payload).encode()).decode()}
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_manifest_mismatch"


@pytest.mark.parametrize("invalid", ["wrong_url", "wrong_method", "invalid_base64", "non_object", "wrong_model", "output_cap", "duplicate_key"])
async def test_proof_refuses_invalid_or_unbound_final_request(admitted, invalid):
    module, binding, manifest, request, body, _ = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    if invalid == "wrong_url":
        request = {**request, "url": "https://invalid.example/no-dispatch"}
    elif invalid == "wrong_method":
        request = {**request, "method": "GET"}
    elif invalid == "invalid_base64":
        request = {**request, "body_base64": "PRIVATE invalid-canary!"}
    else:
        payload = json.loads(body)
        if invalid == "wrong_model":
            payload["model"] = "different-deployment"
        elif invalid == "output_cap":
            payload["max_output_tokens"] = 33
        if invalid == "duplicate_key":
            changed = b'{"instructions":"PRIVATE duplicate-canary",' + body[1:]
        else:
            changed = json.dumps([] if invalid == "non_object" else payload).encode()
        request = {**request, "body_base64": base64.b64encode(changed).decode()}
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert "PRIVATE" not in str(caught.value)


async def test_native_features_must_be_prepared_before_media_filtering(admitted):
    module, binding, manifest, request, _, state = admitted
    preparation = await module.prepare(binding, required_capabilities=("text",))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_capability_unprepared"
    assert not state.get("counted_bodies")


@pytest.mark.parametrize("version", [True, "1", 1.0])
def test_manifest_version_has_strict_integer_identity_without_private_validation_data(admitted, version):
    _, _, manifest, _, _, _ = admitted
    payload = {**manifest.model_dump(mode="json"), "version": version, "system": "PRIVATE input-canary"}
    with pytest.raises(ApiError) as caught:
        NativeManifest.from_payload(payload)
    assert caught.value.code == "deployment_manifest_invalid"
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("part", ["reasoning", "compaction", "system", "remote-image", "mutable-schema"])
def test_v1_manifest_refuses_unmeasurable_or_untyped_native_shapes(admitted, part):
    _, _, manifest, _, _, _ = admitted
    payload = manifest.model_dump(mode="json")
    if part in ("reasoning", "compaction"):
        payload["messages"][0]["content"] = [{"type": part, "text": "PRIVATE omitted-canary"}]
    elif part == "system":
        payload["messages"][0]["role"] = "system"
    elif part == "remote-image":
        payload["messages"][0]["content"][-1]["url"] = "https://invalid.example/private"
    else:
        payload["tools"][0]["parameters_json"] = {"type": "object"}
    with pytest.raises(ApiError) as caught:
        NativeManifest.from_payload(payload)
    assert caught.value.code == "deployment_manifest_invalid"
    assert "PRIVATE" not in str(caught.value)


@pytest.mark.parametrize("step,kind,continuation", [("", "primary", None), ("step-1", "invented", None),
    ("step-1", "primary", "permit-1"), ("step-1", "tool-continuation", None)])
async def test_parent_must_supply_valid_step_and_continuation_identity(admitted, step, kind, continuation):
    module, binding, manifest, request, _, _ = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id=step, request_kind=kind, continuation_of=continuation,
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_step_unbound"


async def test_unknown_guard_result_never_becomes_a_current_authority_grant(admitted):
    original, binding, _, _, _, _ = admitted
    module = HarnessDeployment(resolve=original.resolve, evidence=original.evidence,
                               check_current=lambda _: False, max_request_bytes=16384)
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code == "deployment_authority_unbound"


async def test_proven_window_accounts_for_both_input_and_requested_output(admitted):
    module, binding, manifest, request, _, state = admitted
    state["evidence"] = replace(state["evidence"], limits=RouteLimits(
        input_tokens=100, output_tokens=32, window_tokens=54))
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    with pytest.raises(ApiError) as caught:
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert caught.value.code == "deployment_window_exceeds_limit"


async def test_current_evidence_is_rechecked_at_final_guard(admitted):
    module, binding, manifest, request, body, state = admitted
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    proof = await module.prove(preparation, step_id="step-1", request_kind="primary",
                               serialized_request=request, manifest=manifest)
    state["evidence"] = replace(state["evidence"], limits_revision="synthetic-revised-limit")
    with pytest.raises(ApiError) as caught:
        module.require_current(proof, body=body)
    assert caught.value.code == "deployment_evidence_stale"


async def test_guard_cannot_return_current_after_changing_evidence(admitted):
    original, binding, _, _, _, state = admitted

    def check(preparation):
        state["evidence"] = replace(state["evidence"], counter_revision="synthetic-changed-in-guard")

    module = HarnessDeployment(resolve=original.resolve, evidence=original.evidence,
                               check_current=check, max_request_bytes=16384)
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code == "deployment_evidence_stale"


async def test_malformed_trusted_evidence_has_no_raw_exception_diagnostics(admitted):
    module, binding, _, _, _, state = admitted
    state["evidence"] = replace(state["evidence"], route=None)
    with pytest.raises(ApiError) as caught:
        await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    assert caught.value.code == "deployment_evidence_unknown"


@pytest.mark.parametrize("boundary", ["resolve", "evidence", "current", "counter"])
async def test_unexpected_trusted_fault_is_sanitized_unavailable(admitted, boundary):
    original, binding, manifest, request, _, state = admitted

    async def fail_async(*_):
        raise RuntimeError("PRIVATE internal-canary")

    def fail_sync(*_):
        raise RuntimeError("PRIVATE internal-canary")

    if boundary == "counter":
        state["evidence"] = replace(state["evidence"], counter=fail_async)
    module = HarnessDeployment(resolve=fail_async if boundary == "resolve" else original.resolve,
        evidence=fail_sync if boundary == "evidence" else original.evidence,
        check_current=fail_sync if boundary == "current" else original.check_current,
        max_request_bytes=16384)
    with pytest.raises(ApiError) as caught:
        preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
        await module.prove(preparation, step_id="step-1", request_kind="primary",
                           serialized_request=request, manifest=manifest)
    assert (caught.value.code, caught.value.status, caught.value.retryable) == ("deployment_proof_unavailable", 503, True)
    assert "PRIVATE" not in str(caught.value)


async def test_cancelled_proof_waits_for_actual_cpu_counter_settlement(admitted):
    module, binding, manifest, request, _, state = admitted
    loop, entered = asyncio.get_running_loop(), asyncio.Event()
    release, settled = threading.Event(), threading.Event()

    def cpu_counter():
        loop.call_soon_threadsafe(entered.set)
        try:
            assert release.wait(5), "Synthetic CPU counter did not receive its settlement signal"
            return 23
        finally:
            settled.set()

    async def counter(body, snapshot):
        return await asyncio.to_thread(cpu_counter)

    state["evidence"] = replace(state["evidence"], counter=counter)
    preparation = await module.prepare(binding, required_capabilities=("text", "tools", "image"))
    task = asyncio.create_task(module.prove(preparation, step_id="step-1", request_kind="primary",
                             serialized_request=request, manifest=manifest))
    try:
        await asyncio.wait_for(entered.wait(), 2)
        task.cancel()
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not settled.is_set()
    finally:
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert settled.is_set()
