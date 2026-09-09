
{
  "prompt_spec_id": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
  "schema_version": "1.0.0",
  "case_id": "case1-tinytask",
  "invocation_pattern": "per_domain_lane",
  "lane_id": "D-01",
  "domain_id": "D-01",
  "domain_overlap_analysis": {
    "total_sub_domains": 2,
    "active_sub_domains": 2,
    "pairwise_relationships": 2
  },
  "sub_domain_activations": [
    {
      "sub_domain_id": "D-01.1",
      "applicable": true,
      "scope_overlap": "Y",
      "applicable_regulations": ["GDPR", "CRA"],
      "verified_relationship_per_pair": [
        {
          "reg_pair": ["GDPR", "CRA"],
          "relationship": "SAME (CORRECTED — wording only)"
        }
      ],
      "layer0_refs": ["SubDomains/D-01.1.md §1 CRDA"]
    },
    {
      "sub_domain_id": "D-01.2",
      "applicable": true,
      "scope_overlap": "Y",
      "applicable_regulations": ["GDPR", "CRA"],
      "verified_relationship_per_pair": [
        {
          "reg_pair": ["GDPR", "CRA"],
          "relationship": "SAME (CORRECTED — wording only)"
        }
      ],
      "layer0_refs": ["SubDomains/D-01.2.md §1 CRDA"]
    }
  ],
  "status": "OK",
  "confidence": "HIGH"
}
