// ==============================================================================
// AEGIS-KG Phase 1 — Neo4j Schema DDL (Ontology v3)
// Reference: docs/NEO4J_PHASE1_ONTOLOGY_AND_NAVIGATION_SPEC.md §4
// Note: Includes fixes for composite keys on run-derived nodes and SO index.
// ==============================================================================

// ── Unique Constraints ───────────────────────────────────────────────────────
CREATE CONSTRAINT enterprise_pk      IF NOT EXISTS FOR (n:Enterprise)               REQUIRE n.case_id IS UNIQUE;
CREATE CONSTRAINT regulation_pk      IF NOT EXISTS FOR (n:Regulation)               REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT article_pk         IF NOT EXISTS FOR (n:Article)                  REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT clause_pk          IF NOT EXISTS FOR (n:RegulatoryClause)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT domain_pk          IF NOT EXISTS FOR (n:SecurityControlDomain)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT subdomain_pk       IF NOT EXISTS FOR (n:SubDomain)                REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT so_pk              IF NOT EXISTS FOR (n:SecurityObjective)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT hso_pk             IF NOT EXISTS FOR (n:HierarchicalSecurityObjective) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sso_pk             IF NOT EXISTS FOR (n:SubSecurityObjective)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT sr_pk              IF NOT EXISTS FOR (n:SecurityRule)             REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pair_pk            IF NOT EXISTS FOR (n:RegulatoryPair)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT role_pk            IF NOT EXISTS FOR (n:RegulatoryRole)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_fn_pk          IF NOT EXISTS FOR (n:CSFFunction)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_cat_pk         IF NOT EXISTS FOR (n:CSFCategory)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT csf_sub_pk         IF NOT EXISTS FOR (n:CSFSubcategory)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT system_pk          IF NOT EXISTS FOR (n:System)                   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datastore_pk       IF NOT EXISTS FOR (n:DataStore)                REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dataflow_pk        IF NOT EXISTS FOR (n:DataFlow)                 REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT authsys_pk         IF NOT EXISTS FOR (n:AuthSystem)               REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT thirdparty_pk      IF NOT EXISTS FOR (n:ThirdPartyService)        REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT datasubject_pk     IF NOT EXISTS FOR (n:DataSubject)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT externalparty_pk   IF NOT EXISTS FOR (n:ExternalParty)            REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT stakeholder_pk     IF NOT EXISTS FOR (n:Stakeholder)              REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bizgoal_pk         IF NOT EXISTS FOR (n:BusinessGoal)             REQUIRE n.id IS UNIQUE;

// Run node itself is keyed on run_id
CREATE CONSTRAINT run_pk             IF NOT EXISTS FOR (n:Run)                      REQUIRE n.run_id IS UNIQUE;

// Run-scoped entities: Composite keys (run_id + entity_id) to enable multi-model runs (fixes spec Errata P1)
CREATE CONSTRAINT sda_pk             IF NOT EXISTS FOR (n:SubDomainActivation)      REQUIRE (n.run_id, n.sub_domain_id) IS UNIQUE;
CREATE CONSTRAINT pa_pk              IF NOT EXISTS FOR (n:PairActivation)           REQUIRE (n.run_id, n.pair_id) IS UNIQUE;
CREATE CONSTRAINT ad_pk              IF NOT EXISTS FOR (n:AmbiguityDisposition)     REQUIRE (n.run_id, n.pair_id) IS UNIQUE;
CREATE CONSTRAINT gate_pk            IF NOT EXISTS FOR (n:Gate)                     REQUIRE (n.run_id, n.gate_type) IS UNIQUE;

