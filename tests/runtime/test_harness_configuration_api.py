# SPDX-License-Identifier: MIT
"""Public configuration routes use one synthetic trusted controller, no providers."""
from copy import deepcopy
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from renulus.contracts import ApiError
from renulus.runtime.harness_configuration import ConfigurationSpec, ConnectionReference, PURPOSES, RolePolicy


PATH = "/api/v1/runtime/harness/configuration"
EFFECTIVE = "a" * 64
REQUESTED = "b" * 64
FAILED = "c" * 64
STAGED = "d" * 64
CANARY = "synthetic-secret-canary"


def public_snapshot():
    return {
        "requested": REQUESTED, "effective": EFFECTIVE, "failed": FAILED,
        "failure_code": "candidate_invalid", "admission_open": True,
        "configuration": {
            "roles": [{"purpose": "explain", "enabled": True, "model_id": None,
                "output_tokens": 4096, "dispatch_limit": None}],
            "attempts": {"foreground_dispatches": 12, "standalone_dispatches": 1,
                "title_dispatches": 0, "retries": 0},
        },
        "requested_configuration": {
            "roles": [{"purpose": "summary", "enabled": False, "model_id": "mimo-v2.6-pro",
                "output_tokens": 2048, "dispatch_limit": 0}],
            "attempts": {"foreground_dispatches": 12, "standalone_dispatches": 1,
                "title_dispatches": 0, "retries": 0},
        },
        "pinned_runs": [{"run_id": "synthetic-run", "purpose": "explain", "version": EFFECTIVE}],
        "catalogue": ["deepseek-v4.1-flash", "mimo-v2.6-pro"],
    }


class SyntheticController:
    def __init__(self):
        self.value = public_snapshot()
        self.calls = []

    async def snapshot(self):
        self.calls.append(("snapshot",))
        return deepcopy(self.value)

    async def stage_roles(self, roles):
        self.calls.append(("stage_roles", roles))
        self.value["requested"] = STAGED
        self.value["requested_configuration"]["roles"] = [role.model_dump() for role in roles]
        return {"version": STAGED, **deepcopy(self.value), "credentials": CANARY}

    async def activate(self, version):
        self.calls.append(("activate", version))
        self.value["effective"] = version
        self.value["admission_open"] = True
        return deepcopy(self.value)


def client_for(controller=None):
    from renulus.runtime.harness_configuration_api import create_router

    services = SimpleNamespace(registry={})
    if controller is not None:
        services.registry["harness_configuration_controller"] = controller
    app = FastAPI()

    @app.exception_handler(ApiError)
    async def product_error(request, error):
        return JSONResponse(status_code=error.status, content={"error": {
            "code": error.code, "message": error.message, "retryable": error.retryable,
        }})

    @app.exception_handler(RequestValidationError)
    async def invalid_request(request, error):
        # Match the existing server boundary: submitted values are never echoed.
        fields = [".".join(str(item) for item in issue["loc"]) for issue in error.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "invalid_request", "message": "Check the submitted fields: " + ", ".join(fields),
            "retryable": False,
        }})

    app.include_router(create_router(services), prefix="/api/v1")
    return TestClient(app)


def test_absent_controller_reports_retryable_unavailability():
    with client_for() as client:
        response = client.get(PATH)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "harness_configuration_unavailable"
    assert response.json()["error"]["retryable"] is True


def test_get_projects_settings_fields_and_redacts_every_internal_layer():
    controller = SyntheticController()
    controller.value.update(credentials={"access_token": CANARY}, registry_hash=CANARY)
    for key in ("configuration", "requested_configuration"):
        spec = controller.value[key]
        spec.update(connection={"credential_reference": CANARY}, context={"instructions": CANARY},
            children={"internal": CANARY}, inputs=[{"path": CANARY}])
        spec["roles"][0]["credentials"] = CANARY
        spec["attempts"]["retryable_errors"] = [CANARY]
    controller.value["pinned_runs"][0]["protected_reference"] = CANARY
    original = deepcopy(controller.value)
    with client_for(controller) as client:
        response = client.get(PATH)
    assert response.status_code == 200, response.text
    assert response.json() == public_snapshot()
    assert CANARY not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert controller.value == original
    assert controller.calls == [("snapshot",)]


