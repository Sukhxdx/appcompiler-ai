import { useState } from "react";
import { generateConfig, runEvaluation, getEvaluationResults } from "./api";
import "./App.css";

const PIPELINE_STAGES = [
  { key: "intent_extraction", label: "1. Intent Extraction" },
  { key: "system_design", label: "2. System Design" },
  { key: "schema_generation", label: "3. Schema Generation" },
  { key: "validation", label: "4. Cross-layer Validation" },
  { key: "repair", label: "5. Repair Engine" },
  { key: "runtime_simulation", label: "6. Runtime Simulation" },
  { key: "evaluation", label: "7. Evaluation Metrics" },
];

function StatusBadge({ status }) {
  const cls = status ? `stage-badge stage-${status}` : "stage-badge stage-pending";
  return <span className={cls}>{status || "pending"}</span>;
}

function Panel({ title, children, className = "" }) {
  return (
    <section className={`panel ${className}`}>
      <h2 className="panel-title">{title}</h2>
      <div className="panel-body">{children}</div>
    </section>
  );
}

export default function App() {
  const [prompt, setPrompt] = useState(
    "Build a task management app where users can create and track tasks. Admins manage users."
  );
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const [evalLoading, setEvalLoading] = useState(false);
  const [evalSummary, setEvalSummary] = useState(null);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const data = await generateConfig(prompt);
      setResult(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRunEvaluation = async () => {
    setEvalLoading(true);
    try {
      const data = await runEvaluation();
      setEvalSummary(data.summary);
    } catch (err) {
      setError(err.message);
    } finally {
      setEvalLoading(false);
    }
  };

  const handleLoadEvalResults = async () => {
    try {
      const data = await getEvaluationResults();
      setEvalSummary(data.summary);
    } catch (err) {
      setError(err.message);
    }
  };

  const config = result?.config;
  const validationIssues = config?.validation_report?.issues || [];
  const assumptions = config?.assumptions || [];
  const metrics = result?.metrics || {};
  const stageStatus = result?.stage_status || {};

  return (
    <div className="app">
      <header className="header">
        <div className="header-inner">
          <div className="brand">
            <span className="brand-icon">⚙</span>
            <div>
              <h1>AppCompiler AI</h1>
              <p className="tagline">Natural language → validated executable app configuration</p>
            </div>
          </div>
          <div className="header-actions">
            <button className="btn btn-secondary" onClick={handleLoadEvalResults} disabled={evalLoading}>
              Load Eval Results
            </button>
            <button className="btn btn-secondary" onClick={handleRunEvaluation} disabled={evalLoading}>
              {evalLoading ? "Running…" : "Run Evaluation (20 prompts)"}
            </button>
          </div>
        </div>
      </header>

      <main className="main">
        <section className="input-section">
          <label htmlFor="prompt">App Requirements</label>
          <textarea
            id="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            rows={5}
            placeholder="Describe your app in natural language…"
          />
          <button className="btn btn-primary" onClick={handleGenerate} disabled={loading || !prompt.trim()}>
            {loading ? "Compiling…" : "Generate App Config"}
          </button>
        </section>

        {error && <div className="error-banner">{error}</div>}

        <div className="grid">
          <Panel title="Pipeline Stages" className="panel-stages">
            <ul className="stage-list">
              {PIPELINE_STAGES.map(({ key, label }) => (
                <li key={key} className="stage-item">
                  <span>{label}</span>
                  <StatusBadge status={stageStatus[key]} />
                </li>
              ))}
            </ul>
          </Panel>

          <Panel title="Metrics" className="panel-metrics">
            {result ? (
              <dl className="metrics-dl">
                <div><dt>Success</dt><dd className={result.success ? "ok" : "fail"}>{String(result.success)}</dd></div>
                <div><dt>Latency</dt><dd>{metrics.latency_ms ?? "—"} ms</dd></div>
                <div><dt>Repair Count</dt><dd>{metrics.repair_count ?? 0}</dd></div>
                <div><dt>Retries</dt><dd>{metrics.retries_per_request ?? 0}</dd></div>
                <div><dt>Validation</dt><dd>{String(metrics.validation_valid ?? "—")}</dd></div>
                <div><dt>Executable</dt><dd>{String(metrics.runtime_executable ?? "—")}</dd></div>
                {metrics.failure_types?.length > 0 && (
                  <div className="full-width">
                    <dt>Failure Types</dt>
                    <dd>{metrics.failure_types.join(", ")}</dd>
                  </div>
                )}
              </dl>
            ) : (
              <p className="muted">Run generation to see metrics.</p>
            )}
            {evalSummary && Object.keys(evalSummary).length > 0 && (
              <div className="eval-summary">
                <h3>Evaluation Summary</h3>
                <dl className="metrics-dl">
                  <div><dt>Success Rate</dt><dd>{(evalSummary.success_rate * 100).toFixed(1)}%</dd></div>
                  <div><dt>Avg Latency</dt><dd>{evalSummary.avg_latency_ms} ms</dd></div>
                  <div><dt>Total Repairs</dt><dd>{evalSummary.repair_count}</dd></div>
                  <div><dt>Retries/Request</dt><dd>{evalSummary.retries_per_request}</dd></div>
                </dl>
              </div>
            )}
          </Panel>
        </div>

        <div className="grid grid-2">
          <Panel title="Validation Errors" className="panel-errors">
            {validationIssues.length === 0 ? (
              <p className="muted">{config ? "No validation issues." : "No data yet."}</p>
            ) : (
              <ul className="issue-list">
                {validationIssues.map((issue, i) => (
                  <li key={i} className={`issue issue-${issue.severity}`}>
                    <span className="issue-code">{issue.code}</span>
                    <span className="issue-layer">[{issue.layer}]</span>
                    <p>{issue.message}</p>
                  </li>
                ))}
              </ul>
            )}
          </Panel>

          <Panel title="Assumptions" className="panel-assumptions">
            {assumptions.length === 0 ? (
              <p className="muted">{config ? "No assumptions documented." : "No data yet."}</p>
            ) : (
              <ul className="assumption-list">
                {assumptions.map((a, i) => (
                  <li key={i}>{a}</li>
                ))}
              </ul>
            )}
            {config?.validation_report?.clarification_needed && (
              <div className="clarification">
                <strong>Clarification needed</strong>
                <ul>
                  {(config.validation_report.clarification_notes || []).map((n, i) => (
                    <li key={i}>{n}</li>
                  ))}
                </ul>
              </div>
            )}
          </Panel>
        </div>

        <Panel title="Generated App Config (JSON)" className="panel-json">
          {config ? (
            <pre className="json-viewer">{JSON.stringify(config, null, 2)}</pre>
          ) : (
            <p className="muted">Generated configuration will appear here.</p>
          )}
        </Panel>
      </main>

      <footer className="footer">
        <span>AppCompiler AI Demo</span>
        <span className="muted">LLM_PROVIDER=mock (default) · FastAPI + React</span>
      </footer>
    </div>
  );
}
