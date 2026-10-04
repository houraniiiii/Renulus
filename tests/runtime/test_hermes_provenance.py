import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def test_relocated_markers_preserve_acquired_values_and_documented_source_hashes():
    root = Path(__file__).resolve().parents[2]
    provenance = json.loads((root / "packaging/runtime/hermes-source.json").read_text(encoding="utf-8"))
    patch = next(row for row in provenance["patches"] if row["id"] == "R002")
    for record in patch["paths"]:
        assert hashlib.sha256((root / record["path"]).read_bytes()).hexdigest() == record["patched_sha256"]
    path = root / "upstream/hermes/agent/conversation_markers.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    markers = {node.targets[0].id: ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign)}
    assert len(markers) == patch["unchanged_marker_count"] == 9
    canonical = json.dumps(markers, sort_keys=True, separators=(",", ":")).encode()
    assert hashlib.sha256(canonical).hexdigest() == patch["marker_values_sha256"]
    loop = ast.parse((root / "upstream/hermes/agent/conversation_loop.py").read_text(encoding="utf-8"))
    imports = [node for node in loop.body if isinstance(node, ast.ImportFrom) and node.module == "agent.conversation_markers"]
    assert len(imports) == 1 and {item.name for item in imports[0].names} == set(markers)


def test_memory_trim_opt_out_is_context_local_and_keeps_upstream_defaults(app_paths, monkeypatch):
    from contextvars import Context
    from renulus.runtime.hermes import HermesSubscriptionTransport
    transport = HermesSubscriptionTransport(app_paths.source_root, app_paths.root)
    with transport.controlled():
        from hermes_cli import mem_trim
    calls = []
    def settings():
        calls.append(True)
        return False, 60, 1, 0
    monkeypatch.setattr(mem_trim, "_config_settings", settings)
    with transport.controlled():
        assert mem_trim.trim_memory() is False and not calls
        assert Context().run(mem_trim.trim_memory) is False and len(calls) == 1
        assert mem_trim.trim_memory() is False and len(calls) == 1
    assert mem_trim.trim_memory() is False and len(calls) == 2


def test_cold_hermes_context_does_not_create_native_state_or_log_files(app_paths):
    script = r'''
import json, os, sys
from pathlib import Path
from renulus.storage import AppPaths
from renulus.runtime.context import HermesContextAdapter
from renulus.runtime.hermes import HermesSubscriptionTransport
from renulus.runtime.startup import HelperStartup
paths = AppPaths.create(Path(sys.argv[1]), Path(sys.argv[2]))
startup = HelperStartup(paths, None)
startup.configure()
transport = HermesSubscriptionTransport(paths.source_root, paths.root)
context = HermesContextAdapter(transport)
writes = []
def audit(event, args):
    if event == "open":
        flags = args[2]
        if not isinstance(flags, int) or not flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            return
    elif event not in ("os.mkdir", "os.remove", "os.rmdir", "os.link", "os.symlink", "os.rename"):
        return
    writes.append(event)
    raise RuntimeError("no-write context boundary")
sys.addaudithook(audit)
content = "SYNTHETIC_CONTEXT_SENTINEL; CKD dialysis transplantation glomerular electrolyte. " * 40
messages = [{"role":"user" if index % 2 == 0 else "assistant", "content": content} for index in range(40)]
messages.append({"role":"user", "content":"Review dialysis learning next."})
plan = context.plan(messages, provider="opencode-go", model="mimo-v2.6-pro", force=True)
assert plan.turns
result = context.finish(plan, "Synthetic approved-route summary supplied by test: CKD and transplant learning.")
assert result["compacted"] and result["messages"][-1] == messages[-1]
assert not writes and "agent.conversation_loop" not in sys.modules and "hermes_logging" not in sys.modules
print(json.dumps({"writes":writes, "compacted":result["compacted"]}))
startup.close()
'''
    environment = dict(os.environ, PYTHONPATH=str(app_paths.source_root / "runtime"), PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-c", script, str(app_paths.root), str(app_paths.source_root)],
        capture_output=True, text=True, env=environment, timeout=30)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"writes": [], "compacted": True}