def test_stage_reuses_role_defaults_and_sends_only_an_immutable_role_tuple():
    controller = SyntheticController()
    with client_for(controller) as client:
        response = client.post(PATH, json={"roles": [
            {"purpose": "explain"},
            {"purpose": "title", "enabled": False, "model_id": None,
                "output_tokens": 1, "dispatch_limit": 0},
        ]})
        snapshot = client.get(PATH)
    assert response.status_code == 200, response.text
    assert response.json() == {
        "version": STAGED, "requested": STAGED, "effective": EFFECTIVE, "failed": FAILED,
        "failure_code": "candidate_invalid", "admission_open": True,
    }
    assert CANARY not in response.text
    roles = controller.calls[0][1]
    assert isinstance(roles, tuple) and all(isinstance(role, RolePolicy) for role in roles)
    assert [role.model_dump() for role in roles] == [
        {"purpose": "explain", "enabled": True, "model_id": None,
            "output_tokens": 4096, "dispatch_limit": None},
        {"purpose": "title", "enabled": False, "model_id": None,
            "output_tokens": 1, "dispatch_limit": 0},
    ]
    assert snapshot.json()["requested"] == STAGED
    assert snapshot.json()["effective"] == EFFECTIVE
    assert snapshot.json()["requested_configuration"]["roles"] == [role.model_dump() for role in roles]
    assert [call[0] for call in controller.calls] == ["stage_roles", "snapshot"]


@pytest.mark.parametrize("body", [
    {},
    {"roles": []},
    {"roles": None},
    {"roles": [{"purpose": "explain"}] * 15},
    {"roles": [{"purpose": "explain"}, {"purpose": "explain", "enabled": False}]},
    {"roles": [{"purpose": "invented-purpose"}]},
    {"roles": [{"purpose": "explain", "enabled": "false"}]},
    {"roles": [{"purpose": "explain", "output_tokens": "4096"}]},
    {"roles": [{"purpose": "explain", "output_tokens": 0}]},
    {"roles": [{"purpose": "explain", "output_tokens": 32769}]},
    {"roles": [{"purpose": "explain", "dispatch_limit": True}]},
    {"roles": [{"purpose": "explain", "dispatch_limit": -1}]},
    {"roles": [{"purpose": "explain", "dispatch_limit": 129}]},
    {"roles": [{"purpose": "explain", "credential_reference": CANARY}]},
    {"roles": [{"purpose": "explain", "configuration_id": EFFECTIVE}]},
    {"roles": [{"purpose": "explain"}], "version": EFFECTIVE},
    {"roles": [{"purpose": "explain"}], "connection": {"credentials": CANARY}},
    {"roles": [{"purpose": "explain"}], "attempts": {"foreground_dispatches": 128}},
])
def test_invalid_stage_requests_never_reach_the_controller(body):
    controller = SyntheticController()
    with client_for(controller) as client:
        response = client.post(PATH, json=body)
    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "invalid_request"
    assert CANARY not in response.text
    assert controller.calls == []


def test_all_fourteen_unique_roles_can_be_staged_with_explicit_nullable_fields():
    controller = SyntheticController()
    with client_for(controller) as client:
        response = client.post(PATH, json={"roles": [
            {"purpose": purpose, "model_id": None, "dispatch_limit": None}
            for purpose in sorted(PURPOSES)
        ]})
    assert response.status_code == 200, response.text
    assert len(controller.calls[0][1]) == 14
    assert all(role.model_id is None and role.dispatch_limit is None for role in controller.calls[0][1])


def test_activation_passes_the_exact_hash_and_projects_the_returned_snapshot():
    controller = SyntheticController()
    controller.value["credentials"] = CANARY
    controller.value["configuration"]["connection"] = {"credential_reference": CANARY}
    expected = public_snapshot()
    expected["effective"] = REQUESTED
    with client_for(controller) as client:
        response = client.post(PATH + "/activate", json={"version": REQUESTED})
        snapshot = client.get(PATH)
    assert response.status_code == 200, response.text
    assert response.json() == expected
    assert snapshot.json() == expected
    assert CANARY not in response.text
    assert controller.calls == [("activate", REQUESTED), ("snapshot",)]


@pytest.mark.parametrize("body", [
    {}, {"version": None}, {"version": 1},
    {"version": "B" * 64}, {"version": "g" * 64},
    {"version": "b" * 63}, {"version": "b" * 65}, {"version": REQUESTED + "\n"},
    {"version": REQUESTED, "credentials": CANARY},
    {"version": REQUESTED, "connection": {"credential_reference": CANARY}},
    {"version": REQUESTED, "roles": [{"purpose": "explain"}]},
])
def test_invalid_activation_requests_never_reach_the_controller(body):
    controller = SyntheticController()
    with client_for(controller) as client:
        response = client.post(PATH + "/activate", json=body)
    assert response.status_code == 422, response.text
    assert CANARY not in response.text
    assert controller.calls == []


