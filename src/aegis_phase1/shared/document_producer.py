"""DocumentProducer base class for filling Markdown templates with LLM."""

import re
import time
from datetime import datetime
from pathlib import Path

import yaml

from aegis_phase1.llm.base import create_llm_client
from aegis_phase1.logging_config import get_logger
from aegis_phase1.shared.template_parser import Section

logger = get_logger(__name__)


def _template_dir(case_path: str, phase: int) -> Path:
    return Path(case_path) / "templates" / f"phase{phase}"


def _output_dir(case_path: str, phase: int) -> Path:
    return Path(case_path) / "output" / f"phase{phase}"


def _versions_dir(case_path: str, phase: int) -> Path:
    return Path(case_path) / "output" / f"phase{phase}" / "versions"


def _intermediate_dir(case_path: str, phase: int) -> Path:
    return Path(case_path) / "output" / f"phase{phase}" / "intermediate"


def sanitize_markdown(content: str) -> str:
    """Strip YAML frontmatter, Cypher blocks, JSON blocks, and raw data leakage from LLM output.

    The final markdown must be clean: no Cypher, no YAML, no JSON dumps,
    no raw Python dict/list representations.
    Only standard markdown (headers, tables, lists, paragraphs, code blocks
    other than cypher/json) is allowed through.
    """
    if not content:
        return ""

    result = content

    # 0. Strip leading structured-data block (everything before first ## header
    #    when the block contains evidence/RAG/subdomain markers).
    #    Find the first ## header; if lines before it contain structured-data
    #    markers, drop everything before it.
    first_h2_match = re.search(r"^## \S", result, re.MULTILINE)
    if first_h2_match:
        prefix = result[: first_h2_match.start()]
        _structured_markers = (
            "evidence:",
            "RAG:",
            "subdomainId:",
            "subdomain_id:",
            "eventId:",
            "STK-INT-",
            "STK-EXT-",
            "BG-",
            "NIS2 evidence:",
            "CRA evidence:",
        )
        if any(marker in prefix for marker in _structured_markers):
            result = result[first_h2_match.start() :]

    # 1. Strip YAML frontmatter (--- blocks at start)
    result = re.sub(
        r"^---\s*\n.*?\n---\s*\n",
        "",
        result,
        count=1,
        flags=re.DOTALL | re.MULTILINE,
    )

    # 2. Strip Cypher/GraphQL/Gremlin/SPARQL code blocks
    result = re.sub(
        r"```(?:cypher|graphql|gremlin|sparql)\s*\n.*?```",
        "",
        result,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 3. Strip JSON code blocks
    result = re.sub(
        r"```json\s*\n.*?```",
        "",
        result,
        flags=re.DOTALL | re.IGNORECASE,
    )

    # 4. Strip bare Cypher lines
    result = re.sub(
        r"^\s*(MATCH|OPTIONAL\s+MATCH|CREATE|MERGE|DELETE|DETACH\s+DELETE|RETURN|WITH)\s+.*?$",
        "",
        result,
        flags=re.MULTILINE,
    )
    # 4b. Strip bare Cypher SET m.<var> = ... lines
    result = re.sub(
        r"^\s*SET\s+m\.\w+\s*=.*$",
        "",
        result,
        flags=re.MULTILINE,
    )

    # 5. Strip raw key-value lines that look like structured data dumps
    #    (not table rows or legitimate markdown). Only strip lines that:
    #    - start with a key-like pattern followed by ": "
    #    - AND contain evidence/RAG/subdomain/dict/list markers, OR
    #    - are indented bullet-style lines starting with "- " and containing evidence markers
    def _is_structured_data_line(line: str) -> bool:
        stripped = line.strip()
        if not stripped:
            return False
        # Indented evidence/RAG/dict lines (e.g. "  - GDPR evidence: ...")
        if re.match(r"^[\s]*-\s+\w.*evidence:", stripped):
            return True
        if re.match(r"^[\s]*-\s+RAG:", stripped):
            return True
        if re.match(
            r"^[\s]*-\s+(subdomainId|subdomain_id|eventId|STK-INT-|STK-EXT-|BG-)", stripped
        ):
            return True
        # Non-table lines that look like YAML dumps with { or [
        if not stripped.startswith("|") and re.match(r"^[\s]*\w[\w_-]*:\s*[\{\[]", stripped):
            return True
        # Bare dict/list starts
        if re.match(r"^[\s]*[\{\[]\s*$", stripped):
            return True
        # Lines that are just closing brackets or commas from dict/list
        if re.match(r"^[\s]*[\}\]],?\s*$", stripped):
            return True
        # Lines starting with bare property names in dict dump style (e.g. "'NIS 2': '[...]'")
        if re.match(r"^[\s]*'[\w\s]+':\s*'", stripped):
            return True
        # Lines that are just string values from a dict (indented, starting with quote)
        if re.match(r"^[\s]+'.*',?\s*$", stripped):
            return True
        # Lines like "// Contextual data injection based on analysis"
        if re.match(r"^[\s]*//", stripped):
            return True
        # Lines that are bare Cypher-like fragments: a)-[:HAS_GAP]->...
        if re.match(r"^[\s]*[a-z]\).*\[:", stripped):
            return True
        # Bare SI-XX or similar identifiers on their own line (not in a table)
        return bool(re.match(r"^[A-Z]{2}-\d+$", stripped))

    lines = result.splitlines()
    cleaned_lines = [ln for ln in lines if not _is_structured_data_line(ln)]
    result = "\n".join(cleaned_lines)

    # 5b. Strip bare "SET d.description = ..." lines (Cypher property assignments)
    result = re.sub(
        r"^\s*SET\s+d\.\w+\s*=.*$",
        "",
        result,
        flags=re.MULTILINE,
    )

    # 6. Strip "Retrieved clauses:" blocks (numbered list following the marker)
    result = re.sub(
        r"Retrieved clauses:\n(?:\d+\..*\n?|.*?\n?)+?(?=\n##\s|\Z)",
        "",
        result,
        flags=re.MULTILINE,
    )

    # 7. Collapse multiple consecutive blank lines into at most 2
    result = re.sub(r"\n{3,}", "\n\n", result)

    lines = [ln for ln in result.splitlines() if ln.strip()]
    return "\n".join(lines).strip() + "\n" if lines else ""


class DocumentProducer:
    """Base class for nodes that fill Markdown templates with LLM.

    Templates are read from:  {case_path}/templates/phase{N}/
    Outputs are written to:   {case_path}/output/phase{N}/
    """

    def __init__(
        self,
        case_path: str,
        llm_config: dict | None = None,
        phase: int = 1,
        run_config: dict | None = None,
    ) -> None:
        self.case_path = case_path
        self.llm_config = llm_config or {}
        self.phase = phase
        self.run_config = run_config
        self.llm = create_llm_client(config=self.llm_config)

    def read_template(self, template_name: str) -> str:
        """Read a Markdown template from the phase templates directory."""
        path = _template_dir(self.case_path, self.phase) / template_name
        if not path.exists():
            path = Path(self.case_path) / template_name
        logger.info("[producer] read_template path=%s exists=%s", path, path.exists())
        return path.read_text(encoding="utf-8")

    def fetch_phase_data(self, phase: int) -> dict:
        """Run Cypher queries for the given phase and return data dict."""
        raise NotImplementedError

    def fill_template(
        self,
        template: str,
        data: dict,
        phase: int = 1,
        run_config: dict | None = None,
    ) -> str:
        """Fill a Markdown template section-by-section, with context accumulation."""
        from aegis_phase1.shared.template_parser import parse_sections

        template = self._preprocess_placeholders(template, data)
        sections = parse_sections(template)
        if not sections:
            return ""

        rc = run_config if run_config is not None else self.run_config

        accumulated_bodies: list[str] = []
        accumulated_full: list[tuple[str, str]] = []
        toc_headers: list[str] = []

        for i, section in enumerate(sections):
            toc_block = (
                "\n".join(f"  {h}" for h in toc_headers) if toc_headers else "  (start of document)"
            )

            recent_bodies = accumulated_bodies[-2:]
            context_block = (
                "\n\n---\n\n".join(recent_bodies) if recent_bodies else "(no prior sections)"
            )

            has_placeholders = "[" in section.body and "]" in section.body
            is_short = len(section.body) < 200
            is_h1_metadata = section.level == 1

            if is_h1_metadata or (is_short and not has_placeholders):
                filled_body = section.body
            else:
                filled_body = self._fill_section_with_llm(
                    section=section,
                    data=data,
                    toc_block=toc_block,
                    context_block=context_block,
                    section_index=i,
                    total_sections=len(sections),
                    phase=phase,
                    run_config=rc,
                )

            if filled_body:
                accumulated_bodies.append(filled_body)
                accumulated_full.append((section.header, filled_body))
                if section.header:
                    toc_headers.append(section.header)

        parts = []
        for header, body in accumulated_full:
            if header:
                parts.append(f"{header}\n\n{body}" if body else header)
            else:
                parts.append(body)
        return "\n\n".join(parts)

    def _preprocess_placeholders(self, template: str, data: dict) -> str:
        """Replace {variable} patterns with actual values from data dict."""
        import re

        def _replace(match):
            key = match.group(1)
            value = data.get(key)
            if value is None:
                return match.group(0)
            if isinstance(value, (list, tuple)):
                if value and isinstance(value[0], dict):
                    return ", ".join(str(v.get("name", v)) for v in value[:5])
                return ", ".join(str(v) for v in value[:5])
            if isinstance(value, dict):
                inner = value.get("name", value.get("description", ""))
                return str(inner) if inner else str(value)
            return str(value)

        return re.sub(r"\{(\w+)\}", _replace, template)

    def _fill_section_with_llm(
        self,
        section: "Section",
        data: dict,
        toc_block: str,
        context_block: str,
        section_index: int,
        total_sections: int,
        phase: int,
        run_config: dict | None = None,
    ) -> str:
        """Call LLM to fill a single section with accumulated context."""
        section_data = self._filter_data_for_section(section.header, data)

        prompt = f"""You are filling section {section_index + 1}/{total_sections} of a Markdown document.

DOCUMENT TABLE OF CONTENTS (filled so far):
{toc_block}

PREVIOUS 2 SECTIONS (for style consistency):
{context_block}

SECTION TO FILL (preserve the header EXACTLY as given below):
{section.header}
{section.body}

DATA FOR THIS SECTION:
{section_data}

RULES:
- Output ONLY the filled section body (the content under the header).
- Do NOT repeat the header — it will be prepended automatically.
- CRITICAL: Replace ALL [placeholder] patterns with values from the data. Common patterns:
  - [N], [X%], [X.X%] — use actual numbers from data
  - [placeholder_description] — use the description from data or generate contextually appropriate text
  - [D-XX.X] — use subdomain IDs from data
  - [YYYY-MM-DD] — use actual dates or "YYYY-MM-DD" if unknown
- Remove any remaining placeholder patterns by filling them with reasonable values or removing them.
- If the section header is "Decision Rationale", "Mapping Rationale", "Coverage Rationale", or "Complementarity Rationale", write 2-3 sentences using the corresponding data field.
- If the section header is "Evidence Trail" or "Evidence Sources", list items from data["evidence_sources"] or relevant data field.
- Keep style consistent with previous sections.
- Do not output preamble, explanation, or "Here is the filled section:".

FILLED SECTION BODY:"""

        rc = run_config if run_config is not None else self.run_config
        result = self.llm.generate(
            prompt=prompt,
            system="You are a technical documentation assistant filling Markdown templates.",
            task_name=f"fill_section_{section_index + 1}_of_{total_sections}",
            temperature=0.1,
            config=rc,
        )
        if result.get("error"):
            return section.body
        filled = str(result.get("raw", "")).strip()
        if filled and section.header:
            header_text = section.header.strip()
            if filled.startswith(header_text):
                filled = filled[len(header_text) :].lstrip("\n\r ")
        return filled

    def _filter_data_for_section(self, header: str, data: dict) -> str:
        """Filter data dict to relevant fields based on section header keywords."""
        h = header.lower()
        if "decision rationale" in h or "context" in h:
            keys = [
                "context_assessment_rationale",
                "stakeholder_rationale",
                "business_goal_rationale",
                "company_context",
            ]
        elif "complexity" in h and "tier" in h:
            keys = ["complexity_tier", "complexity_tier_rationale"]
        elif "conditional extension" in h:
            keys = ["conditional_extensions", "conditional_extensions_data"]
        elif "regulatory interaction" in h:
            keys = ["regulatory_interactions", "regulatory_interactions_data"]
        elif "domain elaboration" in h:
            keys = ["domain_elaboration_entries"]
        elif "regulatory obligation" in h:
            keys = ["regulatory_obligations"]
        elif "mapping rationale" in h or "clause" in h:
            keys = ["mapping_rationale", "clause_mappings", "applicability_evidence"]
        elif "coverage rationale" in h or "coverage" in h:
            keys = [
                "coverage_rationale",
                "coverage_matrix",
                "coverage_summary",
                "domain_coverage_entries",
            ]
        elif "complementarity" in h:
            keys = [
                "complementarity_rationale",
                "complementarity_analysis",
                "domain_coverage_entries",
            ]
        elif "evidence trail" in h or "evidence sources" in h:
            keys = [
                "evidence_sources",
                "stakeholder_rationale",
                "business_goal_rationale",
                "applicability_evidence",
            ]
        elif "strategic" in h or "implication" in h:
            keys = ["strategic_implications", "regulatory_gaps"]
        else:
            keys = list(data.keys())

        filtered = {k: data[k] for k in keys if k in data}
        if not filtered:
            filtered = data
        return _format_dict_as_markdown(filtered)

    def write_output(
        self,
        template_name: str,
        filled_content: str,
        version: int | None = None,
        intermediate_data: dict | None = None,
        max_age_sec: int = 3600,
        force_rebuild: bool = False,
    ) -> str:
        """Write filled content to output/phase{N}/ with auto-versioning.

        Behaviour:
        - Sanitizes `filled_content` (strips YAML, Cypher, JSON).
        - If `_filled.md` exists and is less than `max_age_sec` seconds old,
          returns the existing filename without writing (unless `force_rebuild`).
        - If `output/phase{N}/{stem}_filled.md` already exists, moves it to
          `output/phase{N}/versions/{stem}_v{N}.md` (incremental version).
        - Writes the sanitized markdown to `_filled.md` (canonical latest).
        - Prepends an HTML comment with model + timestamp to the markdown
          so the generating model is visible in the file itself.
        - If `intermediate_data` is provided, injects `_metadata: {model, num_ctx, generated_at}`
          and saves it to `output/phase{N}/intermediate/{stem}_v{N}.yaml` for reproducibility.
        - Returns the canonical filename.
        """
        out_dir = _output_dir(self.case_path, self.phase)
        out_dir.mkdir(parents=True, exist_ok=True)

        stem = template_name.replace(".md", "")
        filled_name = f"{stem}_filled.md"
        filled_path = out_dir / filled_name

        if not force_rebuild and filled_path.exists():
            file_age = time.time() - filled_path.stat().st_mtime
            if file_age < max_age_sec:
                logger.info(
                    "[producer] skipped %s (age=%.0fs < %ds limit)",
                    filled_name,
                    file_age,
                    max_age_sec,
                )
                return filled_name

        versions_dir = _versions_dir(self.case_path, self.phase)
        intermediate_dir = _intermediate_dir(self.case_path, self.phase)

        next_version = 1
        if filled_path.exists():
            existing = [
                p for p in versions_dir.glob(f"{stem}_v*.md") if p.stem.split("_v")[-1].isdigit()
            ]
            nums = [int(p.stem.split("_v")[-1]) for p in existing]
            next_version = (max(nums) + 1) if nums else 2

            versions_dir.mkdir(parents=True, exist_ok=True)
            versioned_name = f"{stem}_v{next_version}.md"
            versioned_path = versions_dir / versioned_name
            versioned_path.write_text(filled_path.read_text(encoding="utf-8"), encoding="utf-8")
            logger.info(
                "[producer] archived previous output: %s -> %s",
                filled_path.name,
                versioned_path.name,
            )

        model_name = self.llm_config.get("model", "unknown")
        num_ctx = self.llm_config.get("num_ctx", 8192)
        generated_at = datetime.now().strftime("%Y-%m-%d %H:%M")
        model_tag = f"<!-- Generated by: {model_name} | num_ctx={num_ctx} | {generated_at} -->\n"

        clean_content = sanitize_markdown(filled_content)
        filled_path.write_text(model_tag + clean_content, encoding="utf-8")

        if intermediate_data is not None:
            intermediate_data = dict(intermediate_data)
            intermediate_data["_metadata"] = {
                "model": model_name,
                "num_ctx": num_ctx,
                "generated_at": datetime.now().isoformat(),
                "generator": "aegis-kg DocumentProducer",
            }
            intermediate_dir.mkdir(parents=True, exist_ok=True)
            intermediate_name = f"{stem}_v{next_version}.yaml"
            intermediate_path = intermediate_dir / intermediate_name
            intermediate_path.write_text(
                yaml.safe_dump(intermediate_data, allow_unicode=True, sort_keys=False),
                encoding="utf-8",
            )
            logger.info(
                "[producer] wrote intermediate: %s",
                intermediate_path.name,
            )

        if version is not None and version != next_version:
            logger.debug(
                "[producer] version arg %d differs from auto-incremented %d; using auto",
                version,
                next_version,
            )

        logger.info(
            "[producer] wrote canonical: %s (version=%d)",
            filled_path.name,
            next_version,
        )
        return filled_name

    def produce_all(
        self,
        phase: int,
        templates: list[str],
        run_config: dict | None = None,
    ) -> list[str]:
        """Read each template, fill with LLM, and write output."""
        data = self.fetch_phase_data(phase)
        results = []
        for template in templates:
            content = self.read_template(template)
            filled = self.fill_template(content, data, phase, run_config=run_config)
            output = self.write_output(template, filled)
            results.append(output)
        return results


def _format_dict_as_markdown(d: dict) -> str:
    """Format a dict as readable Markdown for LLM context (not raw Python str)."""
    lines = []
    for key, value in d.items():
        if isinstance(value, str):
            lines.append(f"- **{key}:** {value}")
        elif isinstance(value, (list, tuple)):
            if value and isinstance(value[0], dict):
                for item in value[:10]:
                    item_str = ", ".join(
                        f"{k}: {v}" for k, v in item.items() if not k.startswith("_")
                    )
                    lines.append(f"- {item_str}")
                if len(value) > 10:
                    lines.append(f"- ... ({len(value)} total items)")
            else:
                lines.append(f"- **{key}:** {', '.join(str(v) for v in value[:10])}")
        elif isinstance(value, dict):
            nested = {k: v for k, v in value.items() if not k.startswith("_")}
            lines.append(f"- **{key}:** {nested}")
        else:
            lines.append(f"- **{key}:** {value}")
    return "\n".join(lines)


PHASE1_TEMPLATES = [
    "04_Company_Context_Assessment.md",
    "05_Regulatory_Applicability.md",
    "06_Clause_Mapping_Matrix.md",
    "07_Structured_Compliance_Matrix.md",
]

PHASE1_TEMPLATES_N13 = [
    "05_Regulatory_Applicability.md",
    "06_Clause_Mapping_Matrix.md",
    "07_Structured_Compliance_Matrix.md",
]

PHASE2_TEMPLATES = [
    "08_Obligation_Derivation.md",
    "09_Strategic_Tensions_Report.md",
    "10_Privacy_Security_Goals.md",
    "11_Rules_Catalog.md",
    "12_Rules_Catalog_MD_Spec.md",
]

PHASE3_TEMPLATES = [
    "13_Use_Cases_Catalog.md",
    "13a_Use_Case_Relationships.md",
    "13b_Use_Case_Variability.md",
    "14_Architectural_Nodes.md",
    "15_Requirements_Allocation.md",
    "16_Compliance_Gates_Report.md",
    "17_Functional_Tree.md",
    "22_Traceability_Matrix_Spec.md",
    "23_Functional_Requirements.md",
    "24_Non_Functional_Requirements.md",
    "25_Risk_Analysis.md",
    "Annexes_A-D.md",
]


def resolve_template_path(case_path: str, template_name: str, phase: int = 1) -> Path:
    """Resolve template path, checking phase subdir first, then case root (fallback)."""
    phase_path = _template_dir(case_path, phase) / template_name
    if phase_path.exists():
        return phase_path
    root_path = Path(case_path) / template_name
    return root_path


def resolve_output_path(case_path: str, filename: str, phase: int = 1) -> Path:
    """Resolve output path in output/phase{N}/ directory."""
    out_dir = _output_dir(case_path, phase)
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / filename
