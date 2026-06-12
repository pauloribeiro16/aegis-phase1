# aegis-phase1

Standalone Phase 1 workflow from the AEGIS-KG project — Compliance Context Assessment.

Takes a company's profile and a set of applicable regulations (GDPR, CRA, NIS2, DORA, AI Act), and produces:

- **Doc 04** — Company Context Assessment
- **Doc 05** — Regulatory Applicability
- **Doc 06** — Clause Mapping Matrix
- **Doc 07** — Structured Compliance Matrix

The pipeline runs as a LangGraph state machine with 7-9 LLM calls total (down from ~150 in the pre-architecture version). All deterministic logic (coverage aggregation, compliance matrix assembly, document rendering) is implemented as zero-LLM nodes.

## Installation

```bash
git clone https://github.com/pauloribeiro16/aegis-phase1.git
cd aegis-phase1
pip install -e ".[all]"
cp .env.example .env
# Edit .env with your Ollama config
```

## Quick Start

```bash
# Run with mock LLM (no Ollama needed, useful for testing)
MOCK_LLM=true python -c "
from aegis_phase1 import run_phase1
result = run_phase1('cases/case1-tinytask', mock_llm=True)
print('Output docs:', list(result.get('doc_paths', {}).keys()))
"

# Run with real Ollama
python -c "
from aegis_phase1 import run_phase1
result = run_phase1('cases/case1-tinytask')
"
```

## Architecture

```
START → parse_inputs → subphase_a → subphase_b → subphase_c → END
                       (foundations)  (regulation) (analysis)
```

- **SubPhase A** — Company context, stakeholders, business goals, complexity tier
- **SubPhase B** — Load regulations, batch-enrich clauses, map to domains, compute coverage
- **SubPhase C** — Complementarity analysis, domain elaboration, strategic implications, obligation shells, structured matrix, document production

## Project Structure

```
aegis-phase1/
├── src/aegis_phase1/        # The pipeline package
│   ├── graph.py             # LangGraph state machine
│   ├── state.py             # TypedDict state definitions
│   ├── models.py            # Pydantic models (21 classes + 9 enums)
│   ├── nodes/               # 23 active node files
│   ├── subphases/           # Subphase orchestrators
│   ├── parsers/             # CSV/YAML/JSON parsers
│   ├── prompts/             # LLM prompt templates
│   ├── llm/                 # Ollama LLM client + tracing
│   ├── shared/              # Document producer + template parser
│   ├── config/              # Case config loader
│   ├── logging_config.py    # Logging setup
│   └── env.py               # .env loader
│
├── cases/case1-tinytask/    # Example case data
│   ├── case.yaml            # Case config
│   ├── context/             # Intake documents
│   ├── data/phase1/         # 22 CSV files
│   └── templates/phase1/    # 4 output templates
│
└── tests/                   # 20+ unit tests
```

## Development

```bash
# Run tests
pytest tests/unit/ -v

# Lint
ruff check src/ tests/

# Type check
mypy src/

# Install pre-commit hooks
pre-commit install
```

## License

Proprietary — see license terms.
