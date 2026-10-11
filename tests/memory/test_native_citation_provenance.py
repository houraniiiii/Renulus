# SPDX-License-Identifier: MIT
"""Public Memory contracts for reference-only native citation provenance.

The shared native_receipt helper stages a synthetic trusted native mapping and
answer; it does not prove Library source eligibility or SDK integration. These
tests publish real M5 lineage and check completed reference pins without answer
capture, native transport, inference engines or provider dispatch.
"""
from copy import deepcopy
import json

import pytest

from renulus.contracts import ApiError
from renulus.design_c_contracts import Dependency, EligibleInput, Identity

from .test_native_answer_lineage import finalize, native_receipt, stage_and_publish
from .test_study_answer_capture import study_capture


TEXT_LOCATORS = [
    {'item_ref': '#/texts/0', 'page': None, 'char_span': [0, 70]},
    {'item_ref': '#/texts/1', 'page': None, 'char_span': [72, 130]},
]
CANONICAL_LOCATORS = {
    'text': TEXT_LOCATORS,
    'pdf': [{'item_ref': '#/texts/0', 'page': 2, 'char_span': [0, 70],
        'bbox': {'l': 10.5, 't': 720.0, 'r': 200.0, 'b': 700.0,
            'coord_origin': 'BOTTOMLEFT'},
        'page_size': {'width': 612.0, 'height': 792.0},
        'content_locator': {'kind': 'pdf', 'physical_page': 2, 'printed_label': None}}],
    'image': [{'item_ref': '#/pictures/0', 'page': 1, 'char_span': [0, 70],
        'bbox': {'l': 20.0, 't': 30.0, 'r': 400.0, 'b': 300.0,
            'coord_origin': 'TOPLEFT'}, 'page_size': {'width': 640.0, 'height': 480.0},
        'content_locator': {'kind': 'image', 'frame': 1, 'bounds': [0.1, 0.2, 0.8, 0.9]}}],
    'docx': [{'item_ref': '#/texts/0', 'page': None, 'format': 'docx'}],
    'pptx': [{'item_ref': '#/texts/0', 'page': None, 'format': 'pptx',
        'slide': 3, 'char_span': [0, 70],
        'bbox': {'l': 10, 't': 20, 'r': 500, 'b': 150, 'coord_origin': 'TOPLEFT'},
        'slide_size': {'width': 1280, 'height': 720}}],
    'xlsx': [{'item_ref': '#/tables/0', 'table_ref': '#/tables/0',
        'page': None, 'format': 'xlsx', 'sheet': 2, 'sheet_name': 'CKD table',
        'cell_bbox': {'l': 1, 't': 1, 'r': 3, 'b': 2, 'coord_origin': 'TOPLEFT'},
        'content_locator': {'kind': 'table', 'format': 'xlsx', 'sheet_name': 'CKD table',
            'first_row': 1, 'last_row': 2, 'first_column': 1, 'last_column': 3}}],
}

# Literal adversarial source shapes: expected denials come from the public
# reference-only contract, not the implementation's validation helper.
MALFORMED_LOCATORS = {
    'body': [{'item_ref': '#/texts/0', 'body': 'Synthetic source body.'}],
    'path': [{'item_ref': '#/texts/0', 'path': 'C:/synthetic/source.pdf'}],
    'unknown-key': [{'item_ref': '#/texts/0', 'unrecognized': 1}],
    'nested-body': [{'content_locator': {'kind': 'text', 'body': 'Synthetic source body.'}}],
    'nested-path': [{'bbox': {'l': 0, 'path': 'C:/synthetic/source.pdf'}}],
    'nested-unknown-key': [{'page_size': {'width': 612, 'unrecognized': 1}}],
    'boolean-page': [{'page': True}],
    'string-page': [{'page': '2'}],
    'numeric-item-ref': [{'item_ref': 7}],
    'boolean-char-span': [{'char_span': [0, True]}],
    'string-char-span': [{'char_span': '0:70'}],
    'boolean-geometry': [{'bbox': {'l': True}}],
    'numeric-coordinate-origin': [{'bbox': {'coord_origin': 1}}],
    'string-frame': [{'content_locator': {'kind': 'image', 'frame': '1'}}],
    'boolean-bounds': [{'content_locator': {'bounds': [0.1, True, 0.8, 0.9]}}],
    'non-array': {'item_ref': '#/texts/0'},
    'non-object-entry': ['#/texts/0'],
}
# Canonical staged JSON cannot contain these numbers. Keep them at the public
# supplied-reference boundary rather than bypassing SQLite's JSON constraint.
NONFINITE_LOCATORS = {
    'infinite-geometry': [{'bbox': {'l': float('inf')}}],
    'nan-geometry': [{'bbox': {'l': float('nan')}}],
}


