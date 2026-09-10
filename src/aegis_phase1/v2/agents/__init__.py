"""CORR-118: agent layer for Doc 05 (piloto — qwen3.8 only).

Ciclo: DrafterAgent escreve secções em markdown → DeterministicGate valida
estrutura (custo ~zero) → ReviewerAgent avalia contra o subconjunto do
OBJECTIVES_CONTRACT → revisão via feedback ≤ N ciclos. Só secções com gate
+ review a PASS entram no Doc 05; raws ficam em sidecar, nunca no doc.

Objectivos do contracto usados como checklist do reviewer: OBJ-01, OBJ-02,
OBJ-03, OBJ-09, OBJ-12 (ver docs/OBJECTIVES_CONTRACT.md §2.1-2.2).
"""

from aegis_phase1.v2.agents.drafter import DrafterAgent
from aegis_phase1.v2.agents.gate import DeterministicGate, GateResult
from aegis_phase1.v2.agents.loop import run_doc05_agent_loop
from aegis_phase1.v2.agents.reviewer import ReviewerAgent, ReviewVerdict

__all__ = [
    "DeterministicGate",
    "DrafterAgent",
    "GateResult",
    "ReviewVerdict",
    "ReviewerAgent",
    "run_doc05_agent_loop",
]
