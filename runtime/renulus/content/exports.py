# SPDX-License-Identifier: MIT
"""Integrator-owned backup machinery may export only these public content tables."""

EXPORT_SCHEMA_VERSION = 1
EXPORT_TABLES = (
    "content_packs", "content_topics", "content_case_versions",
    "content_question_versions", "content_pack_topics", "content_pack_cases",
    "content_pack_questions", "content_active_pack",
    "content_question_withdrawals", "content_pack_withdrawals",
)

EXPORT_DESCRIPTION = {
    "module": "content", "schema_version": EXPORT_SCHEMA_VERSION,
    "tables": list(EXPORT_TABLES),
    "includes": "Original published CC BY 4.0 topics, cases, questions, manifests, public source citation metadata, activation and withdrawals.",
    "retention": "Retain immutable historical versions and reconcile newer withdrawals before reactivation.",
    "excludes": "User cases, documents, primary PDF/text, attempts, conversations, credentials and engine indexes.",
}
