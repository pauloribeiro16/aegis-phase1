"""Run metadata reproducibility snapshot (CORR-OBJ-14).

OBJECTIVES_CONTRACT §2.2 — OBJ-14 [H] "Reproducibility / comparability:
same input + model + specs → comparable outputs across runs and models".

This module is the **contract half** of OBJ-14 — the dataclass that
captures every parameter that affects LLM output, so that two runs can
be declared "comparable" or "not comparable" deterministically.

The judge half lives in ``scripts/eval/rubric.py:obj14_*`` (scaffold)
and in the no-regression rule baked into
``scripts/eval/check_gate.py``.

Design
------

* A :class:`RunMetadata` is a frozen dataclass. Every field is required
  (no ``None``) so that two runs with different providers / specs cannot
  share a hash.
* :func:`from_env` builds a RunMetadata from environment variables +
  CLI args, so the orchestrator can call it once at the start of a run.
* :meth:`RunMetadata.to_dict` and :meth:`RunMetadata.hash` are
  deterministic: same inputs → same output bytes.
* :func:`validate_gate_mode` rejects any ``AEGIS_GATE_MODE`` other than
  ``"warn"`` or ``"hard"`` (the canonical pair from the contract).

Why a dataclass and not a Pydantic model
----------------------------------------

Pydantic adds a non-trivial dependency on its own encoder; we want
``hash()`` to be a pure-Python ``hashlib.sha256`` of the canonical
``to_dict()`` JSON so reviewers can re-compute the hash in any language.
A ``@dataclass(frozen=True)`` is the simplest container that gives us
this property.
"""
from __future__ import annotations

import hashlib
import json
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

# The closed list of acceptable ``AEGIS_GATE_MODE`` values.
# Anything else is rejected at run start so the no-regression rule
# (OBJECTIVES_CONTRACT §5) can rely on the gate having well-defined
# semantics. Reference: ``invoker.py`` reads the same env var.
VALID_GATE_MODES: frozenset[str] = frozenset({"warn", "hard"})


class InvalidGateModeError(ValueError):
    """Raised when ``AEGIS_GATE_MODE`` is not in :data:`VALID_GATE_MODES`."""


def validate_gate_mode(value: str | None) -> str:
    """Normalise + validate ``AEGIS_GATE_MODE``.

    * If ``value`` is ``None``, the env-var unset case, returns
      ``"warn"`` (the interactive-development default per
      OBJECTIVES_CONTRACT §5.1).
    * If ``value`` is in :data:`VALID_GATE_MODES`, returns it lowercased.
    * Otherwise raises :class:`InvalidGateModeError` with a clear message.

    The check is case-insensitive (``"HARD"`` and ``"Hard"`` are accepted
    but normalised to ``"hard"``) so that shell env-var casing cannot
    silently bypass the contract.
    """
    if value is None:
        return "warn"
    normalised = value.strip().lower()
    if normalised not in VALID_GATE_MODES:
        raise InvalidGateModeError(
            f"Invalid AEGIS_GATE_MODE={value!r}. "
            f"Must be one of: {sorted(VALID_GATE_MODES)}"
        )
    return normalised