@pytest.mark.parametrize("route,body", [
    (PATH, {"roles": [{"purpose": "explain"}]}),
    (PATH + "/activate", {"version": REQUESTED}),
])
def test_absent_controller_does_not_accept_mutations(route, body):
    with client_for() as client:
        response = client.post(route, json=body)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "harness_configuration_unavailable"
    assert response.json()["error"]["retryable"] is True


def test_busy_activation_keeps_requested_effective_and_reported_pins_unchanged():
    class BusyController(SyntheticController):
        async def activate(self, version):
            self.calls.append(("activate", version))
            raise ApiError("harness_configuration_busy", "Finish or stop the pinned runs.", 409, True)

    controller = BusyController()
    with client_for(controller) as client:
        before = client.get(PATH)
        response = client.post(PATH + "/activate", json={"version": REQUESTED})
        after = client.get(PATH)
    assert response.status_code == 409
    assert response.json() == {"error": {"code": "harness_configuration_busy",
        "message": "Finish or stop the pinned runs.", "retryable": True}}
    assert after.json() == before.json() == public_snapshot()
    assert controller.calls == [("snapshot",), ("activate", REQUESTED), ("snapshot",)]


@pytest.mark.parametrize("operation,status,code,retryable", [
    ("snapshot", 503, "harness_store_unhealthy", True),
    ("stage_roles", 422, "model_not_allowed", False),
    ("activate", 409, "harness_candidate_failed", False),
])
def test_controller_api_errors_keep_their_real_classification(operation, status, code, retryable):
    class RefusingController(SyntheticController):
        async def snapshot(self):
            if operation == "snapshot":
                raise ApiError(code, "Synthetic controller refusal.", status, retryable)
            return await super().snapshot()

        async def stage_roles(self, roles):
            self.calls.append(("stage_roles", roles))
            raise ApiError(code, "Synthetic controller refusal.", status, retryable)

        async def activate(self, version):
            self.calls.append(("activate", version))
            self.value["failed"] = version
            self.value["failure_code"] = code
            raise ApiError(code, "Synthetic controller refusal.", status, retryable)

    controller = RefusingController()
    with client_for(controller) as client:
        if operation == "snapshot":
            response = client.get(PATH)
        elif operation == "stage_roles":
            response = client.post(PATH, json={"roles": [{"purpose": "explain", "model_id": "unapproved"}]})
        else:
            response = client.post(PATH + "/activate", json={"version": REQUESTED})
            after = client.get(PATH).json()
            assert after["requested"] == REQUESTED and after["effective"] == EFFECTIVE
            assert after["failed"] == REQUESTED and after["failure_code"] == code
            assert after["admission_open"] is True
    assert response.status_code == status
    assert response.json() == {"error": {
        "code": code, "message": "Synthetic controller refusal.", "retryable": retryable,
    }}
    if operation == "stage_roles":
        assert controller.calls[0][1][0].model_id == "unapproved"


def test_unexpected_controller_failures_are_not_classified_as_absence():
    class BrokenController(SyntheticController):
        async def snapshot(self):
            raise RuntimeError("Synthetic assembly bug.")

    with client_for(BrokenController()) as client:
        with pytest.raises(RuntimeError, match="Synthetic assembly bug"):
            client.get(PATH)


def test_unconfigured_snapshot_preserves_nullable_versions_and_closed_admission():
    controller = SyntheticController()
    controller.value = {"requested": None, "effective": None, "failed": None, "failure_code": None,
        "admission_open": False, "configuration": None, "requested_configuration": None,
        "pinned_runs": [], "catalogue": []}
    with client_for(controller) as client:
        response = client.get(PATH)
    assert response.status_code == 200, response.text
    assert response.json() == controller.value


def test_existing_immutable_spec_and_catalogue_tuples_project_without_protected_references():
    controller = SyntheticController()
    connection = ConnectionReference(provider="opencode-go", credential_reference=CANARY,
        credential_revision=7, selected_model="mimo-v2.6-pro")
    controller.value["configuration"] = ConfigurationSpec(connection=connection, registry_hash="e" * 64,
        roles=(RolePolicy(purpose="explain"),))
    controller.value["requested_configuration"] = ConfigurationSpec(connection=connection, registry_hash="f" * 64,
        roles=(RolePolicy(purpose="summary", enabled=False, model_id="mimo-v2.6-pro",
            output_tokens=2048, dispatch_limit=0),))
    controller.value["catalogue"] = ("deepseek-v4.1-flash", "mimo-v2.6-pro")
    controller.value["pinned_runs"] = tuple(controller.value["pinned_runs"])
    with client_for(controller) as client:
        response = client.get(PATH)
    assert response.status_code == 200, response.text
    assert response.json() == public_snapshot()
    assert CANARY not in response.text
