# AppCompiler AI — Backend

See the [project README](../README.md) for full documentation and [LOOM_SCRIPT.md](../LOOM_SCRIPT.md) for the video walkthrough.

## Run

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

Open **http://localhost:8000**

## Key Modules

| Path | Purpose |
|------|---------|
| `llm/prompt_analyzer.py` | Deterministic NL prompt profiling |
| `llm/mock_generator.py` | Rich AppConfig generation (mock mode) |
| `pipeline/validator.py` | Cross-layer validation rules |
| `pipeline/repair_engine.py` | Layer-targeted repair |
| `pipeline/runtime_simulator.py` | Executable checks |
| `pipeline/evaluator.py` | Orchestrator + batch evaluation |
| `data/evaluation_prompts.json` | 20 test prompts |

## Environment

Copy `.env.example` to `.env`. Default: `LLM_PROVIDER=mock` (no API key).
