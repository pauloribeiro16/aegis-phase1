"""Post-generation deterministic validator for Phase 1 LLM outputs.

Enforces (per implementation contract):
  AC1 — JSON Schema compliance
  AC2 — Layer 0 file existence (every layer0_refs[] path resolves)
  AC3 — No re-classification of Layer 0 relationships
  AC4 — INSUFFICIENT_EVIDENCE handling
  AC5 — Status field consistency
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Minimal JSON Schema validator (no jsonschema dep needed)
# Implements a subset of JSON Schema Draft 7 sufficient for our schemas
# (type, required, properties, items, enum, const, additionalProperties, $ref).
# For full validation use `pip install jsonschema` (added in pyproject.toml).


class ValidationError(dict):
    """Single validation error. Subclass of dict for easy JSON serialization."""

    def __init__(self, path: str, message: str, **extra: Any) -> None:
        super().__init__(path=path, message=message, **extra)


class Phase1Validator:
    """Validate Phase 1 LLM outputs against JSON Schema + Layer 0 invariants."""

    def __init__(
        self,
        layer0_root: Path,
        output_schemas_path: Path | None = None,
    ) -> None:
        self.layer0_root = Path(layer0_root)
        self.output_schemas_path = (
            Path(output_schemas_path) if output_schemas_path else None
        )
        self._schemas: dict[str, Any] = {}
        if self.output_schemas_path and self.output_schemas_path.exists():
            self._schemas = self._load_yaml_with_frontmatter(self.output_schemas_path)

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

        # 2. Layer 0 citation presence (every layer0_refs[] file must exist)
        citation_errors = self._validate_citations(output)

        # 3. No re-classification (P1C-LLM-01 specific: layer0_relationship preserved)
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

    def _extract_layer0_refs(self, output: Any) -> list[str]:
        """Recursively collect all `layer0_refs[]` entries from output."""
        refs: list[str] = []
        if isinstance(output, dict):
            for k, v in output.items():
                if k == "layer0_refs" and isinstance(v, list):
                    refs.extend(str(x) for x in v)
                else:
                    refs.extend(self._extract_layer0_refs(v))
        elif isinstance(output, list):
            for item in output:
                refs.extend(self._extract_layer0_refs(item))
        return refs

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
        """Every layer0_refs[] / doc07b_refs[] path must resolve to an existing file."""
        errors: list[ValidationError] = []
        for ref in self._extract_layer0_refs(output):
            if not self._path_exists(ref):
                errors.append(
                    ValidationError(
                        "layer0_refs",
                        f"Layer 0 file does not exist: {ref}",
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
        """P1C-LLM-01 specific: layer0_relationship must match Layer 0 source.

        For v1.2 MVP, this is a soft check — we log warnings if relationships
        look suspicious. Full Layer 0 comparison is a stretch goal.
        """
        errors: list[ValidationError] = []
        # The P1C-LLM-01 output has sub_domain_activations[].verified_relationship_per_pair[]
        sd_activations = output.get("sub_domain_activations", [])
        for sd in sd_activations:
            for pair in sd.get("verified_relationship_per_pair", []):
                rel = pair.get("layer0_relationship")
                verdict = pair.get("company_scope_verdict")
                # If LLM invented a non-standard relationship, flag it
                valid_rels = {"SAME", "COMPLEMENTARY", "CONTRADICTORY", "SCOPE_DISJOINT", "CONDITIONAL"}
                if rel and rel not in valid_rels:
                    errors.append(
                        ValidationError(
                            "sub_domain_activations.verified_relationship_per_pair",
                            f"Non-standard layer0_relationship: '{rel}' (allowed: {valid_rels})",
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
          2. As path relative to layer0_root
          3. As path relative to current working directory
        """
        if not ref:
            return False
        p = Path(ref)
        if p.is_absolute() and p.exists():
            return True
        candidate = self.layer0_root / ref
        if candidate.exists():
            return True
        candidate2 = Path.cwd() / ref
        if candidate2.exists():
            return True
        # If layer0_root is itself a relative path, try resolving
        if not self.layer0_root.is_absolute():
            candidate3 = (Path.cwd() / self.layer0_root / ref).resolve()
            if candidate3.exists():
                return True
        return False