def cited_reference(reference, locators):
    cited = deepcopy(reference)
    cited['citations'] = [{'content_ref': {'target': {'type': 'library_revision',
        'id': 'rev_' + 'b' * 32}}, 'document_id': 'doc_' + 'a' * 32,
        'revision_id': 'rev_' + 'b' * 32, 'passage_id': 'passage_' + 'c' * 32,
        'locators': deepcopy(locators)}]
    return cited


def stage_citation_payload(conn, scope, reference, evidence_id):
    # Synthetic trusted fixture admission; all production assertions use the
    # public Memory service, not its private provenance/lineage validators.
    conn.execute('UPDATE learning_evidence SET payload_json=? WHERE id=?',
        (json.dumps({'scope': scope.model_dump(mode='json'),
            'answer_reference': reference}), evidence_id))


@pytest.mark.parametrize('locators', [pytest.param(value, id=name)
    for name, value in CANONICAL_LOCATORS.items()])
async def test_completed_native_citation_preserves_canonical_locators(native_receipt, services, locators):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    reference = cited_reference(reference, locators)
    try:
        with services.db.transaction() as conn:
            stage_citation_payload(conn, scope, reference, evidence_id)
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
        expected = (EligibleInput(kind='committed_evidence', dependency=Dependency(
            target=Identity(type='learning_evidence', id=evidence_id),
            expected_revision=publication)),)
        with services.db.transaction() as conn:
            assert memory.eligible_answer_references_in(conn, (reference,)) == expected
            altered = deepcopy(reference)
            altered['citations'][0]['locators'][0]['item_ref'] = '#/texts/another'
            assert memory.eligible_answer_references_in(conn, (altered,)) == ()
        assert control.calls == []
    finally:
        await memory.close()


@pytest.mark.parametrize('locators', [pytest.param(value, id=name)
    for name, value in MALFORMED_LOCATORS.items()])
async def test_native_publication_rejects_malformed_citation_provenance(native_receipt, services, locators):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    reference = cited_reference(reference, locators)
    try:
        with pytest.raises(ApiError) as rejected:
            with services.db.transaction() as conn:
                stage_citation_payload(conn, scope, reference, evidence_id)
                stage_and_publish(conn, memory, run, reference, evidence_id)
        assert rejected.value.code == 'memory_answer_reference'
        with services.db.transaction() as conn:
            assert memory.eligible_answer_references_in(conn, (reference,)) == ()
        assert control.calls == []
    finally:
        await memory.close()


async def test_completed_reference_excludes_malformed_locator_claims(native_receipt, services):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    reference = cited_reference(reference, TEXT_LOCATORS)
    try:
        with services.db.transaction() as conn:
            stage_citation_payload(conn, scope, reference, evidence_id)
            publication = stage_and_publish(conn, memory, run, reference, evidence_id)
            finalize(conn, run, publication)
        with services.db.transaction() as conn:
            for name, locators in {**MALFORMED_LOCATORS, **NONFINITE_LOCATORS}.items():
                supplied = deepcopy(reference)
                supplied['citations'][0]['locators'] = deepcopy(locators)
                assert memory.eligible_answer_references_in(conn, (supplied,)) == (), name
            assert memory.eligible_answer_references_in(conn, (reference,))
        assert control.calls == []
    finally:
        await memory.close()


async def test_native_publication_rejects_oversized_reference_only_receipt(native_receipt, services):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    reference = cited_reference(reference, [TEXT_LOCATORS[0]] * 1500)
    assert len(json.dumps(reference).encode('utf-8')) > 65536
    try:
        with pytest.raises(ApiError) as rejected:
            with services.db.transaction() as conn:
                stage_citation_payload(conn, scope, reference, evidence_id)
                stage_and_publish(conn, memory, run, reference, evidence_id)
        assert rejected.value.code == 'memory_answer_reference'
        assert control.calls == []
    finally:
        await memory.close()


@pytest.mark.parametrize('count', [100, 101])
async def test_native_citation_count_obeys_receipt_budget(native_receipt, services, count):
    _, memory, control, run, reference, evidence_id, scope = native_receipt
    reference = cited_reference(reference, TEXT_LOCATORS)
    reference['citations'] = deepcopy(reference['citations']) * count
    assert len(json.dumps(reference).encode('utf-8')) < 65536
    try:
        if count == 100:
            with services.db.transaction() as conn:
                stage_citation_payload(conn, scope, reference, evidence_id)
                publication = stage_and_publish(conn, memory, run, reference, evidence_id)
                finalize(conn, run, publication)
            with services.db.transaction() as conn:
                assert memory.eligible_answer_references_in(conn, (reference,))
        else:
            with pytest.raises(ApiError) as rejected:
                with services.db.transaction() as conn:
                    stage_citation_payload(conn, scope, reference, evidence_id)
                    stage_and_publish(conn, memory, run, reference, evidence_id)
            assert rejected.value.code == 'memory_answer_reference'
        assert control.calls == []
    finally:
        await memory.close()
