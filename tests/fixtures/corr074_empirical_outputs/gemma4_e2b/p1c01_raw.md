```json
{
  "prompt_spec_id": "P1C-LLM-01-OVERLAP-CLASSIFICATION",
  "invocation_pattern": "per_domain_lane",
  "lane_id": "D-01",
  "domain_id": "D-01",
  "domain_overlap_analysis": {
    "total_sub_domains": 2,
    "active_sub_domains": 2,
    "pairwise_relationships": 1
  },
  "sub_domain_activations": [
    {
      "sub_domain_id": "D-01.1",
      "applicable": true,
      "scope_overlap": "CONDITIONAL",
      "applicable_regulations": [
        "GDPR",
        "CRA"
      ],
      "verified_relationship_per_pair": [
        {
          "regulation_pair": "GDPR↔CRA",
          "verified_relationship": "CONDITIONAL"
        }
      ],
      "layer0_refs": [
        "SubDomains/D-01_Data-Protection/D-01.1.md",
        "CrossRegulation/DeepAnalysis/D-01.1.md"
      ]
    },
    {
      "sub_domain_id": "D-01.2",
      "applicable": true,
      "scope_overlap": "NOT_TRIGGERED",
      "applicable_regulations": [
        "GDPR",
        "CRA"
      ],
      "verified_relationship_per_pair": [
        {
          "regulation_pair": "GDPR↔CRA",
          "verified_relationship": "SCOPE_DISJOINT"
        }
      ],
      "layer0_refs": [
        "SubDomains/D-01_Data-Protection/D-01.2.md",
        "CrossRegulation/DeepAnalysis/D-01.2.md"
      ]
    }
  ],
  "status": "OK",
  "confidence": "HIGH"
}
```