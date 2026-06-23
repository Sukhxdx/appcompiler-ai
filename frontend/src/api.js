const API_BASE = import.meta.env.VITE_API_URL || "";

export async function generateConfig(prompt) {
  const res = await fetch(`${API_BASE}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Request failed: ${res.status}`);
  }
  return res.json();
}

export async function runEvaluation() {
  const res = await fetch(`${API_BASE}/evaluation/run`);
  if (!res.ok) throw new Error(`Evaluation failed: ${res.status}`);
  return res.json();
}

export async function getEvaluationResults() {
  const res = await fetch(`${API_BASE}/evaluation/results`);
  if (!res.ok) throw new Error(`Failed to load results: ${res.status}`);
  return res.json();
}
