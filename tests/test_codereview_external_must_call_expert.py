"""Positive-coverage tests asserting `external` mode MUST exercise the
expert-analysis path (hollow-ship-cleanup M-07 regression guard).

Symptom these tests catch:
    A future change re-introduces a silent skip of the expert call when
    `review_validation_type` is the default `"external"`. The PAL gate
    then returns PASS instantly with `tokens_used=0` and `model_used=""`
    — the hollow-gate failure mode documented in
    `claude-team-control/docs/REVIEW-hollow-ship-audit-2026-05-24.md`
    finding M-07.

These are unit-level invariants on `CodeReviewTool.should_skip_expert_analysis`.
They DO NOT spin up a full provider call (no API key, no network); the goal is
a tight regression guard at the decision point — if a future refactor flips
the predicate to return True for external + non-continuation requests,
this test fails.

Integration coverage that asserts a real provider IS invoked at the higher
level lives in test_workflow_metadata.py and test_precommit_workflow.py.
"""

from unittest.mock import MagicMock

import pytest

from tools.codereview import CodeReviewRequest, CodeReviewTool


def _make_request(
    *,
    validation_type: str = "external",
    next_step_required: bool = False,
    continuation_id: str | None = None,
) -> CodeReviewRequest:
    """Build a minimal CodeReviewRequest for the predicate under test."""

    return CodeReviewRequest(
        step="example",
        step_number=1,
        total_steps=1,
        next_step_required=next_step_required,
        findings="example findings",
        review_validation_type=validation_type,
        continuation_id=continuation_id,
    )


@pytest.fixture
def tool() -> CodeReviewTool:
    return CodeReviewTool()


def test_external_completed_must_call_expert(tool: CodeReviewTool) -> None:
    """A completed review (`next_step_required=False`) with the default
    `external` validation_type MUST NOT skip expert analysis.

    Regression guard: if a future refactor silently routes external mode
    through the skip path, this test fails immediately. The historical
    hollow-gate symptom (PAL PASS in <10s with tokens_used=0) was the
    operational outcome of exactly this bug class — see
    `claude-team-control/docs/REVIEW-hollow-ship-audit-2026-05-24.md`
    M-07.
    """

    req = _make_request(validation_type="external", next_step_required=False)
    consolidated = MagicMock(findings=[], files_checked=set(), relevant_files=set())

    assert tool.should_skip_expert_analysis(req, consolidated) is False, (
        "external + completed review MUST exercise the expert call; got skip=True"
    )


def test_external_in_progress_must_call_expert(tool: CodeReviewTool) -> None:
    """An in-progress review (`next_step_required=True`) with external
    validation_type also MUST NOT skip — the workflow will continue and
    expert analysis fires at the terminal step."""

    req = _make_request(validation_type="external", next_step_required=True)
    consolidated = MagicMock(findings=[], files_checked=set(), relevant_files=set())

    assert tool.should_skip_expert_analysis(req, consolidated) is False, (
        "external + in-progress review MUST exercise the expert call; got skip=True"
    )


def test_external_continuation_must_call_expert(tool: CodeReviewTool) -> None:
    """A continuation request (`continuation_id` set) with external
    validation_type MUST always call expert immediately, per the
    docstring contract in `CodeReviewTool.should_skip_expert_analysis`.
    """

    req = _make_request(
        validation_type="external",
        next_step_required=False,
        continuation_id="ext-cont-1",
    )
    consolidated = MagicMock(findings=[], files_checked=set(), relevant_files=set())

    assert tool.should_skip_expert_analysis(req, consolidated) is False, (
        "external continuation MUST always call expert; got skip=True"
    )


def test_internal_completed_correctly_skips_expert(tool: CodeReviewTool) -> None:
    """Sanity-pair to the positive cases: `internal` + completed IS the
    documented skip path. If this assertion ever reverses, both branches
    of the predicate are broken and the positive tests above will start
    silently passing for the wrong reason.
    """

    req = _make_request(validation_type="internal", next_step_required=False)
    consolidated = MagicMock(findings=[], files_checked=set(), relevant_files=set())

    assert tool.should_skip_expert_analysis(req, consolidated) is True, (
        "internal + completed review SHOULD skip expert (documented behaviour); predicate reversal detected"
    )


def test_default_validation_type_is_external(tool: CodeReviewTool) -> None:
    """The `review_validation_type` default MUST stay `external` so
    callers that omit the field land on the expert-call path (not the
    silent-skip internal path). If a future refactor flips the default,
    every caller suddenly starts skipping expert analysis — exactly the
    M-07 failure mode in production form.
    """

    req = CodeReviewRequest(
        step="example",
        step_number=1,
        total_steps=1,
        next_step_required=False,
        findings="example findings",
    )

    assert tool.get_review_validation_type(req) == "external", (
        "CodeReviewTool.get_review_validation_type default MUST be 'external';"
        " a change to 'internal' silently re-enables the hollow-gate bypass"
    )
