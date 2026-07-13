"""Loads v1.2 deterministic catalogs (YAML) and evaluates predicates.

Catalogs:
  - tipo2_interpretations.yaml   (8 Berry Tipo 2 entries)
  - tipo3_derogations.yaml       (6 Berry Tipo 3 entries)
  - scope_overlap_predicates.yaml (Layer 0 CONDITIONAL predicates)
  - event_templates.yaml         (compound event templates)

Usage:
    cl = CatalogLoader()
    tipo2 = cl.load("tipo2_interpretations")
    gdpr_entries = cl.filter_applicable(tipo2, regulation="GDPR")
    activated = cl.evaluate_predicates(gdpr_entries, company_facts)
"""

from __future__ import annotations

import re
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml


class CatalogLoadError(RuntimeError):
    """Raised when a catalog cannot be loaded."""


class CatalogLoader:
    """Loads YAML catalogs and filters/evaluates them.

    Attributes:
        root: Path to PROMPTS/catalogs/ directory
    """

    def __init__(self, root: Path | None = None) -> None:
        if root is None:
            # Sibling: ../../../Methodology-main/00_METHODOLOGY/PROMPTS/catalogs
            root = (
                Path(__file__).parent.parent.parent.parent.parent
                / "Methodology-main"
                / "00_METHODOLOGY"
                / "PROMPTS"
                / "catalogs"
            )
        self.root = Path(root)
        if not self.root.exists():
            raise CatalogLoadError(f"Catalogs directory does not exist: {self.root}")

    def load(self, catalog_name: str) -> list[dict[str, Any]]:
        """Load a catalog by name (without .yaml extension).

        Returns list of catalog entries (each is a dict).
        """
        path = self.root / f"{catalog_name}.yaml"
        if not path.exists():
            raise CatalogLoadError(f"Catalog not found: {path}")
        text = path.read_text(encoding="utf-8")
        data = self._load_yaml_with_frontmatter(text)
        if not isinstance(data, list):
            raise CatalogLoadError(
                f"Catalog {catalog_name} expected list, got {type(data).__name__}"
            )
        return data

    @staticmethod
    def _load_yaml_with_frontmatter(text: str) -> Any:
        """Load YAML from a catalog file that has frontmatter + markdown body +
        a fenced ```` ```yaml ... ``` ```` code block containing the entry list.

        Strategy:
          1. Skip the leading `--- ... ---` frontmatter block.
          2. Find the first fenced ```yaml``` code block in the body.
          3. Parse that block as YAML; if it yields a list, return it.
          4. Fallback: parse the whole body as YAML.
        """
        # Step 1: Skip frontmatter — locate the closing '---' delimiter.
        lines = text.splitlines(keepends=False)
        body_start = 0
        dashes_seen = 0
        for i, line in enumerate(lines):
            if line.strip() == "---":
                dashes_seen += 1
                if dashes_seen == 2:
                    body_start = i + 1
                    break
        body = "\n".join(lines[body_start:])

        # Step 2: Extract ALL ```yaml ... ``` fenced code blocks; pick the
        # one with the most list entries (schema is typically 1 entry; data
        # has 5+ entries).
        yaml_blocks = re.findall(r"```yaml\s*\n(.*?)\n```", body, re.DOTALL)
        if yaml_blocks:
            best: list[dict[str, Any]] | None = None
            best_size = 0
            for block in yaml_blocks:
                try:
                    data = yaml.safe_load(block)
                    if isinstance(data, list) and len(data) > best_size:
                        best = data
                        best_size = len(data)
                except yaml.YAMLError:
                    continue
            if best is not None:
                return best

        # Step 3: Fallback — parse the whole body as YAML.
        try:
            return yaml.safe_load(body)
        except yaml.YAMLError:
            return None

    def filter_applicable(
        self,
        catalog: list[dict[str, Any]],
        regulation: str,
        tier: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return entries whose `applies_to` includes the given regulation.

        If `tier` is provided, also filter by `tier_required` (None means any tier).
        """
        out = []
        for entry in catalog:
            applies = entry.get("applies_to", [])
            if regulation not in applies and "*" not in applies:
                continue
            tier_req = entry.get("tier_required")
            if tier_req is not None and tier is not None and tier not in tier_req:
                continue
            out.append(entry)
        return out

    def evaluate_predicate(
        self,
        predicate: str,
        company_facts: dict[str, Any],
    ) -> bool | None:
        """Evaluate a Python-like predicate string against company_facts.

        Returns:
            True / False if evaluation succeeded.
            None if predicate references unknown names (INSUFFICIENT_EVIDENCE).

        Examples:
            >>> cl.evaluate_predicate("company_facts.sector == 'health'", {"sector": "health"})
            True
            >>> cl.evaluate_predicate("company_facts.missing_var == 1", {})
            None
        """
        if not predicate or not predicate.strip():
            return True
        # Convert dict to SimpleNamespace so attribute access (company_facts.sector)
        # works on plain dicts. Nested dicts are also converted recursively so
        # predicates like company_facts.nested.field work.
        facts_ns = self._dict_to_namespace(company_facts)
        try:
            return bool(
                eval(
                    predicate,
                    {"__builtins__": {}},
                    {"company_facts": facts_ns},
                )
            )
        except NameError:
            return None
        except (KeyError, AttributeError):
            return None
        except Exception:
            return None

    @staticmethod
    def _dict_to_namespace(obj: Any) -> Any:
        """Recursively convert dicts to SimpleNamespace so attribute access works."""
        if isinstance(obj, dict):
            return SimpleNamespace(**{k: CatalogLoader._dict_to_namespace(v) for k, v in obj.items()})
        if isinstance(obj, list):
            return [CatalogLoader._dict_to_namespace(item) for item in obj]
        return obj

    def evaluate_predicates(
        self,
        entries: list[dict[str, Any]],
        company_facts: dict[str, Any],
        predicate_field: str = "activation_predicate",
    ) -> list[tuple[dict[str, Any], bool | None]]:
        """Evaluate `predicate_field` for each entry.

        Returns list of (entry, verdict) tuples.
        """
        out = []
        for entry in entries:
            verdict = self.evaluate_predicate(
                entry.get(predicate_field, ""), company_facts
            )
            out.append((entry, verdict))
        return out
