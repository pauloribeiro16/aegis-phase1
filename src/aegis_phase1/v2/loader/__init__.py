"""loader — v2 input loaders.

Loaders in this package:
  - PreprocCatalogLoader (CORR-037-T1): typed JSON loader for preproc_out/
  - CaseProfileLoader    (CORR-037-T2): typed YAML loader for case inputs
  - ManifestLoader       (CORR-101 Gap 2): typed loader for
    ``D-XX.manifest.json`` (per-domain ai_act + NIST controls).
  - common_loader        (legacy v1, retained for ontology/taxonomy/regs)
  - preprocessing_loader (legacy v1, retained for preprocessing state)
  - yaml_input_loader    (helper for common_loader's YAML case loading)

CORR-037-T4b: helper functions (parse_yaml_frontmatter, etc.) are
inlined in their consumers (common_loader, preprocessing_loader) to
remove the v1 global YAML-frontmatter parser from this package.
"""

from aegis_phase1.v2.loader.manifest_loader import (
    Counts,
    Manifest,
    ManifestLoader,
    SubdomainSummary,
)

__all__: list[str] = [
    "Counts",
    "Manifest",
    "ManifestLoader",
    "SubdomainSummary",
]
