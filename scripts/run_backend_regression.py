"""Serial offline backend checks with a complete, source-attributed receipt.

Use the existing public Python environment. Scratch must be fresh; previous
attempts, profiles, dependency trees and acquired collections remain untouched.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.abc
import importlib.machinery
import importlib.metadata
import ipaddress
import json
import os
from pathlib import Path
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
GIB = 2**30
CAPACITY_FILES = {
    "tests/backup/test_segmented_capacity.py",
    "tests/backup/test_recovery_capacity_sidecar.py",
}
CAPACITY_PREFIXES = (
    "test_actual_265_mib_synthetic_originals",
    "test_product_api_streams_large_canonical_library",
    "test_catalogue_at_183891_rows",
    "test_large_structured_extraction_is_omitted",
    "test_raw_file_upload_and_malformed_size_format_errors",
    "test_oversized",
)
ENGINE_FILES = {
    "tests/cases/test_offline_attachment_flow.py",
    "tests/knowledge/test_offline_engines.py",
    "tests/memory/test_mem0_real.py",
    "tests/backup/test_offline_engine_round_trip.py",
    "tests/runtime/test_windows_helpers.py",
    "tests/knowledge/test_byte_extraction.py",
    "tests/knowledge/test_chunk_budget.py",
    "tests/knowledge/test_library_responsiveness_offline.py",
}
ENGINE_PREFIXES = (
    "test_guarded_http_library_delivery_",
    "test_actual_rapidocr_parser_",
    "test_actual_cpu_segmented_library_",
    "test_actual_mem0_oss_outbox_rejects_go_without_assets_or_model_calls",
)
NATIVE_NAMES = {
    "test_actual_windows_dpapi_round_trip_is_profile_bound",
    "test_native_windows_dpapi_own_synthetic_key_and_wrong_namespace",
}
PRIORITY_FILES = {
    "tests/cases/test_images.py",
    "tests/runtime/test_cross_module_generation.py",
    "tests/runtime/test_images_context.py",
    "tests/learn/test_stream_errors.py",
}


def stamp():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")


class ReceiptFiles:
    """Pre-open only metadata outputs before tests install privacy guards.

    Application writes still use the original guarded APIs. These non-inherited
    handles belong solely to the recorder and never contain provider payloads.
    """

    NAMES = ("events.jsonl", "resources.jsonl", "inventory.json", "session.json",
             "outcomes.json", "module-sources.json", "result.json")

    def __init__(self, directory):
        self.streams = {name: (directory / name).open("xb") for name in self.NAMES}

    def json(self, name, value):
        stream = self.streams[name]
        stream.seek(0)
        stream.truncate()
        stream.write(json.dumps(value, indent=2, ensure_ascii=False).encode("utf-8"))
        stream.flush()

    def append(self, name, value):
        stream = self.streams[name]
        stream.write((json.dumps(value, ensure_ascii=False) + "\n").encode("utf-8"))
        stream.flush()

    def close(self):
        for stream in self.streams.values():
            stream.close()


def classify(nodeid):
    file, _, name = nodeid.replace("\\", "/").partition("::")
    if file.startswith("tests/regression/"):
        return "harness", "receipt integrity check; reported separately from product checks"
    if file == "tests/knowledge/test_acquired_offline.py":
        return "external_collection", "requires an acquired external collection; synthetic-only lane"
    if file in CAPACITY_FILES or name.startswith(CAPACITY_PREFIXES):
        return "capacity", "explicit large synthetic capacity fixture"
    if file in ENGINE_FILES or name.startswith(ENGINE_PREFIXES):
        return "engines", "actual helper/engine check; exclusive parent slot required"
    if name in NATIVE_NAMES:
        return "native", "dedicated Windows protection proof reserved for parent"
    return "application", "application regression; controlled seams are not engine acceptance"


def loopback(host):
    if host in ("localhost", b"localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def command_program(command):
    if isinstance(command, str):
        # Windows audit events contain a serialized command line. Classify
        # its executable without shell-parsing a Python -c program's quotes.
        prefix = re.match(r'\s*(?:"([^"]+)"|([^\s"]+))(?=\s|$)', command)
        return (prefix.group(1) or prefix.group(2)) if prefix else ""
    return command[0] if command else ""


class OfflineGuard:
    """Prevent external traffic, profile access and unreserved inference."""

    def __init__(self, scratch, allow_engines=False):
        self.scratch = scratch
        self.allow_engines = allow_engines
        self.violations = []
        self.private = Path("C:/Users/karol").resolve()
        # The shared public interpreter can be reached through a Windows
        # junction. Both its explicit alias and resolved dependency path are
        # read-only inputs; this does not admit the surrounding user profile.
        self.readable = tuple({path for root in (sys.prefix, sys.base_prefix)
                               for path in (Path(root).absolute(), Path(root).resolve())})

    def deny(self, message):
        self.violations.append({"utc": stamp(), "reason": message})
        raise AssertionError(message)

    def path(self, target):
        if isinstance(target, (str, bytes, os.PathLike)):
            return Path(os.fsdecode(target)).absolute()
        return None

    def address_allowed(self, address):
        return (isinstance(address, tuple) and len(address) >= 2
                and loopback(address[0]) and address[1] not in (8787, 5196))

    def audit(self, event, args):
        targets = []
        if event == "open":
            flags = args[2]
            if isinstance(flags, int) and flags & (
                os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
            ):
                targets = args[:1]
            else:
                self.check_read(args[0])
        elif event in ("os.listdir", "os.scandir") and args:
            self.check_read(args[0])
        elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime"):
            targets = args[:1]
        elif event in ("os.rename", "os.link", "os.symlink"):
            targets = args[:2]
        elif event == "socket.connect":
            address = args[1]
            if not self.address_allowed(address):
                self.deny("External socket forbidden in offline regression")
        elif event in ("socket.getaddrinfo", "socket.gethostbyname"):
            if not loopback(args[0]):
                self.deny("External DNS forbidden in offline regression")
        elif event == "subprocess.Popen":
            command = args[1]
            supplied = args[0] or command_program(command)
            executable = self.path(supplied)
            python = executable is not None and executable.resolve() == Path(sys.executable).resolve()
            read_git = False
            if not python:
                if isinstance(command, str):
                    try:
                        command = [part.strip('"') for part in shlex.split(command, posix=False)]
                    except ValueError:
                        command = []
                read_git = bool(command and len(command) > 1
                    and Path(str(supplied)).stem.lower() == "git"
                    and Path(str(command[0])).stem.lower() == "git"
                    and (command[1] in ("rev-parse", "describe", "log", "status", "show", "rev-list")
                        or command[1:3] == ["branch", "--show-current"]
                        or (command[1] == "tag" and "--list" in command[2:])))
            if not python and not read_git:
                self.deny("Only synthetic Python and read-only Git subprocesses allowed")
        for target in targets:
            path = self.path(target)
            if path and path != Path(os.devnull).absolute() and not path.is_relative_to(self.scratch):
                self.deny("Regression write outside fresh owned scratch: " + event + " " + str(path))

    def check_read(self, target):
        path = self.path(target)
        if path and path.is_relative_to(self.private) and not any(
            path.is_relative_to(root) for root in self.readable
        ):
            self.deny("Private user/profile access forbidden in regression: " + str(path))

    def install(self):
        sys.addaudithook(self.audit)
        # Windows Proactor ConnectEx need not emit socket.connect. Check the
        # asyncio connection entry points too, including numeric remote IPs.
        import asyncio
        original_connection = asyncio.BaseEventLoop.create_connection

        async def local_connection(loop, factory, host=None, port=None, *args, **kwargs):
            if host is not None and not self.address_allowed((host, port)):
                self.deny("External or parent-preview asyncio connection forbidden")
            return await original_connection(loop, factory, host, port, *args, **kwargs)

        asyncio.BaseEventLoop.create_connection = local_connection
        for kind in (asyncio.SelectorEventLoop, getattr(asyncio, "ProactorEventLoop", None)):
            if kind is None:
                continue
            original = kind.sock_connect

            async def local_sock_connect(loop, sock, address, _original=original):
                if not self.address_allowed(address):
                    self.deny("External or parent-preview asyncio socket forbidden")
                return await _original(loop, sock, address)

            kind.sock_connect = local_sock_connect
        if not self.allow_engines:
            sys.meta_path.insert(0, InferenceGuardFinder(self))


class InferenceGuardLoader(importlib.abc.Loader):
    def __init__(self, loader, names, guard):
        self.loader, self.names, self.guard = loader, names, guard

    def create_module(self, spec):
        return self.loader.create_module(spec)

    def exec_module(self, module):
        self.loader.exec_module(module)
        for name in self.names:
            def denied(*args, _name=module.__name__ + "." + name, **kwargs):
                self.guard.deny("Unreserved actual model/helper construction: " + _name)
            getattr(module, name).__init__ = denied


class InferenceGuardFinder(importlib.abc.MetaPathFinder):
    WATCH = {
        "onnxruntime": ("InferenceSession",),
        "fastembed.text.text_embedding": ("TextEmbedding",),
        "docling.pipeline.standard_pdf_pipeline": ("StandardPdfPipeline",),
    }

    def __init__(self, guard):
        self.guard = guard

    def find_spec(self, fullname, path=None, target=None):
        if fullname in self.WATCH:
            spec = importlib.machinery.PathFinder.find_spec(fullname, path)
            if spec and spec.loader:
                spec.loader = InferenceGuardLoader(spec.loader, self.WATCH[fullname], self.guard)
            return spec
        return None


class ReceiptPlugin:
    def __init__(self, scratch, guard, stage, floor):
        self.scratch, self.guard, self.stage, self.floor = scratch, guard, stage, floor
        self.items, self.reports, self.collection_errors = [], [], []
        self.minimum_free = shutil.disk_usage(scratch).free
        self.session = None
        self.files = ReceiptFiles(scratch)

    def append(self, filename, row):
        self.files.append(filename, row)

    def resource(self, nodeid=None):
        free = shutil.disk_usage(self.scratch).free
        self.minimum_free = min(self.minimum_free, free)
        self.append("resources.jsonl", {"utc": stamp(), "nodeid": nodeid, "free_bytes": free})
        return free

    def pytest_collection_modifyitems(self, config, items):
        seen, selected, excluded = set(), [], []
        for item in items:
            if item.nodeid in seen:
                raise AssertionError("Duplicate test identity: " + item.nodeid)
            seen.add(item.nodeid)
            category, reason = classify(item.nodeid)
            admitted = category == self.stage
            self.items.append({"nodeid": item.nodeid, "category": category,
                               "selected": admitted, "reason": reason})
            (selected if admitted else excluded).append(item)
        selected.sort(key=lambda item: item.nodeid.partition("::")[0] not in PRIORITY_FILES)
        self.files.json("inventory.json", {
            "collected": len(self.items), "selected": len(selected), "excluded": len(excluded),
            "items": self.items, "execution_order": [item.nodeid for item in selected],
        })
        config.hook.pytest_deselected(items=excluded)
        items[:] = selected

    def pytest_collectreport(self, report):
        if report.failed:
            self.collection_errors.append({"nodeid": report.nodeid, "failure": report.longreprtext})

    def pytest_runtest_setup(self, item):
        if self.resource(item.nodeid) < self.floor:
            import pytest
            pytest.exit("Disk reserve breached; regression incomplete", returncode=2)

    def pytest_runtest_logreport(self, report):
        row = {"utc": stamp(), "nodeid": report.nodeid, "when": report.when,
               "outcome": report.outcome, "duration": report.duration}
        if report.failed:
            row["failure"] = report.longreprtext
        if report.skipped:
            row["reason"] = str(report.longrepr)
        self.reports.append(row)
        self.append("events.jsonl", row)

    def pytest_sessionfinish(self, session, exitstatus):
        self.session = {"finished_utc": stamp(), "exitstatus": int(exitstatus),
                        "testscollected": session.testscollected, "testsfailed": session.testsfailed,
                        "minimum_free_bytes": self.minimum_free,
                        "collection_errors": self.collection_errors,
                        "guard_violations": self.guard.violations}
        self.files.json("session.json", self.session)

    def outcomes(self):
        phases = defaultdict(dict)
        for report in self.reports:
            phases[report["nodeid"]][report["when"]] = report
        rows = []
        for item in self.items:
            reports = phases[item["nodeid"]]
            if not item["selected"]:
                outcome = "excluded"
            elif any(row["outcome"] == "failed" for row in reports.values()):
                outcome = "failed"
            elif any(row["outcome"] == "skipped" for row in reports.values()):
                outcome = "skipped"
            elif set(reports) == {"setup", "call", "teardown"}:
                outcome = "passed"
            elif reports:
                outcome = "interrupted"
            else:
                outcome = "not_run"
            rows.append({**item, "outcome": outcome})
        return rows


def configure_environment(scratch):
    for name in list(os.environ):
        upper = name.upper()
        if upper.startswith(("RENULUS_", "HERMES_")) or any(
            tag in upper for tag in ("API_KEY", "ACCESS_TOKEN", "REFRESH_TOKEN", "AUTH_TOKEN")
        ) or upper in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN", "OPENAI_ORG_ID", "OPENAI_PROJECT_ID",
                       "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "ELECTRON_RUN_AS_NODE"):
            del os.environ[name]
    for name in ("temp", "cache/hf", "cache/torch", "cache/fastembed", "cache/mem0", "tokenizer",
                 "appdata", "localappdata", "cache/matplotlib"):
        (scratch / name).mkdir(parents=True)
    (scratch / "empty-gitconfig").write_text("", encoding="utf-8")
    os.environ.update({
        "PYTHONPATH": str(ROOT / "runtime"), "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        "PYTEST_ADDOPTS": "", "TEMP": str(scratch / "temp"), "TMP": str(scratch / "temp"),
        "TMPDIR": str(scratch / "temp"), "XDG_CACHE_HOME": str(scratch / "cache"),
        "APPDATA": str(scratch / "appdata"), "LOCALAPPDATA": str(scratch / "localappdata"),
        "MPLCONFIGDIR": str(scratch / "cache/matplotlib"),
        "HF_HOME": str(scratch / "cache/hf"), "HF_HUB_CACHE": str(scratch / "cache/hf/hub"),
        "HUGGINGFACE_HUB_CACHE": str(scratch / "cache/hf/hub"),
        "HF_MODULES_CACHE": str(scratch / "cache/hf/modules"),
        "TRANSFORMERS_CACHE": str(scratch / "cache/hf/transformers"),
        "TORCH_HOME": str(scratch / "cache/torch"),
        "FASTEMBED_CACHE_PATH": str(scratch / "cache/fastembed"),
        "MEM0_DIR": str(scratch / "cache/mem0"), "HF_HUB_OFFLINE": "1",
        "TRANSFORMERS_OFFLINE": "1", "HF_HUB_DISABLE_TELEMETRY": "1",
        "MEM0_TELEMETRY": "false", "ANONYMIZED_TELEMETRY": "false", "DO_NOT_TRACK": "1",
        "TOKENIZERS_PARALLELISM": "false", "RAYON_NUM_THREADS": "2", "OMP_NUM_THREADS": "2",
        "MKL_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2", "NUMEXPR_NUM_THREADS": "2",
        "GIT_OPTIONAL_LOCKS": "0", "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": str(scratch / "empty-gitconfig"),
        "HERMES_HOME": str(scratch / "synthetic-hermes"),
        "RENULUS_TEST_TOKENIZER": str(scratch / "tokenizer/tokenizer.json"),
    })
    sys.dont_write_bytecode = True
    tempfile.tempdir = str(scratch / "temp")
    # The reused environment has an editable-install path for its original
    # checkout. Remove that source override instead of admitting unowned reads
    # or accidentally testing the integration checkout's modules.
    private = Path("C:/Users/karol").resolve()
    dependencies = tuple({path for root in (sys.prefix, sys.base_prefix)
                          for path in (Path(root).absolute(), Path(root).resolve())})
    sys.path[:] = [entry for entry in sys.path if not entry
                   or not Path(entry).absolute().is_relative_to(private)
                   or any(Path(entry).absolute().is_relative_to(root) for root in dependencies)]
    sys.path.insert(0, str(ROOT / "runtime"))
    from tokenizers import Tokenizer, models, pre_tokenizers
    tokenizer = Tokenizer(models.WordLevel({"[UNK]": 0}, unk_token="[UNK]"))
    tokenizer.pre_tokenizer = pre_tokenizers.Whitespace()
    tokenizer.save(str(scratch / "tokenizer/tokenizer.json"))


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def receipt_result(plugin, exit_code, junit, clean_source):
    outcomes = plugin.outcomes()
    counts = dict(Counter(row["outcome"] for row in outcomes))
    selected = sum(row["selected"] for row in outcomes)
    complete = bool(selected and plugin.session and not plugin.collection_errors
                    and not counts.get("not_run") and not counts.get("interrupted")
                    and junit["valid"] and junit["cases"] == selected)
    return {"selected": selected, "outcomes": counts, "junit": junit,
            "complete": complete, "source_unchanged": clean_source,
            "accepted_stage_pass": complete and clean_source and exit_code == 0
                and counts.get("passed") == selected and not plugin.guard.violations}


def unexpected_module_sources(module_sources, root):
    root = root.resolve()
    runtime = root / "runtime"
    adopted = {
        "renulus.memory._vendored_hermes_backend":
            root / "upstream/hermes/plugins/memory/mem0/_backend.py",
    }
    return {name: path for name, path in module_sources.items()
            if not Path(path).resolve().is_relative_to(runtime)
            and adopted.get(name) != Path(path).resolve()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scratch", type=Path, required=True)
    parser.add_argument("--expect-commit", required=True)
    parser.add_argument("--stage", choices=("application", "capacity", "harness"), default="application")
    parser.add_argument("--reserve-gib", type=int, default=12)
    parser.add_argument("paths", nargs="*", default=["tests"])
    args = parser.parse_args(argv)
    if args.reserve_gib < 12:
        parser.error("The disk floor may not be reduced below 12 GiB")
    head = git("rev-parse", "HEAD")
    if head != args.expect_commit:
        parser.error("Worktree HEAD differs from the explicitly pinned commit")
    if git("status", "--porcelain", "--", "runtime", "content", "upstream/hermes", "packages",
           "packaging/runtime", "pyproject.toml", "uv.lock", "tests", "scripts/run_backend_regression.py"):
        parser.error("Tested sources, tests and runner must be clean before regression")
    scratch = args.scratch.resolve()
    if scratch.exists():
        parser.error("Scratch must be a fresh path; prior evidence is never reused or deleted")
    if not scratch.is_relative_to(Path("C:/rn-finalise-20261005").resolve()):
        parser.error("Use short fresh C:/rn-finalise-20261005 scratch")
    floor = args.reserve_gib * GIB
    free = shutil.disk_usage(scratch.parent).free
    if free < floor:
        parser.error("Insufficient disk reserve before scratch creation")
    scratch.mkdir()
    configure_environment(scratch)
    guard = OfflineGuard(scratch)
    plugin = ReceiptPlugin(scratch, guard, args.stage, floor)
    command = [*args.paths, "-q", "-ra", "--tb=short", "--durations=20",
               "-p", "no:cacheprovider", "-p", "pytest_asyncio.plugin",
               "--basetemp", str(scratch / "pt"), "--junitxml", str(scratch / "results.xml"),
               "-o", "faulthandler_timeout=120", "-o", "log_file=" + str(scratch / "internal.log")]
    run = {"source_commit": head, "branch": git("branch", "--show-current"),
           "source_status": git("status", "--short"), "scratch": str(scratch),
           "interpreter": sys.executable, "python_version": sys.version,
           "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
           "started_utc": stamp(), "pid": os.getpid(), "stage": args.stage,
           "pytest_arguments": command, "reserve_bytes": floor, "free_before": free,
           "cpu_threads": 2, "offline": True, "synthetic_profiles": True}
    run["source_trees"] = {name: git("rev-parse", "HEAD:" + name) for name in (
        "runtime", "upstream/hermes", "tests", "content", "packaging/runtime",
        "pyproject.toml", "uv.lock", "scripts/run_backend_regression.py")}
    run["package_versions"] = {name: importlib.metadata.version(name) for name in (
        "pytest", "pytest-asyncio", "fastapi", "pydantic", "httpx", "docling", "docling-core",
        "fastembed", "lancedb", "mem0ai", "qdrant-client", "onnxruntime", "tokenizers")}
    write_json(scratch / "run.json", run)
    print(json.dumps({"started_utc": run["started_utc"], "pid": run["pid"], "scratch": str(scratch)}),
          flush=True)
    # CPython 3.14's Windows platform.node() performs a read-only cmd /c ver
    # lookup. JUnit calls it at finalization. Resolve/cache real OS metadata
    # before the restricted test phase rather than permitting shell launch
    # inside application checks. No native application is launched.
    platform.uname()
    guard.install()
    started = time.monotonic()
    runtime_error = None
    try:
        import pytest
        exit_code = int(pytest.main(command, plugins=[plugin]))
    except BaseException as error:
        runtime_error = {"type": type(error).__name__, "message": str(error)}
        exit_code = 3
    outcomes = plugin.outcomes()
    plugin.files.json("outcomes.json", outcomes)
    xml = scratch / "results.xml"
    junit = {"exists": xml.is_file(), "valid": False, "cases": 0}
    if xml.is_file():
        try:
            junit.update(valid=True, cases=len(ET.parse(xml).findall(".//testcase")),
                         sha256=hashlib.sha256(xml.read_bytes()).hexdigest())
        except ET.ParseError:
            pass
    head_unchanged = git("rev-parse", "HEAD") == head
    production_unchanged = not git(
        "status", "--porcelain", "--", "runtime", "content", "upstream/hermes", "packages",
        "packaging/runtime", "pyproject.toml", "uv.lock")
    tests_and_runner_unchanged = not git(
        "status", "--porcelain", "--", "tests", "scripts/run_backend_regression.py")
    module_sources = {name: str(Path(module.__file__).resolve())
                      for name, module in tuple(sys.modules.items())
                      if name.startswith("renulus") and getattr(module, "__file__", None)}
    wrong_sources = unexpected_module_sources(module_sources, ROOT)
    plugin.files.json("module-sources.json", module_sources)
    clean_source = (head_unchanged and production_unchanged and tests_and_runner_unchanged
                    and not wrong_sources)
    result = {"finished_utc": stamp(), "source_commit": head,
              "elapsed_seconds": time.monotonic() - started, "exit_code": exit_code,
              **receipt_result(plugin, exit_code, junit, clean_source),
              "source_checks": {"head_unchanged": head_unchanged,
                                "production_unchanged": production_unchanged,
                                "tests_and_runner_unchanged": tests_and_runner_unchanged,
                                "unexpected_module_sources": wrong_sources},
              "runner_error": runtime_error,
              "minimum_free_bytes": plugin.minimum_free, "guard_violations": guard.violations}
    plugin.files.json("result.json", result)
    plugin.files.close()
    print(json.dumps(result), flush=True)
    return exit_code if result["complete"] and clean_source else 2


if __name__ == "__main__":
    raise SystemExit(main())
