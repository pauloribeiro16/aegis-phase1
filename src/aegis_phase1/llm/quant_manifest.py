"""Quantization manifest sidecar — CORR-111.

Each pulled/staged model on Deucalion gets a JSON sidecar that records:
  - model + provider
  - quantization in use (e.g. q4_K_M, fp8, provider_default)
  - provenance (ollama-pull | hf-stage | provider_default)
  - size + first-bytes sha256
  - timestamp

The sidecar lives next to the model (or under a manifests tree if the model
storage area is huge — see DEFAULT_MANIFEST_ROOT) and is the single source of
truth that the invoker + docs + digests consult to print "model @ quant".

Why this exists (see user feedback 2026-09-02):
  - Same model tag can exist in multiple quantizations (Q4_K_M, Q8_0, FP8, BF16,
    etc.). Comparing two scouts without knowing which quantization was active
    is meaningless.
  - Provider defaults are opaque: ollama pulls qwen3.5:27b as q4_K_M unless told
    otherwise, and we used to write "qwen3.5:27b" in digests — leaving the
    reader to guess. Now we record it explicitly.

No new dependencies — stdlib only (dataclasses, hashlib, json, pathlib).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

# Quantization tags we know about. Used only for validation/normalization
# (e.g. provider might return "Q4_K_M" or "Q4_K_m" — we lower-case and
# uppercase the K suffix consistently). New tags are NOT rejected.
_KNOWN_QUANTS = {
    "fp8", "fp16", "bf16", "q4_0", "q4_1",
    "q5_0", "q5_1", "q6_k", "q8_0",
    "q4_k_m", "q4_k_s", "q5_k_m", "q5_k_s",
    "q2_k", "q3_k_l", "q3_k_m", "q3_k_s",
    "iq1_s", "iq2_m", "iq2_xs", "iq3_xxs", "iq4_nl", "iq4_xs",
    "provider_default", "unknown",
}

# Where manifests live by default. Override via env var when runs are
# written to a different storage tree (so e.g. scout jobs on $SCRATCH
# don't pollute $HOME manifests).
DEFAULT_MANIFEST_ROOT = os.environ.get(
    "AEGIS_QUANT_MANIFEST_ROOT",
    # /home/<user>/aegis_quant_manifests/<provider>/<model>@<quant>.json
    str(Path.home() / "aegis_quant_manifests"),
)


def _normalize_quant_tag(raw: str | None) -> str:
    """Best-effort normalisation: 'Q4_K_M' / 'q4-k-m' / 'q4KM' → 'q4_k_m'.

    We DO NOT guess where the user forgot an underscore — that's a job for a
    catalog, and the GGUF/transformers tag space is small but quirky
    (q8_0 vs q4_K_S vs q3_K_L vs iq4_xs). Instead we:

      1. lowercase,
      2. replace ``-`` / space / ``.`` with ``_``,
      3. squash repeats,
      4. canonicalise a small set of well-known shapes ('q4km' → 'q4_k_m') by
         recognising the qq[NL]KM / qq[NL]_KM patterns.

    Anything unrecognised passes through (e.g. 'exl2@4bpw').
    """
    if raw is None:
        return "unknown"
    s = raw.strip().lower()
    s = s.replace("-", "_").replace(" ", "_").replace(".", "_")
    s = re.sub(r"_+", "_", s).strip("_")
    # Canonical insertion of underscore ONLY where the shape is unambiguous.
    # Pattern A: qq{N}{KM} family without separators  →  q4_km/q4_km_s/q4_km_l
    # Examples:  q4km → q4_k_m,  q4kms → q4_k_m_s
    s = re.sub(
        r"^q(\d)([kK])([mMsSlL])$", r"q\1_k_\3", s
    )
    s = re.sub(
        r"^q(\d)([kK])([mMsSlL])([smlSML])$", r"q\1_k_\3_\4", s
    )
    # Pattern B: iq{N}_{xnl|s|xs|...} already grouped; no-op.
    if s in _KNOWN_QUANTS:
        return s
    return s or "unknown"


def _slug_for_path(model: str) -> str:
    """Filesystem-safe slug from a model tag ('Qwen/Qwen3.8-Flash-Next').

    Keeps ``:`` (Ollama tag separator), ``.``, ``@``, ``+``, ``-`` as-is so
    common model names round-trip cleanly. Substitutes everything else with
    ``_``.
    """
    return re.sub(r"[^A-Za-z0-9._@+:-]", "_", model)


@dataclass
class QuantManifest:
    """Schema version 1 (CORR-111). Read/write JSON only via this class."""

    schema_version: int = 1
    model: str = ""                          # canonical tag, e.g. "nemotron-3.5-lightning:30b"
    provider: str = ""                       # "ollama" | "vllm" | "transformers" | "hf"
    quantization: str = "unknown"            # normalised tag (see _normalize_quant_tag)
    quantization_provenance: str = "provider_default"  # ollama-pull | hf-stage | provider_default | user-declared
    pulled_at: str = ""                      # ISO 8601 UTC, e.g. "2026-09-02T20:14:00Z"
    source: str = ""                         # registry URI or HF repo id
    size_bytes: int = 0
    digest_sha256: str = ""                  # sha256 of first N bytes (cheap, content-addressable enough)
    digest_method: str = "head-16MiB-sha256"
    vllm_compat: bool = False                # true if served by vLLM (AEGIS_VLLM_*) — affects "what counts as the quant"
    notes: str = ""

    def validate(self) -> list[str]:
        """Returns a list of human-readable issues; empty == OK.

        Not a fatal error in itself — leaves the choice to the caller. Used
        by tests and by the pull scripts to log warnings without halting.
        """
        issues: list[str] = []
        if not self.model:
            issues.append("model is empty")
        if self.provider not in {"ollama", "vllm", "transformers", "hf", "llamacpp"}:
            issues.append(f"provider {self.provider!r} is not a recognised value")
        if self.quantization == "unknown":
            issues.append("quantization is 'unknown' — run pull with --quantization explicitly")
        if self.quantization_provenance not in {
            "ollama-pull", "hf-stage", "provider_default", "user-declared", "vllm-served"
        }:
            issues.append(f"quantization_provenance {self.quantization_provenance!r} is not a recognised value")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", self.pulled_at):
            issues.append("pulled_at must be ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')")
        if self.size_bytes < 0:
            issues.append("size_bytes must be non-negative")
        return issues

    def manifest_path(self, root: str | os.PathLike[str] | None = None) -> Path:
        """Compute where this manifest should live on disk.

        Layout: <root>/<provider>/<model>@<quant>.json
        Collisions are resolved by appending -<n> before .json.
        """
        base = Path(root) if root else Path(DEFAULT_MANIFEST_ROOT)
        d = base / _slug_for_path(self.provider)
        d.mkdir(parents=True, exist_ok=True)
        name = f"{_slug_for_path(self.model)}@{self.quantization}.json"
        candidate = d / name
        if not candidate.exists():
            return candidate
        # collision — append -2, -3, ...
        stem = candidate.stem
        for i in range(2, 1000):
            c = d / f"{stem}-{i}.json"
            if not c.exists():
                return c
        return candidate  # fallback — should never happen with sane names

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True)

    @classmethod
    def from_json(cls, raw: str) -> QuantManifest:
        return cls(**json.loads(raw))


# ---------------------------------------------------------------------------
# Disk helpers
# ---------------------------------------------------------------------------


def head_sha256(path: str | os.PathLike[str], n_bytes: int = 16 * 1024 * 1024) -> str:
    """SHA-256 of the first ``n_bytes`` of a file (default 16 MiB).

    Cheap and stable across re-mounts; tells two-quant-apart snapshots apart
    without hashing the whole multi-GB blob. Not a content-addressable hash —
    intended only as a "this is the same file" marker.
    """
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read(n_bytes))
    return h.hexdigest()


def write_manifest(m: QuantManifest, root: str | os.PathLike[str] | None = None) -> Path:
    """Persist ``m`` to disk. Returns the path written.

    Logs any validation issues but does NOT raise by default — pass
    raise_on_warning=True to make it fatal.
    """
    if m.pulled_at == "":
        m.pulled_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues = m.validate()
    if issues and os.environ.get("AEGIS_QUANT_STRICT", "0") == "1":
        raise ValueError("manifest invalid: " + "; ".join(issues))
    p = m.manifest_path(root)
    p.write_text(m.to_json() + "\n", encoding="utf-8")
    return p


def load_manifest(path: str | os.PathLike[str]) -> QuantManifest:
    """Load a manifest from disk. Accepts the JSON written by ``write_manifest``."""
    return QuantManifest.from_json(Path(path).read_text(encoding="utf-8"))


def find_manifest(
    *,
    model: str,
    provider: str,
    quantization: str | None = None,
    root: str | os.PathLike[str] | None = None,
) -> QuantManifest | None:
    """Look up a manifest by model/provider(/quant). Returns the newest match.

    Walks the directory for any file matching the provider, then by model
    exact match. If ``quantization`` is given, filters on it too.
    """
    base = Path(root) if root else Path(DEFAULT_MANIFEST_ROOT)
    d = base / _slug_for_path(provider)
    if not d.is_dir():
        return None
    matches: list[QuantManifest] = []
    for fp in d.glob(f"{_slug_for_path(model)}@*.json"):
        try:
            m = load_manifest(fp)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
        if m.model != model or m.provider != provider:
            continue
        if quantization is not None and m.quantization != quantization:
            continue
        matches.append(m)
    if not matches:
        return None
    return max(matches, key=lambda m: m.pulled_at)


# ---------------------------------------------------------------------------
# Provider-specific helpers (best-effort, no network of their own)
# ---------------------------------------------------------------------------


def detect_ollama_quantization(
    model: str,
    *,
    ollama_models_root: str | os.PathLike[str] | None = None,
) -> str:
    """Best-effort quant probe for an Ollama model — never raises.

    Three paths, in order:

    1. ``ollama show <model> --json`` (graphify 0.32.13+).
    2. Plain ``ollama show <model>`` text (cluster-shipped 0.31.1, when
       a daemon is reachable).
    3. :func:`detect_ollama_quantization_via_blob` — reads the config
       blob on disk directly. No subprocess, no daemon needed. Last
       resort when 1+2 fail.

    Returns ``'unknown'`` on every error so the pipeline keeps moving.
    Optional: set ``AEGIS_QUANT_NO_PROBE=1`` to skip subprocess entirely.
    """
    if os.environ.get("AEGIS_QUANT_NO_PROBE", "0") == "1":
        return "unknown"

    # Path 1: --json (newer Ollama)
    try:
        out = subprocess.run(
            ["ollama", "show", model, "--json"],
            capture_output=True, text=True, timeout=10, check=False,
        )
        if out.returncode == 0 and out.stdout.strip().startswith("{"):
            try:
                data = json.loads(out.stdout)
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                info = data.get("model_info", {}) or {}
                for key in (
                    "general.quantization_version",
                    "quantization",
                    "general.file_type",
                    "format",
                ):
                    v = info.get(key) or data.get(key)
                    if isinstance(v, str) and v.strip():
                        return _normalize_quant_tag(v)
                family = info.get("general.architecture")
                if family:
                    return _normalize_quant_tag(family)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Path 2: plain text output (cluster-shipped 0.31.1).
    # The text contains a line like: ``    quantization        Q4_K_M    ``
    # inside the "Model" section. Parse it line-by-line; bail out on
    # anything that doesn't match the simple shape.
    try:
        out = subprocess.run(
            ["ollama", "show", model],
            capture_output=True, text=True, timeout=10, check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        # Path 3 below will try the blob.
        out = None
    if out is not None and out.returncode == 0:
        quant = _parse_ollama_show_text(out.stdout)
        if quant:
            return _normalize_quant_tag(quant)

    # Path 3 (CORR-111 follow-up): the cluster-shipped Ollama 0.31.1
    # also fails plain ``ollama show`` because it needs an active
    # daemon — but the model's config blob on disk has ``file_type`` set
    # by the CLI at pull time. Read it directly, no subprocess.
    return detect_ollama_quantization_via_blob(
        model, ollama_models_root=ollama_models_root
    )


def detect_ollama_quantization_via_blob(
    model: str,
    *,
    ollama_models_root: str | os.PathLike[str] | None = None,
) -> str:
    """Detect an Ollama model's quantization from the on-disk blob config.

    Skips ``ollama`` subprocesses entirely (no daemon needed — proven
    2026-09-03 when the cluster-shipped 0.31.1 has no ``--json`` and
    the plain-text ``ollama show`` returns ``unknown`` without an
    active server). Reads the manifest JSON + config blob that the
    Ollama CLI wrote at pull time, parses ``file_type`` from there.

    Layout (default for aegis-phase1 on Deucalion):

        <ollama_models_root>/manifests/registry.ollama.ai/library/<model>/<tag>
        <ollama_models_root>/blobs/sha256-<...>

    Caller can override ``ollama_models_root`` for non-Deucalion hosts.
    Returns ``'unknown'`` on every error so the pipeline keeps moving.

    Path 3 of :func:`detect_ollama_quantization`. Called automatically
    when both ``--json`` and ``ollama show`` fail.
    """
    root = Path(
        ollama_models_root
        or os.environ.get("OLLAMA_MODELS")
        or "/projects/F202512235CPCAA1/CyberMetric_Deucalion/ollama_data/models"
    )
    # Strip the :tag suffix — the manifest dir uses the bare name.
    bare = model.split(":", 1)[0]
    manifest_dir = root / "manifests" / "registry.ollama.ai" / "library" / bare
    if not manifest_dir.is_dir():
        return "unknown"

    # Pick the manifest file (subdir layout is one file per tag).
    manifest_files = sorted(p for p in manifest_dir.iterdir() if p.is_file())
    if not manifest_files:
        return "unknown"

    # If the user asked for a specific tag and it's present, use that;
    # otherwise default to the newest by mtime — matches what `ollama
    # show` would show for a bare name.
    wanted_tag = model.split(":", 1)[1] if ":" in model else None
    manifest_path: Path | None = None
    if wanted_tag:
        candidate = manifest_dir / wanted_tag
        manifest_path = candidate if candidate.is_file() else None
    if manifest_path is None:
        manifest_path = max(manifest_files, key=lambda p: p.stat().st_mtime)

    try:
        manifest = json.loads(manifest_path.read_text())
    except (json.JSONDecodeError, OSError):
        return "unknown"

    config_digest = manifest.get("config", {}).get("digest", "")
    if not config_digest.startswith("sha256:"):
        return "unknown"
    config_sha = config_digest[len("sha256:"):]
    config_blob = root / "blobs" / f"sha256-{config_sha}"
    if not config_blob.is_file():
        return "unknown"

    try:
        config = json.loads(config_blob.read_text())
    except (json.JSONDecodeError, OSError):
        return "unknown"

    file_type = config.get("file_type")
    if isinstance(file_type, str) and file_type.strip():
        return _normalize_quant_tag(file_type)
    return "unknown"


def _parse_ollama_show_text(text: str) -> str:
    """Return the quantization tag from plain-text ``ollama show`` output.

    Looks for ``  quantization        <TAG>  `` in the ``Model`` section.
    Returns ``""`` if no match.
    """
    in_model_section = False
    for line in text.splitlines():
        if line.strip().lower().startswith("model"):
            in_model_section = True
            continue
        if in_model_section and line.strip() and not line.startswith((" ", "\t")):
            # Left-aligned non-indented line ends the Model section.
            in_model_section = False
        if not in_model_section:
            continue
        stripped = line.strip()
        if stripped.lower().startswith("quantization"):
            parts = stripped.split()
            if len(parts) >= 2:
                return parts[-1]
    return ""


def build_from_ollama_pull(
    *,
    model: str,
    size_bytes: int = 0,
    source: str = "registry.ollama.ai",
    notes: str = "",
) -> QuantManifest:
    """Construct a manifest after a successful Ollama pull.

    Probes the model automatically for its quant; falls back to
    ``provider_default`` if unrecognised (per user decision 2026-09-02:
    declare the provider default when nothing else is known).
    """
    probed = detect_ollama_quantization(model)
    quant = probed if probed != "unknown" else "provider_default"
    return QuantManifest(
        model=model,
        provider="ollama",
        quantization=quant,
        quantization_provenance=("ollama-pull" if probed != "unknown" else "provider_default"),
        pulled_at=datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source=source,
        size_bytes=size_bytes,
        digest_sha256="",
        digest_method="not-hashed",
        vllm_compat=False,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Frontmatter helpers (used by invoker + renderers — Fase 2 + Fase 3)
# ---------------------------------------------------------------------------


def frontmatter_comment(
    *,
    model: str,
    provider: str,
    quant: str,
    job: str | int | None,
    spec: str,
    ts: str | None = None,
    extra: dict[str, str] | None = None,
) -> str:
    """Single-line HTML comment injected into per_spec_markdown outputs.

    Format: ``<!-- aegis:model="…" provider="…" quant="…" job="…" spec="…" ts="…" -->``
    Never user-visible in rendered outputs — renderers strip it (TODO Fase 3).
    """
    parts = [
        f'model="{_escape(model)}"',
        f'provider="{_escape(provider)}"',
        f'quant="{_escape(quant)}"',
        f'job="{_escape(str(job) if job is not None else "unknown")}"',
        f'spec="{_escape(spec)}"',
        f'ts="{_escape(ts or datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))}"',
    ]
    if extra:
        for k, v in extra.items():
            parts.append(f'{k}="{_escape(str(v))}"')
    return f"<!-- aegis:{' '.join(parts)} -->"


def _escape(s: str) -> str:
    # Replace '--' with U+2011 (NON-BREAKING HYPHEN) so an HTML comment is
    # not terminated by '--' appearing inside user-supplied content.
    return s.replace('"', "&quot;").replace("--", "\u2011\u2011")


def header_for_doc(*, model: str, quant: str, job: str | int | None) -> str:
    """Return the first line for Doc 01-09: ``Model: <model> @ <quant> (job <job>)``.

    Caveats are appended automatically when ``quant`` is "unknown" or
    "provider_default" — those are the two cases the reader must not miss.
    """
    base = f"Model: {model} @ {quant} (job {job})"
    if quant == "unknown":
        return base + "  [quant unknown — verify manifest]"
    if quant == "provider_default":
        return base + "  [quant = provider default — declare explicitly if reproducible]"
    return base


def resolve_quant_for(model: str | None, provider: str | None) -> dict[str, str]:
    """Resolve the active quant for a given (model, provider).

    Public helper used by:
      - :class:`Phase1LLMInvoker._current_quant` (CORR-061 legacy invoker)
      - the v2 orchestrator when populating
        ``state["v2_model_capabilities"]`` at run start.

    Returns a dict with keys ``model``, ``provider``, ``quantization``,
    ``quantization_provenance``, ``manifest_path``, ``job_id`` — all
    string fields, all populated, all explicit. Never raises.
    """
    if not model:
        model = "unknown"
    if not provider:
        provider = "unknown"

    quant = "unknown"
    provenance = "unknown"
    manifest_path = ""
    root = os.environ.get("AEGIS_QUANT_MANIFEST_ROOT") or None
    try:
        m = find_manifest(model=model, provider=provider, root=root)
    except Exception:  # never raise — pipeline must keep moving
        m = None
    if m is not None:
        quant = m.quantization
        provenance = m.quantization_provenance
        manifest_path = str(m.manifest_path())

    # Ollama silently defaults to q4_K_M (or whatever the tag ships with).
    # Per user decision 2026-09-02 — when we can't probe it, declare
    # provider_default rather than 'unknown'. vLLM and transformers users
    # MUST declare explicitly (we don't silently guess).
    if quant == "unknown" and provider == "ollama":
        quant = "provider_default"
        provenance = "provider_default"

    job_id = (
        os.environ.get("AEGIS_JOB_ID")
        or os.environ.get("SLURM_JOB_ID")
        or "unknown"
    )

    return {
        "model": model,
        "provider": provider,
        "quantization": quant,
        "quantization_provenance": provenance,
        "manifest_path": manifest_path,
        "job_id": job_id,
    }


__all__ = [
    "DEFAULT_MANIFEST_ROOT",
    "QuantManifest",
    "build_from_ollama_pull",
    "detect_ollama_quantization",
    "detect_ollama_quantization_via_blob",
    "find_manifest",
    "frontmatter_comment",
    "head_sha256",
    "header_for_doc",
    "load_manifest",
    "resolve_quant_for",
    "write_manifest",
]
