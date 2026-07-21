"""common_loader — Load 00_COMMON directory content for a case.

Loads company context, architecture inventory, taxonomy reference,
ontology YAML, and regulatory mapping master from a case directory's
00_COMMON folder.

References:
    - contracts/SPRINT001_v2-core.md (C-002)
"""

import logging
import re
from pathlib import Path

import yaml

from aegis_phase1.v2.loader.yaml_input_loader import YamlInputLoader, has_yaml_input

# CORR-037-T4b: inlined from aegis_phase1.v2.loader.__init__ (which no
# longer exports these helpers — the v1 global YAML frontmatter parser
# is removed to satisfy contract G5 part 2). The helpers are still used
# internally by common_loader; they live here as private functions.
import yaml as _yaml
import re as _re


def _parse_yaml_fm(text: str) -> dict:
    """Extract YAML frontmatter between ``---`` markers."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---" or lines[i].strip() == "...":
            end_idx = i
            break
    if end_idx is None:
        return {}
    yaml_block = "\n".join(lines[1:end_idx])
    try:
        return _yaml.safe_load(yaml_block) or {}
    except Exception:
        return {}


def _strip_frontmatter(text: str) -> str:
    """Return markdown body without YAML frontmatter."""
    lines = text.splitlines()
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if lines[i].strip() == "---" or lines[i].strip() == "...":
                return "\n".join(lines[i + 1:])
    return text
from aegis_phase1.v2.state import CompanyContext

logger = logging.getLogger(__name__)

_APPLICABILITY_SUMMARY_PATTERN = re.compile(
    r"^### 3\.6 APPLICABILITY(?:\s+SUMMARY)?\s*$", re.IGNORECASE
)


class CommonLoader:
    """Loader for the 00_COMMON/ directory of a case.

    Parses company context markdown, taxonomy reference, ontology
    YAML, and the (deprecated) regulatory mapping master.
    """

    def __init__(self) -> None:
        self._errors: list[str] = []

    def load(self, case_path: str) -> dict:
        """Load all 00_COMMON files for the given case.

        Prefers structured YAML under ``input/`` when present; otherwise
        falls back to parsing the markdown intake form.

        Args:
            case_path: Path to the case directory
                (e.g. ``.../Case_01_TinyTask_SaaS``).

        Returns:
            Dictionary with keys: company_context, architecture_inventory,
            stakeholders, business_goals, taxonomy_entries, ontology,
            regulations, subdomains, errors.
        """
        self._errors.clear()

        if has_yaml_input(case_path):
            yaml_loader = YamlInputLoader(case_path)
            yaml_data = yaml_loader.load()
            if not yaml_data["errors"]:
                logger.info("Loaded case data from YAML input (input/*.yaml)")
                return self._yaml_to_state(case_path, yaml_data)
            logger.warning(
                "YAML input has errors, falling back to markdown: %s",
                yaml_data["errors"],
            )
            self._errors.extend(yaml_data["errors"])

        return self._load_markdown(case_path)

    def _load_markdown(self, case_path: str) -> dict:
        """Parse the 00_COMMON markdown intake form."""
        common_dir = Path(case_path) / "00_COMMON"

        company_context = self._load_company_context(common_dir)
        architecture_inventory = self._load_architecture_inventory(common_dir)
        stakeholders, business_goals = self._load_stakeholders_and_goals(common_dir)
        taxonomy_entries = self._load_taxonomy_reference(common_dir)
        ontology = self._load_ontology(common_dir)
        regulations = self._extract_regulations(ontology)
        subdomains = self._extract_subdomains(taxonomy_entries)

        return {
            "company_context": company_context,
            "architecture_inventory": architecture_inventory,
            "stakeholders": stakeholders,
            "business_goals": business_goals,
            "taxonomy_entries": taxonomy_entries,
            "ontology": ontology,
            "regulations": regulations,
            "subdomains": subdomains,
            "errors": list(self._errors),
        }

    def _yaml_to_state(self, case_path: str, yaml_data: dict) -> dict:
        """Convert YAML input data to the standard loader return shape.

        Taxonomy, ontology, and subdomains are NOT in the YAML schema —
        they live in 00_COMMON markdown files and are loaded from there
        so behaviour stays identical when YAML input is provided.
        """
        common_dir = Path(case_path) / "00_COMMON"
        taxonomy_entries = self._load_taxonomy_reference(common_dir)
        ontology = self._load_ontology(common_dir)
        regulations = self._extract_regulations(ontology)
        subdomains = self._extract_subdomains(taxonomy_entries)

        return {
            "company_context": self._yaml_to_company_context(yaml_data["company"]),
            "architecture_inventory": self._yaml_to_architecture_inventory(yaml_data["architecture"]),
            "stakeholders": self._yaml_to_stakeholders(yaml_data["stakeholders"]),
            "business_goals": self._yaml_to_business_goals(yaml_data["business_goals"]),
            "taxonomy_entries": taxonomy_entries,
            "ontology": ontology,
            "regulations": regulations,
            "subdomains": subdomains,
            "errors": list(self._errors),
        }

    def _yaml_to_company_context(self, company_data: dict | None) -> CompanyContext | None:
        """Build CompanyContext model from classification.yaml content."""
        if not company_data or "company" not in company_data:
            return None
        c = company_data["company"]
        from aegis_phase1.models import ComplexityTier

        applicable = [
            r["abbreviation"]
            for r in company_data.get("applicable_regulations", [])
            if r.get("applicable")
        ]
        try:
            complexity_tier = ComplexityTier(c.get("complexity_tier", "MEDIUM"))
        except ValueError:
            complexity_tier = ComplexityTier.MEDIUM

        return CompanyContext(
            company_name=c.get("name", ""),
            sector=c.get("sector", ""),
            jurisdiction=c.get("jurisdiction", "EU"),
            employees=int(c.get("employees", 0)),
            revenue=float(c.get("revenue_eur", 0.0)),
            scale=c.get("scale", ""),
            applicable_regs=applicable,
            complexity_tier=complexity_tier,
            security_fte=float(c.get("security_fte", 0.0)),
            tech_stack=list(c.get("tech_stack", [])),
        )

    def _yaml_to_architecture_inventory(self, arch_data: dict) -> dict[str, list[dict]]:
        """Map architecture/* YAML files to the legacy inventory buckets."""
        systems = arch_data.get("systems", {}) or {}
        stores = arch_data.get("data_stores", {}) or {}
        flows = arch_data.get("data_flows", {}) or {}
        services = arch_data.get("cloud_services", {}) or {}
        auth = arch_data.get("auth_systems", {}) or {}

        def _records(d: dict, key: str) -> list[dict]:
            items = d.get(key, []) if isinstance(d, dict) else []
            return [dict(item) for item in items] if isinstance(items, list) else []

        return {
            "systems": _records(systems, "systems"),
            "cloud_services": _records(services, "services"),
            "auth_systems": _records(auth, "auth_systems"),
            "data_stores": _records(stores, "stores"),
            "data_flows": _records(flows, "flows"),
            "data_subjects": [],
        }

    def _yaml_to_stakeholders(self, stakeholders_data: dict | None) -> list[dict]:
        """Normalise stakeholders YAML to a list of dicts."""
        if not stakeholders_data:
            return []
        items = stakeholders_data.get("stakeholders", [])
        return [dict(item) for item in items] if isinstance(items, list) else []

    def _yaml_to_business_goals(self, goals_data: dict | None) -> list[dict]:
        """Normalise business_goals YAML to a list of dicts."""
        if not goals_data:
            return []
        items = goals_data.get("goals", [])
        return [dict(item) for item in items] if isinstance(items, list) else []

    def _load_company_context(self, common_dir: Path) -> CompanyContext | None:
        """Parse 01_Company_Context.md into a CompanyContext model."""
        path = common_dir / "01_Company_Context.md"
        if not path.exists():
            logger.warning("Company context file not found: %s", path)
            self._errors.append(f"Missing 01_Company_Context.md: {path}")
            return None

        try:
            text = path.read_text(encoding="utf-8")
            frontmatter = _parse_yaml_fm(text)
            company_name = frontmatter.get("title", "")
            sector = ""
            employees = 0
            revenue = 0.0
            complexity_tier_str = "MEDIUM"
            tech_stack: list[str] = []
            security_fte = 0.0
            scale = ""
            jurisdiction = "EU"

            body = _strip_frontmatter(text)
            lines = body.splitlines()
            applicable_regs = _extract_applicable_regs(lines)
            current_section = ""

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### 2.1 Basic Information"):
                    current_section = "basic"
                elif stripped.startswith("### 2.2 Size Classification"):
                    current_section = "size"
                elif stripped.startswith("### 2.3 Business Sector"):
                    current_section = "sector"
                elif stripped.startswith("## 3. LAYER 1"):
                    current_section = "layer1"
                elif stripped.startswith("### 3.1 GDPR"):
                    current_section = "gdpr"
                elif stripped.startswith("### 3.2 CRA"):
                    current_section = "cra"
                elif stripped.startswith("### 3.3 NIS 2"):
                    current_section = "nis2"
                elif stripped.startswith("### 3.4 DORA"):
                    current_section = "dora"
                elif stripped.startswith("### 3.5 AI Act"):
                    current_section = "aiact"
                elif stripped.startswith("### ") or stripped.startswith("## ") or stripped.startswith("---"):
                    current_section = ""

                if current_section == "basic" and "Company Legal Name" in stripped:
                    company_name = _extract_table_value(stripped)
                if current_section == "basic" and "Registration Country" in stripped:
                    jurisdiction = _extract_table_value(stripped)
                if current_section == "size" and "Number of Employees" in stripped:
                    raw = _extract_table_value(stripped)
                    try:
                        employees = int(raw.split()[0])
                    except (ValueError, IndexError):
                        employees = 0
                if current_section == "size" and "Annual Revenue" in stripped:
                    revenue = 2_000_000.0 if "2M" in stripped else 0.0
                if current_section == "size" and "EU Size Classification" in stripped:
                    scale = _extract_table_value(stripped)
                if current_section == "sector" and "Primary Industry Sector" in stripped:
                    sector = _extract_table_value(stripped)
                if "Complexity Tier" in stripped and "MEDIUM" in stripped:
                    complexity_tier_str = "MEDIUM"
                if "Complexity Tier" in stripped and "LOW" in stripped:
                    complexity_tier_str = "LOW"
                if "Complexity Tier" in stripped and "HIGH" in stripped:
                    complexity_tier_str = "HIGH"
                if ("technologicalControlPlane" in stripped or "Cloud" in stripped) and ":" in stripped:
                    val = stripped.split(":", 1)[1].strip().strip('"').strip("`")
                    if val:
                        new_items = [t.strip() for t in val.replace("(", "").replace(")", "").split("/") if t.strip()]
                        for item in new_items:
                            if item not in tech_stack:
                                tech_stack.append(item)

            from aegis_phase1.models import ComplexityTier
            try:
                complexity_tier = ComplexityTier(complexity_tier_str)
            except ValueError:
                complexity_tier = ComplexityTier.MEDIUM

            return CompanyContext(
                company_name=company_name,
                sector=sector,
                jurisdiction=jurisdiction,
                employees=employees,
                revenue=revenue,
                scale=scale,
                applicable_regs=applicable_regs,
                complexity_tier=complexity_tier,
                security_fte=security_fte,
                tech_stack=tech_stack,
            )
        except Exception:
            logger.exception("Failed to parse company context from %s", path)
            self._errors.append(f"Error parsing company context: {path}")
            return None

    def _load_architecture_inventory(self, common_dir: Path) -> dict[str, list[dict]]:
        """Parse the N.1-N.6 architecture inventory Markdown tables."""
        inventory = {
            "systems": [],
            "cloud_services": [],
            "auth_systems": [],
            "data_stores": [],
            "data_flows": [],
            "data_subjects": [],
        }
        path = common_dir / "01_Company_Context.md"
        if not path.exists():
            return inventory

        section_keys = {
            "N.1 Systems": "systems",
            "N.2 Cloud Services": "cloud_services",
            "N.3 Authentication & Identity Systems": "auth_systems",
            "N.4 Data Stores": "data_stores",
            "N.5 Data Flows": "data_flows",
            "N.6 Data Subject Categories": "data_subjects",
        }
        try:
            lines = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
            current_key = ""
            headers: list[str] = []
            for line in lines:
                stripped = line.strip()
                if stripped.startswith("### "):
                    current_key = section_keys.get(stripped[4:].strip(), "")
                    headers = []
                    continue
                if not current_key or not stripped.startswith("|"):
                    continue
                cells = [cell.strip() for cell in stripped.strip("|").split("|")]
                if not headers:
                    headers = [_normalise_header(cell) for cell in cells]
                    continue
                if _is_separator_row(cells):
                    continue
                if len(cells) != len(headers):
                    logger.warning(
                        "Skipping malformed architecture inventory row in %s: %s",
                        path,
                        stripped,
                    )
                    continue
                inventory[current_key].append(dict(zip(headers, cells, strict=True)))
        except (OSError, UnicodeError):
            logger.exception("Failed to read architecture inventory from %s", path)
        return inventory

    def _load_stakeholders_and_goals(
        self, common_dir: Path
    ) -> tuple[list[dict], list[dict]]:
        """Parse §10 Stakeholders and §11 Business Goals from 01_Company_Context.md.

        Scans the markdown body for the ``## 10. STAKEHOLDERS`` and
        ``## 11. BUSINESS GOALS`` headers and reads the first ``|``-table
        that follows each header. Returns an empty list when a section is
        missing so the caller can fall back to the deterministic default
        stakeholder set (TinyTask 7-stakeholder baseline).

        Returns:
            Tuple ``(stakeholders, business_goals)`` where each list
            contains dicts with normalised column-name keys
            (``id``, ``name``, ``role``, ``organisation``, ``contact``,
            ``responsibilities``, ``priority``, ``related_regs``,
            ``success_metric``, ``description``).
        """
        stakeholders: list[dict] = []
        business_goals: list[dict] = []
        path = common_dir / "01_Company_Context.md"
        if not path.exists():
            return stakeholders, business_goals

        try:
            lines = _strip_frontmatter(path.read_text(encoding="utf-8")).splitlines()
        except (OSError, UnicodeError):
            logger.exception("Failed to read 01_Company_Context.md for stakeholders/goals")
            return stakeholders, business_goals

        sections = {
            "## 10. STAKEHOLDERS": "stakeholders",
            "## 11. BUSINESS GOALS": "business_goals",
        }
        target: str | None = None
        headers: list[str] = []
        for line in lines:
            stripped = line.strip()
            matched = False
            for header, bucket in sections.items():
                if stripped.startswith(header):
                    target = bucket
                    headers = []
                    matched = True
                    break
            if matched:
                continue
            if target is None:
                continue
            # Stop when the next ## section begins.
            if stripped.startswith("## ") and not stripped.startswith("### "):
                target = None
                headers = []
                continue
            if not stripped.startswith("|"):
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if not headers:
                headers = [_normalise_header(c) for c in cells]
                continue
            if _is_separator_row(cells):
                continue
            if len(cells) != len(headers):
                continue
            row = dict(zip(headers, cells, strict=True))
            if target == "stakeholders":
                stakeholders.append(row)
            else:
                business_goals.append(row)
        return stakeholders, business_goals

    def _load_taxonomy_reference(self, common_dir: Path) -> list[dict]:
        path = common_dir / "00_Taxonomy_Reference.md"
        if not path.exists():
            logger.warning("Taxonomy reference not found: %s", path)
            self._errors.append(f"Missing 00_Taxonomy_Reference.md: {path}")
            return []

        try:
            text = path.read_text(encoding="utf-8")
            body = _strip_frontmatter(text)
            entries: list[dict] = []
            in_catalog = False
            in_table = False

            for line in body.splitlines():
                stripped = line.strip()
                if "## 3. SUB-DOMAIN CATALOG" in stripped:
                    in_catalog = True
                    continue
                if in_catalog and stripped.startswith("### "):
                    continue
                if in_catalog and stripped.startswith("| "):
                    if not in_table:
                        in_table = True
                        continue
                    if in_table and "---" in stripped:
                        continue
                    if in_table:
                        cells = [c.strip() for c in stripped.strip("|").split("|")]
                        if len(cells) >= 4:
                            sid = cells[0]
                            name = cells[1]
                            driver = cells[2]
                            ni_str = cells[3]
                            try:
                                ni = float(ni_str)
                            except ValueError:
                                ni = 0.0
                            entries.append({
                                "id": sid,
                                "name": name,
                                "regulatory_driver": driver,
                                "normative_intensity": ni,
                            })
                if in_catalog and not stripped and in_table:
                    in_table = False
                if in_catalog and stripped.startswith("## ") and "SUB-DOMAIN CATALOG" not in stripped and "D-" not in stripped:
                    break
            return entries
        except Exception:
            logger.exception("Failed to parse taxonomy reference from %s", path)
            self._errors.append(f"Error parsing taxonomy reference: {path}")
            return []

    def _load_ontology(self, common_dir: Path) -> dict:
        """Load and parse phase1_ontology.yaml."""
        path = common_dir / "phase1_ontology.yaml"
        if not path.exists():
            logger.warning("Ontology file not found: %s", path)
            self._errors.append(f"Missing phase1_ontology.yaml: {path}")
            return {}

        try:
            text = path.read_text(encoding="utf-8")
            data = yaml.safe_load(text)
            return data if isinstance(data, dict) else {}
        except Exception:
            logger.exception("Failed to parse ontology from %s", path)
            self._errors.append(f"Error parsing ontology: {path}")
            return {}

    def _extract_regulations(self, ontology: dict) -> list[dict]:
        """Extract regulation descriptors from ontology."""
        regs = ontology.get("regulations", [])
        if isinstance(regs, list):
            return list(regs)
        return []

    def _extract_subdomains(self, taxonomy_entries: list[dict]) -> list[dict]:
        """Extract subdomain list from taxonomy entries."""
        return [
            {"id": e["id"], "name": e["name"]}
            for e in taxonomy_entries
            if e.get("id", "").startswith("D-")
        ]


def _normalise_header(header: str) -> str:
    """Normalise a Markdown table header into a stable dictionary key."""
    normalised = re.sub(r"[^a-z0-9]+", "_", header.strip().lower())
    return normalised.strip("_")


def _is_separator_row(cells: list[str]) -> bool:
    """Return whether all cells form a Markdown table separator row."""
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells)


def _extract_table_value(line: str) -> str:
    """Extract the second column value from a markdown table row."""
    parts = [p.strip() for p in line.split("|")]
    if len(parts) >= 3:
        return parts[2]
    return ""


def _extract_applicable_regs(lines: list[str]) -> list[str]:
    """Extract applicable_regs from the APPLICABILITY SUMMARY table only.

    Locates the ``### 3.6 APPLICABILITY`` (or ``### 3.6 APPLICABILITY
    SUMMARY``) header and scans ONLY the rows that follow until the next
    ``### `` or ``## `` markdown header. This bounded scan prevents
    section-state leakage from later analysis sections (e.g., negative
    applicability checklists) where the same regulation keywords appear
    alongside ``YES``/``NO`` for non-applicability rationale.

    Returns:
        Ordered list of regulation names (e.g.,
        ``["GDPR", "CRA"]``) whose row contains ``YES``.
    """
    start: int | None = None
    for i, line in enumerate(lines):
        if _APPLICABILITY_SUMMARY_PATTERN.match(line.strip()):
            start = i
            break
    if start is None:
        return []

    end = len(lines)
    for j in range(start + 1, len(lines)):
        stripped = lines[j].strip()
        if stripped.startswith("### ") or stripped.startswith("## "):
            end = j
            break

    applicable: list[str] = []
    detection_order = (
        (r"\bGDPR\b", "GDPR"),
        (r"\bCRA\b", "CRA"),
        (r"\bNIS\s*2\b", "NIS2"),
        (r"\bDORA\b", "DORA"),
        (r"\bAI\s*Act\b", "AI Act"),
    )
    for raw in lines[start:end]:
        stripped = raw.strip()
        if "YES" not in stripped:
            continue
        for pattern, name in detection_order:
            if re.search(pattern, stripped) and name not in applicable:
                applicable.append(name)
                break
    return applicable
