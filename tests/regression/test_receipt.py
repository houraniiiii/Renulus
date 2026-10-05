"""Receipt integrity and guards; these checks are not product acceptance."""
import importlib.util
import builtins
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace
import sys

import pytest


spec = importlib.util.spec_from_file_location(
    "backend_receipt", Path(__file__).parents[2] / "scripts/run_backend_regression.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


def plugin_with_reports(tmp_path, phases):
    plugin = runner.ReceiptPlugin(tmp_path, runner.OfflineGuard(tmp_path), "application", 0)
    plugin.session = {"exitstatus": 0}
    for name, rows in phases.items():
        plugin.items.append({"nodeid": name, "selected": True, "category": "application"})
        plugin.reports.extend({"nodeid": name, "when": when, "outcome": outcome}
                              for when, outcome in rows)
    return plugin


PASSED = [("setup", "passed"), ("call", "passed"), ("teardown", "passed")]


def test_complete_final_junit_with_all_phases_can_be_accepted(tmp_path):
    plugin = plugin_with_reports(tmp_path, {"synthetic": PASSED})
    result = runner.receipt_result(plugin, 0, {"valid": True, "cases": 1}, True)
    assert result["complete"] is True
    assert result["accepted_stage_pass"] is True


def test_privacy_guards_stay_strict_while_preopened_receipts_finalize(tmp_path, monkeypatch):
    plugin = plugin_with_reports(tmp_path, {"synthetic": []})
    real_open, real_path_open, real_os_open = builtins.open, Path.open, os.open

    def guarded_open(source, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Application write forbidden"
        return real_open(source, mode, *args, **kwargs)

    def guarded_path_open(source, mode="r", *args, **kwargs):
        assert not any(flag in mode for flag in "wax+"), "Application write forbidden"
        return real_path_open(source, mode, *args, **kwargs)

    def guarded_os_open(source, flags, *args, **kwargs):
        assert not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)
        return real_os_open(source, flags, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", guarded_open)
        patch.setattr(Path, "open", guarded_path_open)
        patch.setattr(os, "open", guarded_os_open)
        with pytest.raises(AssertionError, match="Application write forbidden"):
            (tmp_path / "application-payload.txt").write_text("synthetic payload")
        plugin.resource("synthetic")
        for when, outcome in PASSED:
            plugin.pytest_runtest_logreport(SimpleNamespace(
                nodeid="synthetic", when=when, outcome=outcome,
                duration=0.01, failed=False, skipped=False))
        plugin.pytest_sessionfinish(SimpleNamespace(testscollected=1, testsfailed=0), 0)
        plugin.files.json("result.json", runner.receipt_result(
            plugin, 0, {"valid": True, "cases": 1}, True))
    plugin.files.close()
    assert json.loads((tmp_path / "result.json").read_text())["accepted_stage_pass"] is True
    assert len((tmp_path / "events.jsonl").read_text().splitlines()) == 3
    assert not (tmp_path / "application-payload.txt").exists()


def test_fourteen_call_dots_without_teardown_or_junit_cannot_pass(tmp_path):
    phases = {str(n): PASSED[:2] for n in range(14)}
    phases["not reached"] = []
    plugin = plugin_with_reports(tmp_path, phases)
    result = runner.receipt_result(plugin, 0, {"valid": False, "cases": 0}, True)
    assert result["outcomes"] == {"interrupted": 14, "not_run": 1}
    assert result["complete"] is False
    assert result["accepted_stage_pass"] is False


@pytest.mark.parametrize("change", ["missing-junit", "wrong-junit-count", "source-drift",
                                  "guard-violation", "nonzero-exit", "collection-error"])
def test_completed_calls_need_terminal_evidence_and_unchanged_source(tmp_path, change):
    plugin = plugin_with_reports(tmp_path, {"synthetic": PASSED})
    junit, clean, code = {"valid": True, "cases": 1}, True, 0
    if change == "missing-junit":
        junit["valid"] = False
    elif change == "wrong-junit-count":
        junit["cases"] = 2
    elif change == "source-drift":
        clean = False
    elif change == "guard-violation":
        plugin.guard.violations.append({"reason": "synthetic blocked remote access"})
    elif change == "nonzero-exit":
        code = 1
    else:
        plugin.collection_errors.append({"nodeid": "broken module"})
    assert runner.receipt_result(plugin, code, junit, clean)["accepted_stage_pass"] is False


def test_teardown_failure_and_setup_skip_are_not_passing_calls(tmp_path):
    plugin = plugin_with_reports(tmp_path, {
        "teardown fails": PASSED[:2] + [("teardown", "failed")],
        "setup skips": [("setup", "skipped"), ("teardown", "passed")],
        "passes": PASSED,
    })
    result = runner.receipt_result(plugin, 1, {"valid": True, "cases": 3}, True)
    assert result["outcomes"] == {"failed": 1, "skipped": 1, "passed": 1}
    assert result["complete"] is True
    assert result["accepted_stage_pass"] is False


@pytest.mark.parametrize("command", [
    [sys.executable, "-B", "synthetic.py"],
    '"' + sys.executable + '" -B "synthetic.py"',
    ["git", "rev-parse", "--short", "HEAD"],
    'git describe --always --dirty',
])
def test_nullable_executable_and_windows_command_strings_are_supported(tmp_path, command):
    guard = runner.OfflineGuard(tmp_path)
    guard.audit("subprocess.Popen", (None, command, str(tmp_path), {}))
    assert guard.violations == []


@pytest.mark.parametrize("explicit_executable", [False, True])
def test_windows_multiline_python_program_is_not_shell_parsed(tmp_path, explicit_executable):
    script = 'import json\nprint(json.dumps({"quoted": "synthetic path\\\\tail"}))\n'
    command = subprocess.list2cmdline([sys.executable, "-c", script, str(tmp_path)])
    guard = runner.OfflineGuard(tmp_path)
    guard.audit("subprocess.Popen",
        (sys.executable if explicit_executable else None, command, str(tmp_path), {}))
    assert guard.violations == []


@pytest.mark.parametrize("supplied,program", [(None, "powershell.exe"),
                                              ("powershell.exe", sys.executable)])
def test_multiline_command_cannot_disguise_a_non_python_executable(tmp_path, supplied, program):
    command = subprocess.list2cmdline([program, "-c", 'print("synthetic")\n', str(tmp_path)])
    guard = runner.OfflineGuard(tmp_path)
    with pytest.raises(AssertionError, match="subprocesses allowed"):
        guard.audit("subprocess.Popen", (supplied, command, str(tmp_path), {}))


def test_malformed_non_python_command_is_denied(tmp_path):
    guard = runner.OfflineGuard(tmp_path)
    with pytest.raises(AssertionError, match="subprocesses allowed"):
        guard.audit("subprocess.Popen", (None, 'powershell.exe -c "unterminated', str(tmp_path), {}))
    assert guard.violations


def test_pinned_hermes_backend_alias_is_an_owned_source(tmp_path):
    sources = {"renulus": str(tmp_path / "runtime/renulus/__init__.py"),
               "renulus.memory._vendored_hermes_backend":
                   str(tmp_path / "upstream/hermes/plugins/memory/mem0/_backend.py")}
    assert runner.unexpected_module_sources(sources, tmp_path) == {}


@pytest.mark.parametrize("name,relative_path", [
    ("renulus.unrecognised_alias", "upstream/hermes/plugins/memory/mem0/_backend.py"),
    ("renulus.memory._vendored_hermes_backend", "upstream/hermes/plugins/memory/mem0/other.py"),
    ("renulus.memory._vendored_hermes_backend", "foreign/runtime/renulus/_backend.py"),
])
def test_hermes_source_exception_does_not_admit_other_names_or_paths(tmp_path, name, relative_path):
    sources = {name: str(tmp_path / relative_path)}
    assert runner.unexpected_module_sources(sources, tmp_path) == sources


@pytest.mark.parametrize("name,relative_path", [
    ("renulus", "runtime/renulus/__init__.py"),
    ("renulus.memory._vendored_hermes_backend", "upstream/hermes/plugins/memory/mem0/_backend.py"),
])
def test_owned_source_path_cannot_resolve_outside_the_pinned_checkout(tmp_path, monkeypatch, name, relative_path):
    source = tmp_path / relative_path
    foreign = tmp_path / "foreign/source.py"
    original = Path.resolve

    def resolve(path, *args, **kwargs):
        return foreign if path == source else original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", resolve)
    sources = {name: str(source)}
    assert runner.unexpected_module_sources(sources, tmp_path) == sources


def test_git_argument_cannot_disguise_a_shell_executable(tmp_path):
    guard = runner.OfflineGuard(tmp_path)
    with pytest.raises(AssertionError, match="subprocesses allowed"):
        guard.audit("subprocess.Popen", ("powershell.exe", ["git", "status"], str(tmp_path), {}))


def test_parent_ports_remote_addresses_and_outside_writes_are_denied(tmp_path):
    guard = runner.OfflineGuard(tmp_path)
    for address in (("127.0.0.1", 8787), ("::1", 5196), ("198.51.100.42", 443)):
        with pytest.raises(AssertionError, match="socket forbidden"):
            guard.audit("socket.connect", (None, address))
    with pytest.raises(AssertionError, match="outside fresh owned scratch"):
        guard.audit("os.mkdir", (str(tmp_path.parent / "unowned"), 0o777, -1))
    guard.audit("os.mkdir", (str(tmp_path / "owned"), 0o777, -1))


def test_duplicate_collected_identities_are_rejected_before_execution(tmp_path):
    plugin = plugin_with_reports(tmp_path, {})
    item = SimpleNamespace(nodeid="tests/synthetic.py::same")
    with pytest.raises(AssertionError, match="Duplicate test identity"):
        plugin.pytest_collection_modifyitems(SimpleNamespace(), [item, item])
