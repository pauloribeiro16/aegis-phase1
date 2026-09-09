"""AEGIS evaluation & diagnostic scripts.

Sprint-contract deliverable CORR-116 S1 lives in
:mod:`scripts.eval.parser_replay` — an offline harness that replays
the raw LLM corpus under ``output/phase1/raw/<SPEC>/*.md`` through its
registered parser to build a per-(spec, model) failure matrix.
"""
