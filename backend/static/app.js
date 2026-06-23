const PIPELINE_STAGES = [
  { key: "intent_extraction", label: "1. Intent Extraction" },
  { key: "system_design", label: "2. System Design" },
  { key: "schema_generation", label: "3. Schema Generation" },
  { key: "validation", label: "4. Cross-layer Validation" },
  { key: "repair", label: "5. Repair Engine" },
  { key: "runtime_simulation", label: "6. Runtime Simulation" },
  { key: "evaluation", label: "7. Evaluation Metrics" },
];

const API_BASE = "";

const $ = (id) => document.getElementById(id);

function badge(status) {
  const s = status || "pending";
  return `<span class="stage-badge stage-${s}">${status || "pending"}</span>`;
}

function renderStages(stageStatus) {
  return PIPELINE_STAGES.map(
    ({ key, label }) =>
      `<li class="stage-item"><span>${label}</span>${badge(stageStatus[key])}</li>`
  ).join("");
}

function renderMetrics(result, evalSummary) {
  if (!result && !evalSummary) {
    return '<p class="muted">Run generation to see metrics.</p>';
  }

  let html = "";
  if (result) {
    const m = result.metrics || {};
    const rt = result.runtime_simulation || result.config?.runtime || {};
    const ok = result.success ? "ok" : "fail";
    html += `<dl class="metrics-dl">
      <div><dt>Success</dt><dd class="${ok}">${result.success}</dd></div>
      <div><dt>Latency</dt><dd>${m.latency_ms ?? "—"} ms</dd></div>
      <div><dt>Repair Count</dt><dd>${m.repair_count ?? 0}</dd></div>
      <div><dt>Retries</dt><dd>${m.retries_per_request ?? 0}</dd></div>
      <div><dt>Validation</dt><dd class="${m.validation_valid ? "ok" : "fail"}">${m.validation_valid ?? "—"}</dd></div>
      <div><dt>Executable</dt><dd class="${m.runtime_executable ? "ok" : "fail"}">${m.runtime_executable ?? rt.executable ?? "—"}</dd></div>
      ${(m.failure_types || []).length ? `<div class="full-width"><dt>Failure Types</dt><dd>${m.failure_types.join(", ")}</dd></div>` : ""}
      ${(m.repair_notes || []).length ? `<div class="full-width"><dt>Repair Notes</dt><dd>${m.repair_notes.join("; ")}</dd></div>` : ""}
    </dl>`;
    if (rt.checks?.length) {
      html += `<div class="runtime-checks"><h3>Runtime Checks</h3><ul>${rt.checks
        .map((c) => `<li class="${c.passed ? "ok-text" : "fail-text"}">${c.check} — ${c.passed ? "pass" : "fail"}</li>`)
        .join("")}</ul></div>`;
    }
  }

  if (evalSummary && Object.keys(evalSummary).length) {
    html += renderEvalSummary(evalSummary);
  }

  return html;
}

function renderEvalSummary(evalSummary) {
  const ft = evalSummary.failure_types || {};
  const ftStr = Object.keys(ft).length
    ? Object.entries(ft).map(([k, v]) => `${k}: ${v}`).join(", ")
    : "none";

  let html = `<div class="eval-summary"><h3>Evaluation Summary</h3><dl class="metrics-dl">
    <div><dt>Total Prompts</dt><dd>${evalSummary.total_prompts ?? "—"}</dd></div>
    <div><dt>Successful</dt><dd>${evalSummary.successful_prompts ?? "—"}</dd></div>
    <div><dt>Success Rate</dt><dd>${((evalSummary.success_rate || 0) * 100).toFixed(1)}%</dd></div>
    <div><dt>Avg Latency</dt><dd>${evalSummary.avg_latency_ms} ms</dd></div>
    <div><dt>Total Repairs</dt><dd>${evalSummary.repair_count}</dd></div>
    <div><dt>Avg Repairs/Prompt</dt><dd>${evalSummary.avg_repairs_per_prompt ?? "—"}</dd></div>
    <div class="full-width"><dt>Failure Types</dt><dd>${ftStr}</dd></div>
  </dl>`;

  if (evalSummary.repair_examples?.length) {
    html += `<h4>Repair Examples</h4><ul class="assumption-list">${evalSummary.repair_examples
      .map((ex) => `<li><strong>${ex.prompt_id}</strong>: ${(ex.notes || []).join("; ")}</li>`)
      .join("")}</ul>`;
  }
  html += `</div>`;
  return html;
}

