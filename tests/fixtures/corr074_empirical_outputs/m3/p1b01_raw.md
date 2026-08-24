## Status

OK — HIGH confidence. All catalog entries resolved against supplied company facts without ambiguity.

## Interpretations

### TIPO2-CRA-ART14-DUAL-FLOW — YES

Manufacturer classification is confirmed (Doc 04 §5) and the company's Main SaaS Application is a CRA-regulated digital product placed on the EU market. The dual reporting flow (ENISA within 24h + users on material impact) under CRA Art. 14(1) and Art. 14(2) structurally applies to this manufacturer.

- legal_refs: CRA Art. 14(1); CRA Art. 14(2)
- anchors: Annex I Part II §(7); Annex I Part II §(8)
- layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO; SubDomains/D-04_Incident-Response/D-04.3.md §1 CRDA CRA

### TIPO2-CRA-ART15-VOLUNTARY — YES

Company has a product (Main SaaS Application) on the EU market; Art. 15 voluntary reporting is structurally available to this manufacturer. Whether the company actively runs pre-exploitation vulnerability management is not stated in Doc 04, but the interpretation itself (availability of the voluntary channel) applies — the predicate `company_facts.products is not None` is satisfied.

- legal_refs: CRA Art. 15
- anchors: Annex I Part II §(7)
- layer0_refs: SubDomains/D-02_Vulnerability-Management/D-02.3.md §2 HSO

## Derogations

### TIPO3-CRA-NON-PLACED — NOT_ACTIVATED

Predicate requires `placing_on_eu_market == False` AND `making_available_in_eu == False`. Doc 04 facts set both flags to `true`. The derogation does not activate; CRA fully applies to this manufacturer.

- legal_refs: CRA Art. 2
- anchors: Annex I Part I §(2)
- layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO

### TIPO3-CRA-OPEN-SOURCE — NOT_ACTIVATED

Predicate requires `software_licence in [OSS variants]` AND `commercial_purpose == False`. Doc 04 states `software_licence: "Proprietary"` and `commercial_purpose: true`. The open-source derogation does not activate.

- legal_refs: CRA Recital 18
- anchors: Annex I Part I §(2)
- layer0_refs: SubDomains/D-07_Secure-Development/D-07.1.md §2 HSO

## Notes

Both derogation predicates fail on factual grounds (company is commercial and proprietary, product is placed/made-available in EU), so CRA scope is preserved with full manufacturer obligations. For TIPO2-CRA-ART15-VOLUNTARY, the entry applies structurally but practical uptake depends on whether the company runs active vulnerability management — Doc 04 §4b (security posture) does not explicitly confirm this; flag for human reviewer to decide if Art. 15 reporting should be operationalised in Doc 05. Tier is LOW (micro), so proportionality in Doc 05 should keep Art. 14/15 procedures lightweight but documented.