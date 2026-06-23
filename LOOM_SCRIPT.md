
> "Hi, I'm walking through AppCompiler AI — an internship demo that compiles natural language app requirements into a validated, executable application configuration. Think of it as a compiler for app specs, not a single ChatGPT prompt."


> "If you ask an LLM once to 'build a task app,' you get inconsistent JSON, hallucinated database fields, and forms that don't connect to APIs. AppCompiler AI fixes this with a 7-stage pipeline."

*Click Generate with the Task + Admin Users sample prompt*

> "Stage 1 extracts intent — entities, roles, ambiguities.
> Stage 2 produces system design — pages, endpoints, tables.
> Stage 3 generates strict AppConfig JSON validated by Pydantic.
> Stage 4 runs cross-layer validation — forms must map to POST APIs, tables to GET APIs, API fields must exist in the database.
> Stage 5 is the repair engine — it fixes only the broken layer, never regenerates everything.
> Stage 6 simulates runtime — pages renderable, auth enforceable, executable true or false.
> Stage 7 tracks evaluation metrics."

*Point at Pipeline Stages panel as each completes*



> "The config includes everything a codegen tool needs: UI pages with components, REST endpoints, database tables with relations, auth roles with permissions, business rules, and an execution plan."

*Scroll JSON viewer — highlight:*
- `/admin/users` page with `users_table`
- Dashboard metrics: `total_tasks`, `completed_tasks` — not email/password
- `GET /api/tasks`, `POST /api/tasks`, `GET /api/users`
- `validation_report.valid: true`
- `runtime.executable: true`

## Validation & Repair

> "Validation catches cross-layer bugs. The repair engine adds missing admin pages, fixes dashboard fields, creates GET endpoints for tables — each with a documented repair note in assumptions."

*Click Auth Conflict sample prompt → Generate*

> "Edge case: no login but admins manage users. The system enables auth anyway, flags clarification_needed, and documents the conflict."

## Evaluation & Tradeoffs 

> "Click Run Evaluation — 20 prompts, 10 normal, 10 edge cases. We track success rate, latency, repair count, and failure types."

*Click Run Evaluation*

> "Mock mode is free and deterministic for demos. Real LLMs cost more but handle novel prompts. The repair engine is the sweet spot — fix one layer instead of re-running three LLM calls."

> "AppCompiler AI shows how to build production-style AI systems: structured pipelines, strict schemas, validation, targeted repair, and runtime simulation before generating code. Thanks for watching."
