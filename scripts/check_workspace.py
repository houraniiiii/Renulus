"""Check the clean Renulus workspace without reading runtime or private data."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = (
    "README.md", "AGENTS.md", ".gitignore", ".gitattributes",
    "docs/PROJECT_BRIEF.md", "docs/DECISIONS.md", "docs/SOURCES.md",
    "docs/WORKSPACE.md", "docs/CLEANUP.md", "docs/DESIGN_TOOLS.md",
    "THIRD_PARTY_NOTICES.md", "assets/brand/README.md",
    "assets/brand/renulus-master.png", "assets/brand/renulus.ico",
    "references/README.md", "references/taxonomy/README.md",
    "references/taxonomy/topics.jsonl", "references/taxonomy/subtopics.jsonl",
    "Start-Renulus.cmd", "scripts/start-renulus.ps1",
    "scripts/install-desktop-shortcut.ps1",
    ".agents/skills/impeccable/SKILL.md",
    ".agents/skills/interface-design/SKILL.md",
    ".claude/skills/impeccable/SKILL.md",
    ".claude/skills/interface-design/SKILL.md",
)


def git(*args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args], cwd=ROOT, input=input_text, capture_output=True,
        text=True, encoding="utf-8", errors="strict", check=False,
    )


def main() -> int:
    errors: list[str] = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    for relative in REQUIRED:
        require((ROOT / relative).is_file(), f"Missing required file: {relative}")

    remotes = git("remote")
    require(remotes.returncode == 0 and remotes.stdout.split() == ["origin"],
            "Renulus must have only its own origin remote.")
    for direction in ((), ("--push",)):
        origin = git("remote", "get-url", *direction, "origin")
        url = origin.stdout.strip().lower().removesuffix(".git")
        require(origin.returncode == 0 and url in {
            "https://github.com/houraniiiii/renulus",
            "git@github.com:houraniiiii/renulus",
        }, "Origin must point only to houraniiiii/Renulus.")
    sparse = git("config", "--bool", "--get", "core.sparseCheckout")
    require(sparse.returncode == 1 or sparse.stdout.strip() == "false",
            "The independent Renulus checkout must not inherit sparse-checkout rules.")
    require(not (ROOT / "src/nephro_engine").exists(),
            "The inherited batch engine belongs in the separate archive.")
    require(not (ROOT / "biomedical_synthetic_dataset_pipeline_v2").exists(),
            "The inherited research corpus belongs in the separate archive.")

    protected = (
        ".local/check.json", ".env", ".env.production",
        ".claude/settings.local.json", "data/unclassified.jsonl",
        "private/correspondence.pdf", "backend/.venv/Scripts/python.exe",
        "node_modules/example/package.json",
        ".agents/skills/impeccable/scripts/bin/windows-x64/impeccable.exe",
    )
    ignored = git("check-ignore", "--stdin", "-z", input_text=chr(0).join(protected) + chr(0))
    ignored_paths = set(ignored.stdout.split(chr(0)))
    for relative in protected:
        require(relative in ignored_paths, f"Missing ignore protection: {relative}")

    public_files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z")
    require(public_files.returncode == 0, "Could not enumerate publishable file names.")
    files = [name for name in public_files.stdout.split("\0") if name]
    for name in files:
        path = Path(name)
        components = set(path.parts)
        require(not components.intersection({".local", ".venv", "node_modules", "private"}) and path.parts[0] != "data",
                f"Local/private file must not be published: {name}")
        require(path.suffix.lower() not in {".exe", ".dll", ".db", ".sqlite", ".sqlite3", ".pem", ".key"},
                f"Runtime or private artifact must not be published: {name}")
        require(not path.name.startswith(".env") or path.name == ".env.example",
                f"Environment state must not be published: {name}")

    try:
        def rows(relative: str) -> list[dict[str, str]]:
            return [json.loads(line) for line in (ROOT / relative).read_text(encoding="utf-8-sig").splitlines() if line.strip()]

        topics = rows("references/taxonomy/topics.jsonl")
        subtopics = rows("references/taxonomy/subtopics.jsonl")
        require(len(topics) == 27 and len(subtopics) == 199, "Historical taxonomy counts changed; review provenance.")
        require(all(set(row) == {"topic_id", "topic"} and all(isinstance(v, str) for v in row.values()) for row in topics),
                "Topics must contain IDs and labels only.")
        require(all(set(row) == {"topic_id", "topic", "subtopic_id", "subtopic"} and all(isinstance(v, str) for v in row.values()) for row in subtopics),
                "Subtopics must contain IDs and labels only.")
        parents = {row["topic_id"]: row["topic"] for row in topics}
        require(len(parents) == len(topics), "Topic IDs must be unique.")
        require(len({row["subtopic_id"] for row in subtopics}) == len(subtopics), "Subtopic IDs must be unique.")
        require(all(parents.get(row["topic_id"]) == row["topic"] for row in subtopics),
                "Subtopic parent IDs and names must match the canonical topics.")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"Cannot validate the reviewed taxonomy: {type(exc).__name__}")

    link_count = 0
    for name in files:
        if not name.endswith(".md") or name.startswith((".agents/", ".claude/", ".codex/")):
            continue
        document = ROOT / name
        for match in re.finditer(r"!?\[[^\]]*\]\(([^\n)]+)\)", document.read_text(encoding="utf-8-sig")):
            target = match.group(1).strip().split(' "', 1)[0].strip("<>")
            if not target or target.startswith("#") or urlsplit(target).scheme:
                continue
            relative = unquote(target.split("#", 1)[0])
            resolved = (document.parent / relative).resolve()
            require(resolved.is_relative_to(ROOT), f"Local public link leaves the workspace: {name}: {target}")
            require(resolved.exists(), f"Broken local link: {name}: {target}")
            link_count += 1

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(f"PASS: Renulus origin and layout; {len(files)} public files; {link_count} local links; 27 topics and 199 subtopics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
