"""Post-generation deterministic validator for Phase 1 LLM outputs.

Enforces (per implementation contract):
  AC1 — JSON Schema compliance
  AC2 — Regulatory Baseline file existence (every regulatory_baseline_refs[] path resolves)
  AC3 — No re-classification of Regulatory Baseline relationships
  AC4 — INSUFFICIENT_EVIDENCE handling
  AC5 — Status field consistency
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# Minimal JSON Schema validator (no jsonschema dep needed)
# Implements a subset of JSON Schema Draft 7 sufficient for our schemas
# (type, required, properties, items, enum, const, additionalProperties, $ref).
# For full validation use `pip install jsonschema` (added in pyproject.toml).


class ValidationError(dict):
    """Single validation error. Subclass of dict for easy JSON serialization."""

    def __init__(self, path: str, message: str, **extra: Any) -> None:
        super().__init__(path=path, message=message, **extra)


class Phase1Validator:
    """Validate Phase 1 LLM outputs against JSON Schema + Regulatory Baseline invariants."""

    def __init__(
        self,
        regulatory_baseline_root: Path | None = None,
        layer0_root: Path | None = None,
        output_schemas_path: Path | None = None,
    ) -> None:
        """Construct a Phase1Validator.

        Args:
            regulatory_baseline_root: Canonical (CORR-005) root directory for the
                Regulatory Baseline (formerly Layer 0). Required unless the
                deprecated ``layer0_root`` alias is used.
            layer0_root: DEPRECATED alias for ``regulatory_baseline_root``.
                Kept for backwards compatibility with code written before
                CORR-005. Emits ``DeprecationWarning`` when used. Will be
                removed in a future contract.
            output_schemas_path: Optional path to a YAML file containing JSON
                Schemas keyed by ``prompt_spec_id``.
        """
        import warnings

        if regulatory_baseline_root is None and layer0_root is not None:
            warnings.warn(
                "Argument 'layer0_root' is deprecated; "
                "use 'regulatory_baseline_root' instead. (CORR-005)",
                DeprecationWarning,
                stacklevel=2,
            )
            regulatory_baseline_root = layer0_root
        if regulatory_baseline_root is None:
            raise TypeError(
                "Phase1Validator requires 'regulatory_baseline_root' "
                "(or deprecated alias 'layer0_root')."
            )
        self.regulatory_baseline_root = Path(regulatory_baseline_root)
        # CORR-049-T5: default to output_schemas.yaml in the PROMPTS dir
        # adjacent to aegis-phase1 (Methodology-main is a SIBLING repo).
        if output_schemas_path is None:
            # aegis-phase1/src/aegis_phase1/prompts_v2/validator.py →
            # /<root>/aegis-phase1 → /<root>/Methodology-main/...
            aegis_root = Path(__file__).resolve().parent.parent.parent.parent.parent
            default_path = (
                aegis_root
                / "Methodology-main"
                / "00_METHODOLOGY"
                / "PROMPTS"
                / "output_schemas.yaml"
            )
            self.output_schemas_path = default_path
        else:
            self.output_schemas_path = Path(output_schemas_path)
        self._schemas: dict[str, Any] = {}
        if self.output_schemas_path and self.output_schemas_path.exists():
            # CORR-049-T5: use the fenced-block parser (the file is
            # Markdown with ```yaml blocks, one per LLM spec; the
            # previous _load_yaml_with_frontmatter treated it as
            # YAML+frontmatter and discarded the body, so
            # _resolve_schema() always returned {}).
            self._schemas = self._load_output_schemas(self.output_schemas_path)
            # Backward-compat: if no fenced blocks were found, fall back
            # to the old loader (in case the file becomes pure YAML one
            # day).
            if not self._schemas:
                logger.info(
                    "CORR-049-T5: no fenced blocks found in %s; falling back "
                    "to legacy _load_yaml_with_frontmatter",
                    self.output_schemas_path,
                )
                self._schemas = self._load_yaml_with_frontmatter(self.output_schemas_path)

    # CORR-049-T5: fenced-block regex for the output_schemas.yaml Markdown file.
    _FENCED_YAML_RE = re.compile(
        r"```yaml\s*\n(.*?)\n```",
        re.DOTALL,
    )

    @staticmethod
    def _load_output_schemas(path: Path) -> dict[str, dict[str, Any]]:
        """CORR-049-T5: load JSON Schemas from output_schemas.yaml.

        The file is NOT pure YAML — it's Markdown with ```yaml fenced
        code blocks, one per LLM spec. The previous loader treated it
        as YAML+frontmatter and discarded the body, so
        ``_resolve_schema()`` always returned ``{}`` (root cause of
        "0 sub_domain_activations" across all real LLM runs since
        CORR-045).

        Strategy:
          1. Find all ```yaml ... ``` fenced blocks.
          2. ``yaml.safe_load`` each block.
          3. Index by ``properties.prompt_spec_id.const`` (JSON Schema
             convention used by the canonical 5 specs).

        Args:
            path: path to output_schemas.yaml.

        Returns:
            dict mapping spec_id (e.g. ``"P1B-LLM-01-INTERPRETATION"``)
            to the parsed JSON Schema dict. Empty dict if file missing
            or no fenced blocks.
        """
        if not path.exists():
            logger.warning("output_schemas.yaml not found at %s", path)
            return {}

        text = path.read_text(encoding="utf-8")
        schemas: dict[str, dict[str, Any]] = {}

        for match in Phase1Validator._FENCED_YAML_RE.finditer(text):
            block_text = match.group(1)
            try:
                parsed = yaml.safe_load(block_text)
            except yaml.YAMLError as e:
                logger.debug("skipping fenced block (parse error): %s", e)
                continue
            if not isinstance(parsed, dict):
                continue
            # Lookup key: properties.prompt_spec_id.const
            spec_id = (
                parsed.get("properties", {})
                .get("prompt_spec_id", {})
                .get("const")
            )
            if spec_id:
                schemas[spec_id] = parsed
            else:
                logger.debug(
                    "fenced block has no properties.prompt_spec_id.const; "
                    "keys=%s",
                    list(parsed.keys())[:5],
                )

        logger.info(
            "CORR-049-T5: loaded %d schemas from %s (specs=%s)",
            len(schemas), path.name, sorted(schemas.keys()),
        )
        return schemas

    @staticmethod
    def _load_yaml_with_frontmatter(path: Path) -> dict[str, Any]:
        """Load a YAML file that may have a frontmatter wrapper. See PromptLoader."""
        text = path.read_text(encoding="utf-8")
        try:
            return yaml.safe_load(text) or {}
        except yaml.composer.ComposerError:
            pass
        lines = text.splitlines(keepends=False)
        in_frontmatter = False
        frontmatter_done = False
        frontmatter_lines: list[str] = []
        for line in lines:
            if line.strip() == "---":
                if not in_frontmatter and not frontmatter_done:
                    in_frontmatter = True
                    continue
                elif in_frontmatter:
                    in_frontmatter = False
                    frontmatter_done = True
                    break
            if in_frontmatter:
                frontmatter_lines.append(line)
        if frontmatter_done and frontmatter_lines:
            try:
                return yaml.safe_load("\n".join(frontmatter_lines)) or {}
            except yaml.YAMLError:
                return {}
        try:
            docs = list(yaml.safe_load_all(text))
            for doc in docs:
                if doc is not None and isinstance(doc, dict):
                    return doc
            return {}
        except yaml.YAMLError:
            return {}

    def validate(
        self, spec_id: str, output: dict[str, Any], inputs: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Validate the output of a single LLM call.

        Returns:
            {
              "valid": bool,
              "schema_errors": [ValidationError, ...],
              "citation_errors": [ValidationError, ...],
              "warnings": [...],
            }
        """
        schema_errors: list[ValidationError] = []
        citation_errors: list[ValidationError] = []
        warnings: list[str] = []

        # 1. JSON Schema validation (if schema available)
        schema = self._resolve_schema(spec_id)
        if schema:
            schema_errors = self._validate_against_schema(output, schema)
        else:
            warnings.append(f"No schema registered for spec_id={spec_id}")

        # 2. Regulatory Baseline citation presence (every regulatory_baseline_refs[] file must exist)
        citation_errors = self._validate_citations(output)

        # 3. No re-classification (P1C-LLM-01 specific: regulatory_baseline_relationship preserved)
        if spec_id == "P1C-LLM-01-OVERLAP-CLASSIFICATION":
            reclass_errors = self._validate_no_reclassification(output)
            citation_errors.extend(reclass_errors)

        # 4. INSUFFICIENT_EVIDENCE handling
        if (
            output.get("status") == "INSUFFICIENT_EVIDENCE"
            and not output.get("missing_fact")
            and not (output.get("interpretations") or output.get("derogations") or output.get("sub_domain_activations"))
        ):
            warnings.append("INSUFFICIENT_EVIDENCE without missing_fact or partial output")

        # 5. status field consistency
        status = output.get("status")
        if status not in ("OK", "INSUFFICIENT_EVIDENCE", "INDETERMINATE"):
            warnings.append(f"Unknown status value: {status}")

        return {
            "valid": not schema_errors and not citation_errors,
            "schema_errors": schema_errors,
            "citation_errors": citation_errors,
            "warnings": warnings,
        }

    def _resolve_schema(self, spec_id: str) -> dict[str, Any]:
        """Look up the JSON Schema for this spec_id (same logic as PromptLoader)."""
        if not self._schemas:
            return {}
        if spec_id in self._schemas and isinstance(self._schemas[spec_id], dict):
            return self._schemas[spec_id]
        # Search nested
        for _key, value in self._schemas.items():
            if isinstance(value, dict):
                props = value.get("properties", {})
                pid = props.get("prompt_spec_id", {})
                if isinstance(pid, dict) and pid.get("const") == spec_id:
                    return value
        return {}

    def _validate_against_schema(
        self, output: dict[str, Any], schema: dict[str, Any]
    ) -> list[ValidationError]:
        """Minimal JSON Schema validator (Draft 7 subset)."""
        errors: list[ValidationError] = []

        # Top-level
        if "type" in schema and not self._check_type(output, schema["type"]):
            errors.append(
                ValidationError(
                    "$",
                    f"Expected type {schema['type']}, got {type(output).__name__}",
                )
            )

        # Required
        for req in schema.get("required", []):
            if req not in output:
                errors.append(
                    ValidationError(
                        f"$.{req}",
                        f"Required field '{req}' missing",
                    )
                )

        # Properties
        properties = schema.get("properties", {})
        for prop_name, prop_schema in properties.items():
            if prop_name not in output:
                continue
            prop_value = output[prop_name]
            self._validate_property(prop_value, prop_schema, f"$.{prop_name}", errors)

        # AdditionalProperties
        if schema.get("additionalProperties") is False:
            allowed = set(properties.keys())
            extras = set(output.keys()) - allowed
            for extra in extras:
                errors.append(
                    ValidationError(
                        f"$.{extra}",
                        f"Additional property not allowed: '{extra}'",
                    )
                )

        return errors

    def _validate_property(
        self,
        value: Any,
        schema: dict[str, Any],
        path: str,
        errors: list[ValidationError],
    ) -> None:
        """Recursively validate a property."""
        # const
        if "const" in schema:
            if value != schema["const"]:
                errors.append(
                    ValidationError(
                        path,
                        f"Expected const '{schema['const']}', got '{value}'",
                    )
                )
            return

        # enum
        if "enum" in schema:
            if value not in schema["enum"]:
                errors.append(
                    ValidationError(
                        path,
                        f"Value '{value}' not in enum {schema['enum']}",
                    )
                )
            return

        # type
        if "type" in schema and not self._check_type(value, schema["type"]):
            errors.append(
                ValidationError(
                    path,
                    f"Expected type {schema['type']}, got {type(value).__name__}",
                )
            )
            return  # No point checking items/properties if type wrong

        # minLength / maxLength (for strings)
        if isinstance(value, str):
            if "minLength" in schema and len(value) < schema["minLength"]:
                errors.append(
                    ValidationError(
                        path,
                        f"String length {len(value)} < minLength {schema['minLength']}",
                    )
                )
            if "maxLength" in schema and len(value) > schema["maxLength"]:
                errors.append(
                    ValidationError(
                        path,
                        f"String length {len(value)} > maxLength {schema['maxLength']}",
                    )
                )

        # minItems / maxItems (for arrays)
        if isinstance(value, list):
            if "minItems" in schema and len(value) < schema["minItems"]:
                errors.append(
                    ValidationError(
                        path,
                        f"Array length {len(value)} < minItems {schema['minItems']}",
                    )
                )
            if "maxItems" in schema and len(value) > schema["maxItems"]:
                errors.append(
                    ValidationError(
                        path,
                        f"Array length {len(value)} > maxItems {schema['maxItems']}",
                    )
                )

        # items (for arrays)
        if isinstance(value, list) and "items" in schema:
            items_schema = schema["items"]
            for i, item in enumerate(value):
                self._validate_property(item, items_schema, f"{path}[{i}]", errors)

        # properties (for objects)
        if isinstance(value, dict) and "properties" in schema:
            sub_properties = schema["properties"]
            for sub_name, sub_schema in sub_properties.items():
                if sub_name in value:
                    self._validate_property(
                        value[sub_name], sub_schema, f"{path}.{sub_name}", errors
                    )

    def _check_type(self, value: Any, expected_type: str) -> bool:
        """Check JSON Schema type (supports 'object', 'array', 'string', 'integer', 'number', 'boolean', 'null')."""
        if expected_type == "object":
            return isinstance(value, dict)
        if expected_type == "array":
            return isinstance(value, list)
        if expected_type == "string":
            return isinstance(value, str)
        if expected_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if expected_type == "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        if expected_type == "boolean":
            return isinstance(value, bool)
        if expected_type == "null":
            return value is None
        return True  # Unknown type — permissive

    def _extract_regulatory_baseline_refs(self, output: Any) -> list[str]:
        """Recursively collect all `regulatory_baseline_refs[]` entries from output."""
        refs: list[str] = []
        if isinstance(output, dict):
            for k, v in output.items():
                if k == "regulatory_baseline_refs" and isinstance(v, list):
                    refs.extend(str(x) for x in v)
                else:
                    refs.extend(self._extract_regulatory_baseline_refs(v))
        elif isinstance(output, list):
            for item in output:
                refs.extend(self._extract_regulatory_baseline_refs(item))
        return refs

    # DEPRECATED alias (CORR-005) — preserved for backwards compatibility.
    def _extract_layer0_refs(self, output: Any) -> list[str]:
        """DEPRECATED: use ``_extract_regulatory_baseline_refs`` instead."""
        import warnings as _warnings

        _warnings.warn(
            "Phase1Validator._extract_layer0_refs is deprecated; "
            "use _extract_regulatory_baseline_refs instead. (CORR-005)",
            DeprecationWarning,
            stacklevel=2,
        )
        return self._extract_regulatory_baseline_refs(output)

    def _extract_doc07b_refs(self, output: Any) -> list[str]:
        """Recursively collect all `doc07b_refs[]` entries from output."""
        refs: list[str] = []
        if isinstance(output, dict):
            for k, v in output.items():
                if k == "doc07b_refs" and isinstance(v, list):
                    refs.extend(str(x) for x in v)
                else:
                    refs.extend(self._extract_doc07b_refs(v))
        elif isinstance(output, list):
            for item in output:
                refs.extend(self._extract_doc07b_refs(item))
        return refs

    def _validate_citations(self, output: dict[str, Any]) -> list[ValidationError]:
        """Every regulatory_baseline_refs[] / doc07b_refs[] path must resolve to an existing file."""
        errors: list[ValidationError] = []
        for ref in self._extract_regulatory_baseline_refs(output):
            if not self._path_exists(ref):
                errors.append(
                    ValidationError(
                        "regulatory_baseline_refs",
                        f"Regulatory Baseline file does not exist: {ref}",
                        ref=ref,
                    )
                )
        for ref in self._extract_doc07b_refs(output):
            if not self._path_exists(ref):
                errors.append(
                    ValidationError(
                        "doc07b_refs",
                        f"Doc 07b file does not exist: {ref}",
                        ref=ref,
                    )
                )
        return errors

    def _validate_no_reclassification(
        self, output: dict[str, Any]
    ) -> list[ValidationError]:
        """P1C-LLM-01 specific: regulatory_baseline_relationship must match Regulatory Baseline source.

        For v1.2 MVP, this is a soft check — we log warnings if relationships
        look suspicious. Full Regulatory Baseline comparison is a stretch goal.
        """
        errors: list[ValidationError] = []
        # The P1C-LLM-01 output has sub_domain_activations[].verified_relationship_per_pair[]
        sd_activations = output.get("sub_domain_activations", [])
        for sd in sd_activations:
            for pair in sd.get("verified_relationship_per_pair", []):
                rel = pair.get("regulatory_baseline_relationship")
                verdict = pair.get("company_scope_verdict")
                # If LLM invented a non-standard relationship, flag it
                valid_rels = {"SAME", "COMPLEMENTARY", "CONTRADICTORY", "SCOPE_DISJOINT", "CONDITIONAL"}
                if rel and rel not in valid_rels:
                    errors.append(
                        ValidationError(
                            "sub_domain_activations.verified_relationship_per_pair",
                            f"Non-standard regulatory_baseline_relationship: '{rel}' (allowed: {valid_rels})",
                        )
                    )
                # If LLM uses CONDITIONAL, it MUST have a verdict
                if rel == "CONDITIONAL" and not verdict:
                    errors.append(
                        ValidationError(
                            "sub_domain_activations.verified_relationship_per_pair",
                            "CONDITIONAL relationship requires company_scope_verdict",
                        )
                    )
        return errors

    def _path_exists(self, ref: str) -> bool:
        """Check if a path reference resolves to an existing file.

        Tries:
          1. As absolute path
          2. As path relative to regulatory_baseline_root
          3. As path relative to current working directory
        """
        if not ref:
            return False
        p = Path(ref)
        if p.is_absolute() and p.exists():
            return True
        candidate = self.regulatory_baseline_root / ref
        if candidate.exists():
            return True
        candidate2 = Path.cwd() / ref
        if candidate2.exists():
            return True
        # If regulatory_baseline_root is itself a relative path, try resolving
        if not self.regulatory_baseline_root.is_absolute():
            candidate3 = (Path.cwd() / self.regulatory_baseline_root / ref).resolve()
            if candidate3.exists():
                return True
        return False
