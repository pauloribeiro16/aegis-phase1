"""loader — v2 input loaders.

Loaders in this package:
  - PreprocCatalogLoader (CORR-037-T1): typed JSON loader for preproc_out/
  - CaseProfileLoader    (CORR-037-T2): typed YAML loader for case inputs
  - common_loader        (legacy v1, retained for ontology/taxonomy/regs)
  - preprocessing_loader (legacy v1, retained for preprocessing state)
  - yaml_input_loader    (helper for common_loader's YAML case loading)

CORR-037-T4b: helper functions (parse_yaml_frontmatter, etc.) are
inlined in their consumers (common_loader, preprocessing_loader) to
remove the v1 global YAML-frontmatter parser from this package.
"""

__all__: list[str] = []
