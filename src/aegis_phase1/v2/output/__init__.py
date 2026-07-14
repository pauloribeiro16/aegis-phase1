"""output — shared helpers for Phase 1 v2 markdown and xlsx generators.

Exposes :func:`generate_frontmatter`, :func:`write_output`,
:func:`markdown_table`, and small convenience accessors that all
``doc_XX`` modules and the :func:`xlsx_generator.generate_xlsx`
function depend on. Keeping these in one place avoids drift across the
five document renderers.

References:
    - contracts/SPRINT002_003_map_reduce_output.md (OUTPUT step)
"""

from ._common import (
    generate_frontmatter,
    markdown_table,
    next_version,
    safe_get,
    write_output,
)

__all__ = [
    "generate_frontmatter",
    "markdown_table",
    "next_version",
    "safe_get",
    "write_output",
]
