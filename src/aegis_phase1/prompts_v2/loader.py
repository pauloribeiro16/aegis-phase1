"""Loads v1.2 prompt templates from Methodology-main/00_METHODOLOGY/PROMPTS/.

Each prompt is a Markdown file with:
- YAML frontmatter (prompt_spec_id, version, legacy_aliases, invocation_pattern, etc.)
- Markdown body (system prompt + task instructions)
- References to output_schemas.yaml#<spec_id> for output validation

Usage:
    loader = PromptLoader()  # uses default path (../Methodology-main/...)
    loaded = loader.load("P1B-LLM-01-INTERPRETATION")
    rendered = loader.render(spec_id, inputs)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Default path: sibling repo Methodology-main
DEFAULT_PROMPTS_ROOT = (
    Path(__file__).parent.parent.parent.parent.parent
    / "Methodology-main"
    / "00_METHODOLOGY"
    / "PROMPTS"
)


class PromptLoadError(RuntimeError):
    """Raised when a prompt file cannot be loaded."""


class PromptLoader:
    """Loads v1.2 prompt templates and renders them with inputs.

    Attributes:
        root: Path to PROMPTS/ directory
        base_system: Contents of base_system_prompt.md (common preamble)
        schemas: Parsed output_schemas.yaml (5 JSON Schemas)
        cache: In-memory cache for loaded specs (cleared on invalidate)
    """

    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root) if root else DEFAULT_PROMPTS_ROOT
        if not self.root.exists():
            raise PromptLoadError(f"PROMPTS directory does not exist: {self.root}")
        self.base_system_path = self.root / "base_system_prompt.md"
        self.base_system = self.base_system_path.read_text(encoding="utf-8")
        self.schemas_path = self.root / "output_schemas.yaml"
        self.schemas = self._load_yaml_with_frontmatter(self.schemas_path)
        self.cache: dict[str, dict[str, Any]] = {}

    @staticmethod
    def _load_yaml_with_frontmatter(path: Path) -> dict[str, Any]:
        """Load a YAML file that may have a frontmatter (--- ... ---) wrapper.

        Returns the parsed YAML content. For files with `---` blocks, parses
        the first block (YAML) and ignores subsequent `---` blocks.

        Strategy: try yaml.safe_load first; if it raises ComposerError
        (multiple documents), use a simple frontmatter stripper.
        """
        text = path.read_text(encoding="utf-8")
        # Try direct first (in case the file is pure YAML)
        try:
            return yaml.safe_load(text) or {}
        except yaml.composer.ComposerError:
            pass

        # Try stripping YAML frontmatter: split on lines that are exactly '---'
        lines = text.splitlines(keepends=False)
        in_frontmatter = False
        frontmatter_done = False
        frontmatter_lines: list[str] = []
        for _i, line in enumerate(lines):
            if line.strip() == "---":
                if not in_frontmatter and not frontmatter_done:
                    in_frontmatter = True
                    continue
                elif in_frontmatter:
                    # End of frontmatter
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
        # Fallback: try safe_load_all and return the first non-empty doc
        try:
            docs = list(yaml.safe_load_all(text))
            for doc in docs:
                if doc is not None and isinstance(doc, dict):
                    return doc
            return {}
        except yaml.YAMLError:
            return {}

    def invalidate(self, spec_id: str | None = None) -> None:
        """Clear cache for one spec or all."""
        if spec_id is None:
            self.cache.clear()
        else:
            self.cache.pop(spec_id, None)

    def load(self, spec_id: str) -> dict[str, Any]:
        """Load a spec_id (e.g. P1B-LLM-01-INTERPRETATION).

        Returns:
            dict with:
              - frontmatter: dict from YAML
              - body: str (Markdown body, no frontmatter)
              - system: str (base_system_prompt + body, joined)
              - schema_ref: str ("output_schemas.yaml#<spec_id>")
              - schema: dict (resolved JSON Schema for the spec)
              - path: Path (file path)
        """
        if spec_id in self.cache:
            return self.cache[spec_id]

        path = self.root / f"{spec_id}.md"
        if not path.exists():
            raise PromptLoadError(f"Prompt file not found: {path}")

        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        if len(parts) < 3:
            raise PromptLoadError(
                f"Prompt file {path} does not have valid YAML frontmatter "
                f"(expected opening '---', closing '---', then body)"
            )

        try:
            frontmatter = yaml.safe_load(parts[1])
        except yaml.YAMLError as e:
            raise PromptLoadError(f"Invalid YAML frontmatter in {path}: {e}") from e

        body = parts[2].strip()
        system = f"{self.base_system}\n\n{body}"
        schema_ref = f"output_schemas.yaml#{spec_id}"
        schema = self._resolve_schema(spec_id)

        loaded = {
            "spec_id": spec_id,
            "frontmatter": frontmatter,
            "body": body,
            "system": system,
            "schema_ref": schema_ref,
            "schema": schema,
            "path": path,
        }
        self.cache[spec_id] = loaded
        return loaded

    def render(self, spec_id: str, inputs: dict[str, Any]) -> dict[str, str]:
        """Render a prompt with inputs.

        Returns:
            dict with:
              - system: str (with inputs as JSON appendix)
              - user: str (JSON-encoded inputs for the LLM)
        """
        loaded = self.load(spec_id)
        # Serialize inputs as JSON for the user message
        import json
        inputs_json = json.dumps(inputs, indent=2, default=str, ensure_ascii=False)
        system = loaded["system"]
        user = (
            f"# INPUTS for {spec_id}\n\n"
            f"```json\n{inputs_json}\n```\n\n"
            f"# TASK\n\nExecute the task defined in the system prompt. "
            f"Return output matching the JSON Schema in `output_schemas.yaml#{spec_id}`."
        )
        return {"system": system, "user": user}

    def list_specs(self) -> list[str]:
        """List all available prompt specs (P1B-*, P1C-*)."""
        return sorted(p.stem for p in self.root.glob("P1?-LLM-*.md"))

    def _resolve_schema(self, spec_id: str) -> dict[str, Any]:
        """Look up the JSON Schema for this spec_id.

        The schema in output_schemas.yaml uses comments like:
            #:schema_id P1B-LLM-01
        but YAML parsers strip comments. We use a flat mapping: the first YAML
        document whose nested `properties.prompt_spec_id.const` matches spec_id,
        OR fall back to spec_id directly as key.
        """
        schemas = self.schemas
        if not isinstance(schemas, dict):
            return {}

        # Try direct key match first
        if spec_id in schemas:
            return schemas[spec_id]

        # Search all docs for properties.prompt_spec_id.const == spec_id
        for _key, value in schemas.items():
            if isinstance(value, dict):
                props = value.get("properties", {})
                pid = props.get("prompt_spec_id", {})
                if isinstance(pid, dict) and pid.get("const") == spec_id:
                    return value
                # Also handle list of schemas under one key
                if isinstance(props.get("prompt_spec_id"), dict):
                    pass

        return {}