function renderIssues(issues) {
  const errors = (issues || []).filter((i) => i.severity === "error");
  if (!errors.length) return '<p class="muted">No validation errors.</p>';
  return `<ul class="issue-list">${errors
    .map(
      (i) => `<li class="issue issue-${i.severity}">
        <span class="issue-code">${i.code}</span>
        <span class="issue-layer">[${i.layer}]</span>
        <p>${i.message}</p>
      </li>`
    )
    .join("")}</ul>`;
}

function renderAssumptions(config) {
  if (!config) return '<p class="muted">No data yet.</p>';
  const assumptions = (config.assumptions || []).filter((a) => a.startsWith("[repair"));
  const all = config.assumptions || [];
  let html = all.length
    ? `<ul class="assumption-list">${all.map((a) => `<li>${a}</li>`).join("")}</ul>`
    : '<p class="muted">No assumptions documented.</p>';

  if (assumptions.length) {
    html += `<p class="muted repair-count">${assumptions.length} repair note(s) documented.</p>`;
  }

  const vr = config.validation_report || {};
  if (vr.clarification_needed) {
    html += `<div class="clarification"><strong>Clarification needed</strong><ul>${(vr.clarification_notes || [])
      .map((n) => `<li>${n}</li>`)
      .join("")}</ul></div>`;
  }
  return html;
}

let evalSummary = null;

function showError(msg) {
  const el = $("error-banner");
  if (msg) {
    el.textContent = msg;
    el.classList.remove("hidden");
  } else {
    el.classList.add("hidden");
  }
}

async function handleGenerate() {
  const prompt = $("prompt").value.trim();
  if (!prompt) return;

  $("btn-generate").disabled = true;
  $("btn-generate").textContent = "Compiling…";
  showError(null);

  try {
    const res = await fetch(`${API_BASE}/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      const detail = err.detail || `Request failed: ${res.status}`;
      if (res.status === 405) {
        throw new Error(
          "Method not allowed. Open http://localhost:8000 (not /generate) and click Generate App Config."
        );
      }
      throw new Error(detail);
    }
    const result = await res.json();
    $("stage-list").innerHTML = renderStages(result.stage_status || {});
    $("metrics-panel").innerHTML = renderMetrics(result, null);

    const config = result.config;
    const issues = config?.validation_report?.issues || [];
    $("issues-panel").innerHTML = config ? renderIssues(issues) : '<p class="muted">No data yet.</p>';
    $("assumptions-panel").innerHTML = renderAssumptions(config);
    $("json-viewer").textContent = config
      ? JSON.stringify(config, null, 2)
      : "Generated configuration will appear here.";
  } catch (err) {
    showError(err.message);
  } finally {
    $("btn-generate").disabled = false;
    $("btn-generate").textContent = "Generate App Config";
  }
}

async function handleRunEvaluation() {
  $("btn-eval").disabled = true;
  $("btn-eval").textContent = "Running…";
  showError(null);
  try {
    const res = await fetch(`${API_BASE}/evaluation/run`);
    if (!res.ok) throw new Error(`Evaluation failed: ${res.status}`);
    const data = await res.json();
    evalSummary = data.summary;
    $("metrics-panel").innerHTML = renderMetrics(null, evalSummary);
    $("eval-panel").innerHTML = renderEvalSummary(evalSummary);
  } catch (err) {
    showError(err.message);
  } finally {
    $("btn-eval").disabled = false;
    $("btn-eval").textContent = "Run Evaluation (20 prompts)";
  }
}

async function handleLoadEvalResults() {
  showError(null);
  try {
    const res = await fetch(`${API_BASE}/evaluation/results`);
    if (!res.ok) throw new Error(`Failed to load: ${res.status}`);
    const data = await res.json();
    evalSummary = data.summary;
    $("metrics-panel").innerHTML = renderMetrics(null, evalSummary);
    $("eval-panel").innerHTML = renderEvalSummary(evalSummary);
  } catch (err) {
    showError(err.message);
  }
}

document.querySelectorAll(".btn-sample").forEach((btn) => {
  btn.addEventListener("click", () => {
    $("prompt").value = btn.dataset.prompt;
  });
});

$("btn-generate").addEventListener("click", handleGenerate);
$("btn-eval").addEventListener("click", handleRunEvaluation);
$("btn-load-eval").addEventListener("click", handleLoadEvalResults);
$("stage-list").innerHTML = renderStages({});
