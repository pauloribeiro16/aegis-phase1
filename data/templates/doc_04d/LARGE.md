<!-- data/templates/doc_04d/LARGE.md -->

## 5. Reporting Lines

For LARGE tier, the reporting structure includes:
- CEO with direct reports (CISO, CRO, DPO, Head of Compliance)
- CTO with CISO, Head of Security, Head of AI/ML, VP Engineering
- Board with Audit Committee (independent)

```
                                ┌──────────────────────┐
                                │         Board          │
                                │   (Audit Committee)    │
                                └────────────┬──────────┘
                                             │
                ┌────────────────────────────┼───────────────────────────┐
                │                            │                            │
         ┌──────▼──────┐            ┌────────▼────────┐            ┌──────▼──────┐
         │     CEO      │            │      CTO       │            │     CFO      │
         │              │            │                 │            │              │
         └──────┬──────┘            └────────┬────────┘            └──────────────┘
                │                            │
        ┌───────┼────────┐                  ┌──┼─────────────────────────┐
        │       │        │                  │                            │
   ┌────▼─┐ ┌──▼────┐ ┌─▼─────────┐ ┌────▼────────┐ ┌────▼──────────┐ ┌──▼────────┐
   │ DPO  │ │ CISO  │ │  CRO      │ │ VP Eng      │ │ Head of AI/ML │ │ Head of   │
   │      │ │       │ │           │ │             │ │              │ │ Compliance│
   └──────┘ └───────┘ └───────────┘ └─────────────┘ └──────────────┘ └────────────┘
```

## 7. Training Status

For LARGE tier: annual security awareness required by Art. 39 GDPR;
role-specific training for engineers (CRA Annex I §2); quarterly
phishing simulation; mandatory DPO training per Art. 38-39.

## 9. Gaps and Known Limitations

- Three-lines-of-defense separation required for DORA Art. 5
- DPO must be independent per Art. 37 if sensitive processing at scale
- NIS2 24h early-warning workflow requires dedicated on-call rotation