// Other entity constraints
CREATE CONSTRAINT clauseact_pk       IF NOT EXISTS FOR (n:ClauseActivation)         REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ri_pk              IF NOT EXISTS FOR (n:RegulatoryInteraction)    REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pe_pk              IF NOT EXISTS FOR (n:ProportionalityEntry)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT gap_pk             IF NOT EXISTS FOR (n:DeclarationGap)           REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT rar_pk             IF NOT EXISTS FOR (n:RegulatoryApplicabilityResult) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT pp_pk              IF NOT EXISTS FOR (n:ProportionalityProfile)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ce_pk              IF NOT EXISTS FOR (n:ControlEvidence)          REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ext_pk             IF NOT EXISTS FOR (n:ConditionalExtension)     REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT bt_pk              IF NOT EXISTS FOR (n:BlockTrigger)             REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dce_pk             IF NOT EXISTS FOR (n:DomainCoverageEntry)      REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT dee_pk             IF NOT EXISTS FOR (n:DomainElaborationEntry)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT ca_pk              IF NOT EXISTS FOR (n:ComplementarityAnalysis)   REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT meta_pk            IF NOT EXISTS FOR (n:GraphMeta)                REQUIRE n.key IS UNIQUE;

// ── Lookup Indexes ───────────────────────────────────────────────────────────
CREATE INDEX system_case             IF NOT EXISTS FOR (n:System)                   ON (n.case_id);
CREATE INDEX datastore_case          IF NOT EXISTS FOR (n:DataStore)                ON (n.case_id);
CREATE INDEX dataflow_case           IF NOT EXISTS FOR (n:DataFlow)                 ON (n.case_id);
CREATE INDEX authsys_case            IF NOT EXISTS FOR (n:AuthSystem)               ON (n.case_id);
CREATE INDEX thirdparty_case         IF NOT EXISTS FOR (n:ThirdPartyService)        ON (n.case_id);
CREATE INDEX externalparty_case      IF NOT EXISTS FOR (n:ExternalParty)            ON (n.case_id);
CREATE INDEX stakeholder_case        IF NOT EXISTS FOR (n:Stakeholder)              ON (n.case_id);
CREATE INDEX bizgoal_case            IF NOT EXISTS FOR (n:BusinessGoal)             ON (n.case_id);
CREATE INDEX sda_run_subdomain       IF NOT EXISTS FOR (n:SubDomainActivation)      ON (n.run_id, n.sub_domain_id);
CREATE INDEX sda_run_case            IF NOT EXISTS FOR (n:SubDomainActivation)      ON (n.run_id, n.case_id);
CREATE INDEX pa_run_pair             IF NOT EXISTS FOR (n:PairActivation)           ON (n.run_id, n.pair_id);
CREATE INDEX ad_run_pair             IF NOT EXISTS FOR (n:AmbiguityDisposition)     ON (n.run_id, n.pair_id);
CREATE INDEX gate_run_type           IF NOT EXISTS FOR (n:Gate)                     ON (n.run_id, n.gate_type);
CREATE INDEX clauseact_case_clause   IF NOT EXISTS FOR (n:ClauseActivation)         ON (n.case_id, n.clause_id);
CREATE INDEX pe_case_subdomain       IF NOT EXISTS FOR (n:ProportionalityEntry)     ON (n.case_id, n.sub_domain_id);
CREATE INDEX ri_case_type            IF NOT EXISTS FOR (n:RegulatoryInteraction)    ON (n.case_id, n.interaction_type);
CREATE INDEX clause_reg              IF NOT EXISTS FOR (n:RegulatoryClause)         ON (n.regulation_id);

// Simple lookup index for SecurityObjective by regulation_code (fixes spec Errata P2)
CREATE INDEX so_reg                  IF NOT EXISTS FOR (n:SecurityObjective)        ON (n.regulation_code);

CREATE INDEX subdomain_macro         IF NOT EXISTS FOR (n:SubDomain)                ON (n.macro_id);
CREATE INDEX gap_case_severity       IF NOT EXISTS FOR (n:DeclarationGap)           ON (n.case_id, n.severity);
CREATE INDEX ce_domain               IF NOT EXISTS FOR (n:ControlEvidence)          ON (n.domain_id);
