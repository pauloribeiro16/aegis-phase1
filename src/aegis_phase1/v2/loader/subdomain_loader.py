"""subdomain_loader — Load sub-domain preprocessing files (D-*.md).

Scans the SubDomains directory recursively for all D-*.md files,
parses YAML frontmatter and the three sections (CRDA, HSO,
Security Requirements).

References:
    - contracts/SPRINT001_v2-core.md (C-003)
"""

import logging
import re
from pathlib import Path

import yaml

from aegis_phase1.v2.loader import _parse_yaml_frontmatter, _strip_frontmatter
from aegis_phase1.v2.state import SubDomainDef

logger = logging.getLogger(__name__)


HEADER_RE = re.compile(r"^###\s+D-(\d+)\.(\d+)\.(\d+)\b")


class SubDomainLoader:
    """Loader for sub-domain preprocessing files.

    Finds all D-*.md files under the given path and parses each
    into a SubDomainDef model.
    """

    def load(self, subdomains_path: str) -> dict[str, SubDomainDef]:
        """Load all sub-domain files into a dict keyed by sub-domain ID.

        Args:
            subdomains_path: Path to the SubDomains/ directory.

        Returns:
            Dict mapping sub-domain IDs (e.g. ``D-01.1``) to
            SubDomainDef instances.
        """
        base = Path(subdomains_path)
        if not base.exists():
            logger.warning("SubDomains path not found: %s", base)
            return {}

        result: dict[str, SubDomainDef] = {}
        files = sorted(base.glob("**/D-*.md"))

        for filepath in files:
            try:
                subdomain = self._parse_file(filepath)
                if subdomain:
                    key = subdomain.document_id.split("-")[-1] if "-" in subdomain.document_id else filepath.stem
                    if not key.startswith("D-"):
                        key = filepath.stem
                    result[key] = subdomain
            except Exception:
                logger.exception("Failed to parse subdomain file: %s", filepath)

        return result

    def _parse_file(self, filepath: Path) -> SubDomainDef | None:
        """Parse a single D-*.md file into a SubDomainDef.

        Args:
            filepath: Path to the markdown file.

        Returns:
            SubDomainDef instance, or None if parsing fails.
        """
        try:
            text = filepath.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Could not read %s", filepath)
            return None

        frontmatter = _parse_yaml_frontmatter(text)
        document_id = frontmatter.get("document_id", filepath.stem)
        title = frontmatter.get("title", filepath.stem)
        status = frontmatter.get("status", "DRAFT")

        body = _strip_frontmatter(text)

        section1 = self._parse_section1(body)
        section2 = self._parse_section2(body)
        section3 = self._parse_section3(body)

        return SubDomainDef(
            document_id=document_id,
            title=title,
            status=status,
            section1_crda=section1,
            section2_hso=section2,
            section3_requirements=section3,
            frontmatter=frontmatter,
        )

    def _parse_section1(self, body: str) -> list[dict]:
        """Parse section 1 — Cross-Regulation Analysis.

        Extracts pair analyses between ``#### Pair:`` markers.
        """
        pairs: list[dict] = []
        pair_pattern = re.compile(r"^####\s+Pair:\s*(.+)$", re.MULTILINE)
        matches = list(pair_pattern.finditer(body))

        for i, match in enumerate(matches):
            pair_name = match.group(1).strip()
            start = match.end()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
            pair_text = body[start:end].strip()
            pairs.append({
                "pair": pair_name,
                "text": pair_text,
            })

        return pairs

    def _parse_section2(self, body: str) -> dict:
        """Parse section 2 — Hierarchical Security Objective.

        Extracts the high-level objective, sub-SOs, and emergent
        tensions if present.
        """
        section2_start = re.search(
            r"^##\s+2\.\s+Hierarchical Security Objective", body, re.MULTILINE
        )
        if not section2_start:
            return {}

        section3_start = re.search(
            r"^##\s+3\.\s+Security Requirements", body, re.MULTILINE
        )
        section2_end = section3_start.start() if section3_start else len(body)
        section2_text = body[section2_start.end():section2_end].strip()

        hl_objective = ""
        per_reg_sos: list[dict] = []
        emergent_tensions: list[dict] = []

        lines = section2_text.splitlines()
        current_sub = ""
        current_sub_lines: list[str] = []
        in_emergent = False

        for line in lines:
            stripped = line.strip()
            header_match = HEADER_RE.match(stripped) if stripped.startswith("### D-") else None
            if header_match:
                suffix = header_match.group(3)
                if suffix == "0":
                    hl_objective = "\n".join(current_sub_lines) if current_sub_lines else stripped
                    current_sub_lines = [stripped]
                else:
                    if current_sub_lines:
                        text_block = "\n".join(current_sub_lines)
                        if current_sub:
                            per_reg_sos.append({
                                "id": current_sub,
                                "text": text_block,
                            })
                    current_sub = stripped.replace("### ", "").strip()
                    current_sub_lines = [stripped]
            elif stripped.startswith("### ") and (
                "Emergent tensions" in stripped or "emergent tensions" in stripped
            ):
                in_emergent = True
                if current_sub_lines:
                    text_block = "\n".join(current_sub_lines)
                    if current_sub:
                        per_reg_sos.append({
                            "id": current_sub,
                            "text": text_block,
                        })
                current_sub_lines = []
                current_sub = ""
            elif in_emergent:
                emergent_tensions.append({"text": stripped})
            else:
                current_sub_lines.append(stripped)

        if current_sub_lines and current_sub:
            text_block = "\n".join(current_sub_lines)
            per_reg_sos.append({
                "id": current_sub,
                "text": text_block,
            })

        return {
            "hl_objective": hl_objective,
            "per_reg_sos": per_reg_sos,
            "emergent_tensions": emergent_tensions,
        }

    def _parse_section3(self, body: str) -> list[dict]:
        """Parse section 3 — Security Requirements (Volere YAML blocks)."""
        section3_start = re.search(
            r"^##\s+3\.\s+Security Requirements", body, re.MULTILINE
        )
        if not section3_start:
            return []

        section3_text = body[section3_start.end():].strip()

        requirements: list[dict] = []
        yaml_blocks = re.findall(
            r"```yaml\n(.*?)```", section3_text, re.DOTALL
        )

        for block in yaml_blocks:
            try:
                data = yaml.safe_load(block)
                if isinstance(data, list):
                    requirements.extend(data)
                elif isinstance(data, dict):
                    requirements.append(data)
            except Exception:
                logger.debug("Could not parse YAML requirement block", exc_info=True)

        return requirements

