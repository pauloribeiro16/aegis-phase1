"""review.loader — load/save human review entries for adapted_objective.

The MAP stage writes LLM proposals to ``state.domain_results[D-XX]
["adapted_objective"]``. After MAP runs, the orchestrator seeds an
empty review file at ``<case_path>/review/adapted_objectives.yaml``
with one entry per domain, each in ``PENDING`` status. A human editor
then flips entries to ``APPROVED`` / ``EDITED`` / ``REJECTED``; on the
next pipeline run, ``doc_04b`` reads the YAML and renders each
domain's Adapted Objective section accordingly.

Entry schema (per domain ``D-XX``)::

    D-01:
      status: PENDING | APPROVED | EDITED | REJECTED
      llm_proposal: <original LLM output, kept for reference>
      edited_text: <human rewrite when status=EDITED, else empty>
      notes: <free-form reviewer note>

Status semantics:

* ``PENDING``  — not yet reviewed; doc renders LLM proposal with a
  ``[PENDING REVIEW]`` prefix.
* ``APPROVED`` — accepted as-is; doc renders LLM proposal unmodified.
* ``EDITED``   — human rewrite replaces the proposal in the doc; the
  proposal is preserved in ``llm_proposal`` for the audit trail.
* ``REJECTED`` — regenerate from scratch on a future pipeline run;
  doc renders LLM proposal with a ``[RE-GENERATION REQUIRED]`` prefix.

Functions:
    get_review_path(case_path) -> Path
    load_review(case_path) -> dict[str, dict]
    save_review(case_path, review) -> None
    seed_review(case_path, domain_results) -> dict[str, dict]
"""

from __future__ import annotations

from pathlib import Path

import yaml

_REVIEW_FILENAME = "adapted_objectives.yaml"


def get_review_path(case_path: str) -> Path:
    """Return the review YAML path for ``case_path``.

    Args:
        case_path: Path to the case directory
            (e.g. ``"cases/case1-tinytask"``).

    Returns:
        ``<case_path>/review/adapted_objectives.yaml``.
    """
    return Path(case_path) / "review" / _REVIEW_FILENAME


def load_review(case_path: str) -> dict[str, dict]:
    """Load the review YAML for ``case_path``.

    Returns an empty dict when the file does not exist (the common
    case before the first MAP run, or if the orchestrator never
    seeded the file). Existing YAML is parsed with
    :func:`yaml.safe_load` so untrusted data is not deserialised as
    Python objects.

    Args:
        case_path: Path to the case directory.

    Returns:
        Mapping from domain id (``"D-XX"``) to review entry dict.
    """
    p = get_review_path(case_path)
    if not p.exists():
        return {}
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    except yaml.YAMLError:
        return {}
    if not isinstance(raw, dict):
        return {}
    return raw


def save_review(case_path: str, review: dict[str, dict]) -> None:
    """Persist ``review`` to ``<case_path>/review/adapted_objectives.yaml``.

    Creates the parent ``review/`` directory if missing. The YAML is
    dumped with ``sort_keys=False`` to preserve iteration order and
    ``allow_unicode=True`` so non-ASCII review notes survive.

    Args:
        case_path: Path to the case directory.
        review: Mapping from domain id to review entry dict.
    """
    p = get_review_path(case_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        yaml.safe_dump(review, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def seed_review(
    case_path: str,
    domain_results: dict,
) -> dict[str, dict]:
    """Create ``PENDING`` review entries for every domain in ``domain_results``.

    Existing entries are preserved — only domains missing from the
    file are added. This makes the function idempotent and safe to
    call after every MAP run without clobbering human edits.

    Each new entry carries:

      * ``status`` — ``"PENDING"``
      * ``llm_proposal`` — the LLM-generated ``adapted_objective``
        (the textual section to be reviewed). The proposal is stored
        here so the reviewer can compare it against ``edited_text``
        later and so the audit trail is complete.
      * ``edited_text`` — empty string (filled by humans when status
        becomes ``EDITED``).
      * ``notes`` — empty string.

    Args:
        case_path: Path to the case directory.
        domain_results: Mapping from domain id (``"D-XX"``) to the
            :class:`DomainResult` dict produced by MAP.

    Returns:
        The full review mapping that was persisted (includes both
        newly-seeded and pre-existing entries).
    """
    existing = load_review(case_path)
    for domain_id, result in (domain_results or {}).items():
        if domain_id in existing:
            continue
        if not isinstance(result, dict):
            continue
        existing[domain_id] = {
            "status": "PENDING",
            "llm_proposal": str(result.get("adapted_objective", "") or ""),
            "edited_text": "",
            "notes": "",
        }
    save_review(case_path, existing)
    return existing


__all__ = [
    "get_review_path",
    "load_review",
    "save_review",
    "seed_review",
]
