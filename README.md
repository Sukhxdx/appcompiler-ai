# AppCompiler AI

An AI engineer internship demo that converts natural language app requirements into a **strict, validated, executable application configuration**.

## What It Does

AppCompiler AI is a **compiler-like pipeline** — not a single LLM call. It transforms prose into structured `AppConfig` JSON that can be validated, repaired, and simulated before any code is generated.

```
Natural Language  →  Intent  →  Design  →  Schema  →  Validate  →  Repair  →  Simulate  →  AppConfig
```

## Quick Start

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Open **[http://localhost:8000](http://localhost:8000)** — UI is served by FastAPI (no Node.js required).

### Run Frontend (Optional React UI)

Requires Node.js 18+.

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**. The Vite dev server proxies API calls to `http://localhost:8000` — keep the backend running in another terminal.

To build for production: `npm run build` (output in `frontend/dist/`).

### Deterministic Mock Mode (Default)

```bash
export LLM_PROVIDER=mock   # default — no API key needed
```

The mock provider uses `llm/prompt_analyzer.py` and `llm/mock_generator.py` to produce rich, deterministic configs from keyword analysis. Same prompt → same output.

### Optional LLM Providers

```bash
export LLM_PROVIDER=openai
export OPENAI_API_KEY=sk-...

export LLM_PROVIDER=gemini
export GEMINI_API_KEY=...
```

## Architecture

| Stage | Module | Output |
|-------|--------|--------|
| 1. Intent Extraction | `pipeline/intent_extractor.py` | Entities, roles, ambiguities |
| 2. System Design | `pipeline/system_designer.py` | Pages, endpoints, tables |
| 3. Schema Generation | `pipeline/schema_generator.py` | Strict `AppConfig` |
| 4. Validation | `pipeline/validator.py` | Cross-layer consistency report |
| 5. Repair Engine | `pipeline/repair_engine.py` | Layer-targeted fixes |
| 6. Runtime Simulation | `pipeline/runtime_simulator.py` | `executable: true/false` |
| 7. Evaluation | `pipeline/evaluator.py` | Batch metrics on 20 prompts |

## Validation Strategy

Cross-layer rules in `pipeline/validator.py`:

- **Forms** → must map to POST/PUT endpoints with matching request fields
- **Tables** → must map to GET endpoints via `props.data_endpoint`
- **Dashboard cards** → must use metric fields (not email/password)
- **API request fields** → must exist in referenced DB table
- **Admin user management** → requires `/admin/users` page + `GET /api/users`
- **Payments/premium** → requires `subscriptions` or `payments` tables
- **Auth roles** → must reference existing pages and endpoints
- **Business rules** → must reference existing roles and entities

## Repair Strategy

`pipeline/repair_engine.py` repairs **only the broken layer**:

| Issue | Repair |
|-------|--------|
| Missing DB field | Add field with safe default + log note |
| Missing admin users page | Add `/admin/users` with `users_table` |
| Dashboard has login fields | Replace with metric fields |
| Table has no GET endpoint | Add GET endpoint + `data_endpoint` |
| Missing payments infra | Add subscriptions/payments tables |
| Unknown role refs | Prune or flag `clarification_needed` |

Max 5 repair iterations. Never regenerates the full config.

## Runtime Simulation

`pipeline/runtime_simulator.py` returns `executable: true` only when:

- All pages are renderable (have route + name)
- Forms submit to valid POST/PUT APIs
- Tables load from valid GET APIs
- Mutating APIs map to DB tables
- RBAC references defined roles
- Admin users API has matching admin UI page
- Validation report is clean

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `POST` | `/generate` | Run full pipeline |
| `GET` | `/evaluation/run` | Run 20 evaluation prompts |
| `GET` | `/evaluation/results` | Load persisted results |
| `GET` | `/health` | Health check |

### Generate Response Shape

```json
{
  "success": true,
  "config": { "app_name", "ui", "api", "database", "auth", "business_logic", "execution_plan", "validation_report", "runtime" },
  "metrics": { "latency_ms", "repair_count", "validation_valid", "runtime_executable" },
  "runtime_simulation": { "executable", "checks", "failures" }
}
```

## Evaluation

20 prompts (10 normal + 10 edge cases) in `backend/data/evaluation_prompts.json`.

Tracked metrics: `success_rate`, `successful_prompts`, `avg_latency_ms`, `repair_count`, `avg_repairs_per_prompt`, `retries_per_request`, `failure_types`, `repair_examples`.

## Cost vs Quality Tradeoff

| Approach | Cost | Quality | Determinism |
|----------|------|---------|-------------|
| Single LLM call | Low | Poor — hallucinated entities | Low |
| Multi-stage + mock | Free | Good for demo/testing | High |
| Multi-stage + GPT-4o | Medium | High on novel prompts | Medium |
| Multi-stage + repair | Medium+ | Highest — fixes layer by layer | High |

**Recommendation:** Use mock mode for development and evaluation baselines. Use OpenAI/Gemini for novel production prompts. Always run validation + repair — cheaper than re-prompting the full pipeline.

## Deploy

**Backend:** `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Frontend (optional):** `npm run build` in `frontend/`, set `VITE_API_URL` to backend URL.

## Sample Prompts (built into UI)

1. **Task + Admin Users** — tasks CRUD, dashboard metrics, `/admin/users`, PUT/DELETE user APIs
2. **CRM + Payments** — contacts, premium billing, subscriptions, admin analytics
3. **Auth Conflict** — "no login" but admins manage users → auth enabled with clarification flag