@dataclass(frozen=True)
class RunMetadata:
    """Immutable metadata for a single AEGIS Phase 1 run.

    Two runs with the same field values produce the same ``hash()`` and
    the same ``to_dict()`` JSON; any difference in any field produces a
    different hash. This is the substrate for OBJ-14.

    Attributes:
        run_id: Stable, unique identifier for this run (e.g. UUID4).
        case_id: Case identifier (e.g. ``"case1-tinytask"``).
        model: Model name as reported by the provider (e.g.
            ``"gemma4:e4b"``).
        provider: Provider key (e.g. ``"ollama"``, ``"transformers"``,
            ``"minimax"``).
        quantization: Model quantization string (e.g. ``"Q4_K_M"``) or
            ``"unknown"`` if the provider does not report it.
        spec_versions: Mapping of spec_id -> version (e.g.
            ``{"P1B-LLM-01-INTERPRETATION": "1.0.0"}``).
        gate_mode: Either ``"warn"`` or ``"hard"`` (closed vocabulary;
            see :data:`VALID_GATE_MODES`).
        started_at: ISO-8601 UTC timestamp of run start.
        ended_at: ISO-8601 UTC timestamp of run end (or ``""`` if not
            yet finished; the orchestrator fills this in at the end).
    """

    run_id: str
    case_id: str
    model: str
    provider: str
    quantization: str
    spec_versions: dict[str, str]
    gate_mode: str
    started_at: str
    ended_at: str = ""

    def __post_init__(self) -> None:
        # Re-validate gate_mode so direct construction also enforces the
        # closed vocabulary (in addition to ``from_env``).
        normalised = validate_gate_mode(self.gate_mode)
        if normalised != self.gate_mode:
            object.__setattr__(self, "gate_mode", normalised)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable dict with keys in stable order.

        ``spec_versions`` is sorted by key for byte-stable output. The
        top-level dict ordering is the dataclass field order.
        """
        d = asdict(self)
        d["spec_versions"] = dict(sorted(self.spec_versions.items()))
        return d

    def to_json(self, *, indent: int | None = None) -> str:
        """Return a canonical JSON string. Stable across runs / platforms."""
        return json.dumps(self.to_dict(), sort_keys=False, indent=indent, ensure_ascii=False)

    def hash(self) -> str:
        """Return the SHA-256 hex digest of the canonical JSON form.

        Two ``RunMetadata`` instances with identical field values produce
        identical hashes on any platform. Any change to any field
        produces a different hash (SHA-256 avalanche property).
        """
        canonical = json.dumps(
            self.to_dict(), sort_keys=False, ensure_ascii=False, separators=(",", ":"),
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # Convenience aliases

    def is_comparable_to(self, other: RunMetadata) -> bool:
        """Return True iff this run is comparable to ``other``.

        Two runs are comparable iff they share case_id, model, provider,
        quantization, spec_versions, and gate_mode. The run_id and
        timestamps are excluded (they identify the run, not the
        configuration).
        """
        return (
            self.case_id == other.case_id
            and self.model == other.model
            and self.provider == other.provider
            and self.quantization == other.quantization
            and self.spec_versions == other.spec_versions
            and self.gate_mode == other.gate_mode
        )

    @staticmethod
    def diff_fields(a: RunMetadata, b: RunMetadata) -> dict[str, tuple[Any, Any]]:
        """Return a dict of fields that differ between ``a`` and ``b``.

        Useful for human review when ``is_comparable_to`` returns False.
        """
        a_d = a.to_dict()
        b_d = b.to_dict()
        return {
            k: (a_d[k], b_d[k])
            for k in a_d
            if a_d[k] != b_d[k]
        }


# ────────────────────────────────────────────────────────────────────
# Factory: build from env + args
# ────────────────────────────────────────────────────────────────────


def from_env(
    *,
    run_id: str,
    case_id: str,
    model: str,
    provider: str,
    quantization: str = "unknown",
    spec_versions: dict[str, str] | None = None,
    started_at: str | None = None,
    ended_at: str = "",
) -> RunMetadata:
    """Build a :class:`RunMetadata` from explicit kwargs + env-var fallback.

    ``AEGIS_GATE_MODE`` is read from the environment unless ``gate_mode``
    is supplied via the keyword args. The factory validates
    ``AEGIS_GATE_MODE`` via :func:`validate_gate_mode` and raises
    :class:`InvalidGateModeError` on an invalid value, so the no-
    regression rule (OBJECTIVES_CONTRACT §5) cannot be bypassed by a
    typo in the env-var.
    """
    gate_mode_env = os.getenv("AEGIS_GATE_MODE")
    gate_mode = validate_gate_mode(gate_mode_env)
    return RunMetadata(
        run_id=run_id,
        case_id=case_id,
        model=model,
        provider=provider,
        quantization=quantization,
        spec_versions=dict(spec_versions or {}),
        gate_mode=gate_mode,
        started_at=started_at or datetime.now(UTC).isoformat(),
        ended_at=ended_at,
    )


__all__ = [
    "VALID_GATE_MODES",
    "InvalidGateModeError",
    "RunMetadata",
    "from_env",
    "validate_gate_mode",
]
