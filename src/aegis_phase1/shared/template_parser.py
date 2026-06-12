"""Parse Markdown templates into section objects for LLM section-by-section filling."""

import re
from dataclasses import dataclass


@dataclass
class Section:
    """A single section of a Markdown template."""

    level: int
    header: str
    body: str
    index: int


_HEADER_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)


def parse_sections(template: str) -> list[Section]:
    """Split a Markdown template into sections by `#{1,3}` headers.

    Each section includes the header line + all content until the next header.
    Content before the first header is the "preamble" (level=0, header="").
    H1 sections are typically metadata (title, document ID).
    H2/H3 are content sections to be processed.
    """
    if not template or not template.strip():
        return []

    sections = []
    matches = list(_HEADER_RE.finditer(template))

    if not matches:
        return [Section(level=0, header="", body=template.strip(), index=0)]

    preamble = template[: matches[0].start()].strip()
    if preamble:
        sections.append(Section(level=0, header="", body=preamble, index=0))

    for i, m in enumerate(matches):
        header_line = m.group(0)
        level = len(m.group(1))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(template)
        body = template[body_start:body_end].strip()

        sections.append(
            Section(
                level=level,
                header=header_line,
                body=body,
                index=len(sections),
            )
        )

    return sections
