"""Stage 7: Evaluation Metrics — batch run and persist results."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from llm.provider import get_provider
from pipeline.endpoint_utils import sync_auth_endpoints
from pipeline.intent_extractor import extract_intent
from pipeline.system_designer import design_system
from pipeline.schema_generator import generate_schema
from pipeline.validator import validate_config
from pipeline.repair_engine import repair_config
from pipeline.runtime_simulator import simulate_runtime

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
PROMPTS_FILE = DATA_DIR / "evaluation_prompts.json"
RESULTS_FILE = DATA_DIR / "evaluation_results.json"


class PipelineOrchestrator:
    """Runs the full 7-stage compilation pipeline."""

    STAGES = [
        "intent_extraction",
        "system_design",
        "schema_generation",
        "validation",
        "repair",
        "runtime_simulation",
        "evaluation",
    ]

    def __init__(self) -> None:
        self.provider = get_provider()

    async def run(self, prompt: str) -> dict[str, Any]:
        start = time.perf_counter()
        stage_status: dict[str, str] = {}
        retries = 0
        repair_count = 0
        failure_types: list[str] = []
        repair_notes: list[str] = []

        try:
            stage_status["intent_extraction"] = "running"
            intent = await extract_intent(prompt, self.provider)
            stage_status["intent_extraction"] = "completed"

            stage_status["system_design"] = "running"
            design = await design_system(intent, self.provider)
            stage_status["system_design"] = "completed"

            stage_status["schema_generation"] = "running"
            config = await generate_schema(design, self.provider)
            if intent.raw_prompt:
                config.assumptions.insert(0, f"[intent] raw_prompt={intent.raw_prompt[:120]}")
            if any("manage" in f.lower() and "user" in f.lower() for f in intent.core_features):
                config.assumptions.append("[intent] admin_manages_users=true")
            if any("assign" in f.lower() for f in intent.core_features) or "assign" in prompt.lower():
                config.assumptions.append("[intent] task_assignment=true")
            if intent.requires_payment:
                config.assumptions.append("[intent] has_payments=true")
            sync_auth_endpoints(config)
            stage_status["schema_generation"] = "completed"

            stage_status["validation"] = "running"
            report = validate_config(config)
            config.validation_report = report
            stage_status["validation"] = "completed" if report.valid else "failed"

            if not report.valid:
                stage_status["repair"] = "running"
                pre_repair_assumptions = len(config.assumptions)
                config, report = repair_config(config)
                repair_count = report.repair_count
                repair_notes = config.assumptions[pre_repair_assumptions:]
                retries = 1 if repair_count > 0 else 0
                stage_status["repair"] = "completed" if report.valid else "partial"
            else:
                stage_status["repair"] = "skipped"

            sync_auth_endpoints(config)

            stage_status["runtime_simulation"] = "running"
            runtime = simulate_runtime(config)
            stage_status["runtime_simulation"] = "completed" if runtime.executable else "failed"

            if not report.valid:
                failure_types.append("validation_error")
            if report.clarification_needed or intent.ambiguities:
                failure_types.append("clarification_needed")
                if intent.ambiguities and not report.clarification_needed:
                    report.clarification_needed = True
                    report.clarification_notes.extend(intent.ambiguities)
                    config.validation_report = report
            if not runtime.executable:
                failure_types.append("runtime_simulation_failed")

            latency_ms = int((time.perf_counter() - start) * 1000)
            stage_status["evaluation"] = "completed"

            config_dump = config.model_dump()
            metrics = {
                "latency_ms": latency_ms,
                "repair_count": repair_count,
                "retries_per_request": retries,
                "failure_types": failure_types,
                "validation_valid": report.valid,
                "runtime_executable": runtime.executable,
                "repair_notes": repair_notes,
            }

            return {
                "success": report.valid and runtime.executable,
                "config": config_dump,
                "intent": intent.model_dump(),
                "design": design.model_dump(),
                "stage_status": stage_status,
                "metrics": metrics,
                "runtime_simulation": runtime.model_dump(),
                "validation_report": report.model_dump(),
            }
        except Exception as exc:
            latency_ms = int((time.perf_counter() - start) * 1000)
            for stage in self.STAGES:
                if stage_status.get(stage) == "running":
                    stage_status[stage] = "failed"
            failure_types.append(type(exc).__name__)
            return {
                "success": False,
                "error": str(exc),
                "stage_status": stage_status,
                "metrics": {
                    "latency_ms": latency_ms,
                    "repair_count": repair_count,
                    "retries_per_request": retries,
                    "failure_types": failure_types,
                },
            }


def load_prompts() -> list[dict[str, Any]]:
    if not PROMPTS_FILE.exists():
        return []
    data = json.loads(PROMPTS_FILE.read_text())
    if isinstance(data, dict) and "prompts" in data:
        return data["prompts"]
    if isinstance(data, list):
        return data
    return []


def load_results() -> dict[str, Any]:
    if not RESULTS_FILE.exists():
        return {"runs": [], "summary": {}}
    return json.loads(RESULTS_FILE.read_text())


def save_results(data: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps(data, indent=2))


async def run_evaluation() -> dict[str, Any]:
    orchestrator = PipelineOrchestrator()
    prompts = load_prompts()
    run_id = datetime.now(timezone.utc).isoformat()
    results: list[dict[str, Any]] = []

    for item in prompts:
        prompt_id = item.get("id", "unknown")
        prompt_text = item.get("prompt", "")
        category = item.get("category", "normal")

        outcome = await orchestrator.run(prompt_text)
        repair_notes = outcome.get("metrics", {}).get("repair_notes", [])
        results.append(
            {
                "prompt_id": prompt_id,
                "category": category,
                "prompt": prompt_text,
                "success": outcome.get("success", False),
                "metrics": outcome.get("metrics", {}),
                "error": outcome.get("error"),
                "repaired": bool(repair_notes),
                "repair_notes": repair_notes[:5],
            }
        )

    successes = sum(1 for r in results if r["success"])
    total = len(results) or 1
    total_repairs = sum(r.get("metrics", {}).get("repair_count", 0) for r in results)
    total_retries = sum(r.get("metrics", {}).get("retries_per_request", 0) for r in results)
    avg_latency = sum(r.get("metrics", {}).get("latency_ms", 0) for r in results) / total

    failure_type_counts: dict[str, int] = {}
    for r in results:
        for ft in r.get("metrics", {}).get("failure_types", []):
            failure_type_counts[ft] = failure_type_counts.get(ft, 0) + 1

    repair_examples = [
        {"prompt_id": r["prompt_id"], "notes": r["repair_notes"]}
        for r in results
        if r.get("repaired") and r.get("repair_notes")
    ][:5]

    summary = {
        "run_id": run_id,
        "timestamp": run_id,
        "total_prompts": len(results),
        "successful_prompts": successes,
        "success_rate": round(successes / total, 4),
        "retries_per_request": round(total_retries / total, 2),
        "repair_count": total_repairs,
        "avg_repairs_per_prompt": round(total_repairs / total, 2),
        "avg_latency_ms": round(avg_latency, 2),
        "failure_types": failure_type_counts,
        "repair_examples": repair_examples,
    }

    stored = load_results()
    stored["runs"].append({"run_id": run_id, "summary": summary, "results": results})
    stored["summary"] = summary
    save_results(stored)

    return {"summary": summary, "results": results}
