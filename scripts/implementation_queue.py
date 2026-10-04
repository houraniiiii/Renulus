"""The authorised implementation queue and observable heartbeat; no credentials are read."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local" / "implementation-run.json"
REPO = "houraniiiii/Renulus"

TICKETS = [
    ("runtime", "Adopt Hermes and connect approved subscriptions",
     "Reuse a pinned attributed Hermes runtime. Implement app-owned connection/auth settings, exact model allowlists, capability detection, streaming/cancel and isolated profiles. Prove compatible selected-stack packages on Windows.",
     "Approved paths work; no hidden auxiliary fallback. Disconnected/unavailable states are honest. Synthetic cancel/retention checks pass. Live connection proof remains separate from test providers."),
    ("desktop", "Build the Flow desktop shell and managed backend",
     "Carry the user-selected Flow design into a working Electron/React app. Reuse suitable Hermes lifecycle code and the existing Flow artifacts. Establish tokens, accessible primitives, navigation and the real API client.",
     "The desktop and browser development route boot against the local backend. Loading/empty/error states work. No synthetic counts or prototype responses masquerade as live product state."),
    ("content", "Install original cross-domain learning packs",
     "Implement pack validation, versioned activation and original objectives, reviewed questions and teaching cases across nephrology. Record source/key review and CC BY 4.0 scope.",
     "A real pack activates transactionally; immutable versions and withdrawals are resolved correctly. Coverage/review gaps are visible. Reserved assessment items stay out of teaching retrieval."),
    ("learn", "Ask, explain, cancel and resume real study threads",
     "Implement direct/guided Explain with approved runtime generation, streaming, evidence references and persisted ordinary study threads. Case branches inherit temporary scope.",
     "Restart resumes a study thread; cancel/retry is accurate. Auth/quota/offline errors retain work. Temporary cases do not enter durable transcripts. No fake Ask response ships."),
    ("knowledge", "Import documents and retrieve cited evidence",
     "Use Docling/HybridChunker, FastEmbed and LanceDB for text/PDF/image ingestion and scoped hybrid retrieval. Consume authorised selected files and acquisition manifests; preserve external originals and rights.",
     "A completed revision retrieves passages with page/section locators. Replace/delete/cancel races retain valid previous state and remove stale derivatives. Real CPU extraction/embedding/index round trips are recorded."),
    ("cases", "Discuss temporary cases and explicitly save them",
     "Implement daily case discussion and staged original teaching cases. Temporary payloads and derivatives stay volatile; Save is explicit. Include real UI and persistence for saved cases.",
     "Synthetic temporary sentinel is absent from app-owned stores/logs/export after errors and mode handoffs. Saved cases resume after restart. Stages/reveals use installed content."),
    ("assessment", "Take reviewed tests and learn from deterministic feedback",
     "Implement committed answers, fixed question/key versions, deterministic scores, pause/resume and source-linked mistake review. Separate assisted/repeat/generated-practice records.",
     "Retries/restart do not double-score. Corrections annotate history; fresh/assisted/repeat aggregates stay separate. Coverage limits and reviewed versus generated roles are visible."),
    ("memory", "Capture and correct learner memory with Mem0 OSS",
     "Connect Hermes in-process Mem0 and embedded Qdrant with explicit FastEmbed to canonical learning records, durable eligible capture, scoped recall, edit/delete/reindex.",
     "Real evidence captures idempotently; correction/deletion removes derived text and Mem0 history. Case facts never enter personal memory. Approved generative route only; failure is retryable."),
    ("study", "Build home and an editable evidence-based study plan",
     "Connect Ask/Resume/review/updates home to real records. Schedule from objectives, committed attempts and preferences; allow manual changes and free topic exploration.",
     "A real mistake affects the proposed next study; manual edits survive restart. New-user home is useful. Chat volume is not displayed as mastery."),
    ("updates", "Check source currency and review educational updates",
     "Implement bounded official source/literature checks, last-success/failure dates, draft/final/replacement/correction/retraction states and reviewed update records linked to objectives.",
     "A changed eligible source is detected, deduplicated and reviewed before educational publication. Offline/stale states are accurate; source checks never transmit raw case details."),
    ("release", "Integrate, package and validate the Windows app",
     "Run cross-module journeys, migration/export/restore, retained-data deletion, Windows packaging and capability/coverage review. Record meaningful evidence and concrete remaining blockers.",
     "Runnable app and installer artifacts are delivered; relevant real journeys pass. Live-provider, clean-machine, signing and coverage gaps remain explicit when not proved. No deployment/provider cost incidental to checks."),
]


def gh(*args, json_output=False):
    result = subprocess.run(["gh", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(result.stderr.strip())
    return json.loads(result.stdout) if json_output else result.stdout.strip()


def issue(title, body):
    body_path = STATE.parent / "issue-body.md"
    body_path.write_text(body, encoding="utf-8")
    url = gh("issue", "create", "--repo", REPO, "--title", title, "--body-file", str(body_path))
    return {"number": int(url.rstrip("/").split("/")[-1]), "url": url}


def save(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2), encoding="utf-8")


def initialise():
    if STATE.exists():
        return json.loads(STATE.read_text(encoding="utf-8-sig"))
    STATE.parent.mkdir(parents=True, exist_ok=True)
    parent = issue("Renulus end-to-end implementation — Flow, parallel lanes and evidence",
        "User-authorised implementation run beginning 2026-10-04 19:21 UTC, targeting the next eight hours. Flow is selected. This issue is the live queue; plans remain flexible engineering baselines.\n\n"
        "Each vertical ticket owns code, behaviour and validation. Ready work starts in the next available lane. Dependencies govern integration, not speculative completion. Decisions, test evidence and concrete blockers go into the relevant ticket. Every 30 minutes a heartbeat records observed progress and next work.\n\n"
        "Foundation: pinned Hermes, Electron/React, canonical SQLite, Docling/HybridChunker, FastEmbed, LanceDB OSS and Hermes/Mem0 OSS/local Qdrant. Keep exact approved subscriptions/models, source terms and temporary-case retention. No fake responses, paid-provider usage, secret copying or restricted-source redistribution.\n\n"
        "See docs/implementation/EXECUTION.md on the integration branch. UI/source acquisition sessions retain ownership of their active work.")
    state = {"parent": parent, "started_utc": "2026-10-04T19:21:00+00:00",
             "deadline_utc": "2026-10-05T03:21:00+00:00", "active": True,
             "tickets": {}, "checkpoint": "Foundation code being established; runtime, desktop and content agents running."}
    save(state)
    for key, title, behaviour, acceptance in TICKETS:
        entry = issue(title, f"Part of #{parent['number']}.\n\n{behaviour}\n\nAcceptance: {acceptance}\n\n"
                     "Working agreements: isolated worktree and profile; disjoint owned paths; shared schema/dependency changes go through the integrator. Update this ticket with decisions, commits, checks and remaining limits. The initial description is adjustable when actual integration evidence warrants it.")
        entry["status"] = "in-progress" if key in ("runtime", "desktop", "content") else "ready"
        state["tickets"][key] = entry
        save(state)
    body_path = STATE.parent / "queue-comment.md"
    body_path.write_text("Live queue\n\n" + "\n".join(
        f"- {key}: #{entry['number']} — {entry['status']}" for key, entry in state["tickets"].items()),
        encoding="utf-8")
    gh("issue", "comment", str(parent["number"]), "--repo", REPO, "--body-file", str(body_path))
    return state


def heartbeat():
    state = json.loads(STATE.read_text(encoding="utf-8-sig"))
    if not state.get("active"):
        return {"status": "inactive"}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    log = subprocess.run(["git", "log", "-5", "--format=%h %s"], cwd=ROOT,
                         capture_output=True, text=True).stdout.strip()
    statuses = gh("issue", "list", "--repo", REPO, "--state", "all", "--limit", "100",
                  "--json", "number,title,state", json_output=True)
    ours = {entry["number"] for entry in state["tickets"].values()}
    lines = [f"### Heartbeat {now}", "", state.get("checkpoint", "No new checkpoint recorded."),
             "", "Observed integration commits:", "", "```", log, "```",
             "", "Ticket state:", ""]
    lines += [f"- #{row['number']}: {row['state']} — {row['title']}" for row in statuses if row["number"] in ours]
    lines += ["", "Open tickets require integration evidence before closure. This heartbeat records observed state; it does not assert unreported checks passed."]
    path = STATE.parent / "heartbeat.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    gh("issue", "comment", str(state["parent"]["number"]), "--repo", REPO, "--body-file", str(path))
    state["last_heartbeat_utc"] = now
    save(state)
    return {"status": "recorded", "at": now, "issue": state["parent"]["url"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("initialise", "heartbeat"))
    args = parser.parse_args()
    print(json.dumps(initialise() if args.action == "initialise" else heartbeat(), indent=2))
