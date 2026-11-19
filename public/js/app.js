/**
 * Floor-Plan Checker — main application module.
 */

import { FloorPlan3D, isWebGLAvailable } from "./viewer3d.js";

const API = "";

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
  });
});

document.querySelectorAll(".view-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".view-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");

    // Lazy-init 3D viewer when switching to 3D tab for the first time.
    if (btn.dataset.view === "3d" && !viewer3d) {
      // Wait one frame so the container is visible and has dimensions.
      requestAnimationFrame(() => initViewer3D());
    }
    // Refresh 3D if plan data is available and viewer is ready.
    if (btn.dataset.view === "3d" && viewer3d && currentPlan) {
      requestAnimationFrame(() => viewer3d.loadPlan(currentPlan, currentViolations));
    }
  });
});

// ---------------------------------------------------------------------------
// Editor
// ---------------------------------------------------------------------------
const editor = document.getElementById("plan-editor");
const errorBox = document.getElementById("schema-errors");
const scoreBar = document.getElementById("score-bar");
const violationsList = document.getElementById("violations-list");
const view2d = document.getElementById("view-2d");
const seedPicker = document.getElementById("seed-picker");

let debounceTimer = null;

// 3D viewer state.
let viewer3d = null;
let currentPlan = null;
let currentViolations = [];

function initViewer3D() {
  const container = document.getElementById("view-3d");
  if (!isWebGLAvailable()) {
    container.innerHTML = '<p class="notice">WebGL is not available in this browser. The 2D view still works.</p>';
    return;
  }
  container.innerHTML = "";
  // Add toolbar.
  const toolbar = document.createElement("div");
  toolbar.className = "view-3d-toolbar";
  toolbar.innerHTML = `
    <button id="btn-3d-top" class="view-3d-btn" title="Top-down view">⬇ Top</button>
    <button id="btn-3d-perspective" class="view-3d-btn" title="Perspective view">◆ 3D</button>
  `;
  container.appendChild(toolbar);
  // Canvas container.
  const canvasWrap = document.createElement("div");
  canvasWrap.className = "view-3d-canvas";
  container.appendChild(canvasWrap);

  viewer3d = new FloorPlan3D(canvasWrap);
  viewer3d.init();

  document.getElementById("btn-3d-top").addEventListener("click", () => viewer3d.resetTopDown());
  document.getElementById("btn-3d-perspective").addEventListener("click", () => viewer3d.resetPerspective());

  // Load current plan if available.
  if (currentPlan) {
    viewer3d.loadPlan(currentPlan, currentViolations);
  }
}

editor.addEventListener("input", () => {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(() => scorePlan(), 300);
});

document.getElementById("btn-format").addEventListener("click", () => {
  try {
    const plan = JSON.parse(editor.value);
    editor.value = JSON.stringify(plan, null, 2);
  } catch {
    // ignore
  }
});

// ---------------------------------------------------------------------------
// Seeds
// ---------------------------------------------------------------------------
async function loadSeeds() {
  try {
    const resp = await fetch(`${API}/api/seeds`);
    const seeds = await resp.json();
    seeds.forEach((s) => {
      const opt = document.createElement("option");
      opt.value = s.id;
      opt.textContent = `${s.title} (${s.id})`;
      seedPicker.appendChild(opt);
    });
    return seeds;
  } catch (e) {
    console.error("Failed to load seeds", e);
    return [];
  }
}

let seedCache = null;

seedPicker.addEventListener("change", async () => {
  if (!seedPicker.value) return;
  if (!seedCache) {
    const resp = await fetch(`${API}/api/seeds`);
    seedCache = await resp.json();
  }
  const resp = await fetch(`${API}/api/seeds/${seedPicker.value}`);
  const seed = await resp.json();
  editor.value = JSON.stringify(seed, null, 2);
  scorePlan();
});

// ---------------------------------------------------------------------------
// Score and render
// ---------------------------------------------------------------------------
async function scorePlan() {
  const text = editor.value.trim();
  if (!text) {
    clearResults();
    return;
  }

  let plan;
  try {
    plan = JSON.parse(text);
  } catch (e) {
    showSchemaError(`Invalid JSON: ${e.message}`);
    return;
  }

  try {
    const [scoreResp, renderResp] = await Promise.all([
      fetch(`${API}/api/score`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(plan) }),
      fetch(`${API}/api/render`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(plan) }),
    ]);

    if (scoreResp.status === 422) {
      const err = await scoreResp.json();
      showSchemaErrors(err);
      return;
    }

    const scoreData = await scoreResp.json();
    const renderData = await renderResp.json();

    hideSchemaError();
    renderResults(scoreData, renderData.svg);
  } catch (e) {
    showSchemaError(`Request failed: ${e.message}`);
  }
}

function showSchemaError(msg) {
  errorBox.textContent = msg;
  errorBox.classList.add("visible");
  clearResults();
}

function showSchemaErrors(err) {
  const details = err.details || [];
  errorBox.innerHTML = details.map((d) => `<div><strong>${d.path}</strong>: ${d.message}</div>`).join("");
  errorBox.classList.add("visible");
  clearResults();
}

function hideSchemaError() {
  errorBox.classList.remove("visible");
}

function clearResults() {
  scoreBar.className = "";
  scoreBar.innerHTML = "";
  violationsList.innerHTML = "";
  view2d.innerHTML = "<p class='notice'>Enter a plan to see the 2D view.</p>";
  currentPlan = null;
  currentViolations = [];
  if (viewer3d) {
    viewer3d.loadPlan({ rooms: [], doors: [], windows: [] }, []);
  }
}

function renderResults(data, svg) {
  // Score bar.
  const passed = data.passed;
  scoreBar.className = passed ? "passed" : "failed";
  scoreBar.innerHTML = `
    <span class="badge ${passed ? "badge-pass" : "badge-fail"}">${passed ? "PASS" : "FAIL"}</span>
    <span>Score: ${data.score}</span>
  `;

  // Violations.
  violationsList.innerHTML = "";
  data.violations.forEach((v) => {
    const li = document.createElement("li");
    li.className = v.severity;
    li.innerHTML = `
      <div><span class="rule-id">${v.rule}</span> ${v.severity.toUpperCase()}</div>
      <div>${v.message}</div>
      <div class="fix">💡 ${v.suggested_fix}</div>
    `;
    li.addEventListener("click", () => highlightRegion(v));
    violationsList.appendChild(li);
  });

  // SVG.
  view2d.innerHTML = svg;

  // Store current plan + violations for 3D view.
  try {
    currentPlan = JSON.parse(editor.value);
    currentViolations = data.violations;
  } catch {
    currentPlan = null;
    currentViolations = [];
  }

  // Update 3D view if initialized.
  if (viewer3d && currentPlan) {
    viewer3d.loadPlan(currentPlan, currentViolations);
  }
}

function highlightRegion(v) {
  // Simple highlight: scroll SVG into view.
  view2d.scrollIntoView({ behavior: "smooth" });
}

// ---------------------------------------------------------------------------
// Share link
// ---------------------------------------------------------------------------
document.getElementById("btn-share").addEventListener("click", () => {
  const text = editor.value.trim();
  if (!text) return;
  try {
    const plan = JSON.parse(text);
    const encoded = encodePlan(plan);
    const url = `${window.location.origin}${window.location.pathname}#plan=${encoded}`;
    navigator.clipboard.writeText(url);
    alert("Share link copied to clipboard!");
  } catch (e) {
    alert(`Cannot share: ${e.message}`);
  }
});

// ---------------------------------------------------------------------------
// URL fragment decoding
// ---------------------------------------------------------------------------
function encodePlan(plan) {
  const json = JSON.stringify(plan);
  // Simple base64 for now (no compression — browser decompression needs DecompressionStream).
  return btoa(unescape(encodeURIComponent(json)));
}

function decodePlanFragment(fragment) {
  try {
    return JSON.parse(decodeURIComponent(escape(atob(fragment))));
  } catch {
    return null;
  }
}

function checkHash() {
  const hash = window.location.hash;
  if (hash.startsWith("#plan=")) {
    const encoded = hash.slice(6);
    const plan = decodePlanFragment(encoded);
    if (plan) {
      editor.value = JSON.stringify(plan, null, 2);
      scorePlan();
    } else {
      showSchemaError("Could not decode plan from URL. It may be corrupt or use a format this browser cannot decompress.");
    }
  }
}

// ---------------------------------------------------------------------------
// Reviewer
// ---------------------------------------------------------------------------
const LABELS_KEY = "floors_labels_v1";

function loadLabels() {
  try {
    return JSON.parse(localStorage.getItem(LABELS_KEY) || "[]");
  } catch {
    return [];
  }
}

function saveLabels(labels) {
  try {
    localStorage.setItem(LABELS_KEY, JSON.stringify(labels));
  } catch {
    // ignore
  }
}

let currentReviewPlan = null;
let currentAutoResult = null;
let selectedLabel = null;
let selectedReasons = new Set();

document.getElementById("btn-pass").addEventListener("click", () => {
  selectedLabel = "pass";
  updateLabelButtons();
});
document.getElementById("btn-fail").addEventListener("click", () => {
  selectedLabel = "fail";
  updateLabelButtons();
});
document.getElementById("btn-skip").addEventListener("click", () => {
  selectedLabel = "skip";
  updateLabelButtons();
});

function updateLabelButtons() {
  document.getElementById("btn-pass").style.opacity = selectedLabel === "pass" ? 1 : 0.5;
  document.getElementById("btn-fail").style.opacity = selectedLabel === "fail" ? 1 : 0.5;
  document.getElementById("btn-skip").style.opacity = selectedLabel === "skip" ? 1 : 0.5;
}

// Keyboard shortcuts.
document.addEventListener("keydown", (e) => {
  if (document.querySelector("#tab-reviewer.active")) {
    if (e.key === "p" || e.key === "P") { selectedLabel = "pass"; updateLabelButtons(); }
    if (e.key === "f" || e.key === "F") { selectedLabel = "fail"; updateLabelButtons(); }
    if (e.key === "s" || e.key === "S") { selectedLabel = "skip"; updateLabelButtons(); }
  }
});

document.getElementById("btn-save-label").addEventListener("click", () => {
  if (!currentReviewPlan || !selectedLabel) return;

  const label = {
    plan_id: currentReviewPlan.id,
    plan: currentReviewPlan,
    auto: currentAutoResult ? {
      passed: currentAutoResult.passed,
      score: currentAutoResult.score,
      rules: currentAutoResult.violations.map((v) => v.rule),
    } : null,
    human: {
      label: selectedLabel,
      reasons: [...selectedReasons],
      note: document.getElementById("review-note").value,
    },
    agree: currentAutoResult ? (currentAutoResult.passed === (selectedLabel === "pass")) : null,
    labelled_at: new Date().toISOString(),
  };

  const labels = loadLabels();
  labels.push(label);
  saveLabels(labels);
  updateReviewerStats();

  // Show auto verdict.
  if (currentAutoResult) {
    const verdictEl = document.getElementById("auto-verdict");
    verdictEl.classList.remove("hidden");
    verdictEl.innerHTML = `<strong>Auto verdict:</strong> ${currentAutoResult.passed ? "PASS" : "FAIL"} (score ${currentAutoResult.score})`;
  }
});

function updateReviewerStats() {
  const labels = loadLabels();
  document.getElementById("label-count").textContent = `Labels: ${labels.length}`;

  const withAgree = labels.filter((l) => l.agree !== null);
  if (withAgree.length > 0) {
    const agreed = withAgree.filter((l) => l.agree).length;
    const rate = ((agreed / withAgree.length) * 100).toFixed(0);
    document.getElementById("agreement-rate").textContent = `Agreement: ${rate}%`;
  }
}

// Load seeds into reviewer queue.
document.getElementById("btn-load-seeds").addEventListener("click", async () => {
  const resp = await fetch(`${API}/api/seeds`);
  const seeds = await resp.json();
  if (seeds.length > 0) {
    const detail = await fetch(`${API}/api/seeds/${seeds[0].id}`);
    const plan = await detail.json();
    loadPlanIntoReviewer(plan);
  }
});

async function loadPlanIntoReviewer(plan) {
  currentReviewPlan = plan;
  selectedLabel = null;
  selectedReasons.clear();
  updateLabelButtons();
  document.getElementById("review-note").value = "";
  document.getElementById("auto-verdict").classList.add("hidden");
  document.getElementById("reason-chips").innerHTML = "";

  editor.value = JSON.stringify(plan, null, 2);
  await scorePlan();

  // Fetch auto result.
  const resp = await fetch(`${API}/api/score`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(plan),
  });
  if (resp.ok) {
    currentAutoResult = await resp.json();
    // Build reason chips.
    const rules = [...new Set(currentAutoResult.violations.map((v) => v.rule))];
    const chipsEl = document.getElementById("reason-chips");
    rules.forEach((r) => {
      const btn = document.createElement("button");
      btn.textContent = r;
      btn.addEventListener("click", () => {
        if (selectedReasons.has(r)) {
          selectedReasons.delete(r);
          btn.classList.remove("selected");
        } else {
          selectedReasons.add(r);
          btn.classList.add("selected");
        }
      });
      chipsEl.appendChild(btn);
    });
  }
}

document.getElementById("btn-export").addEventListener("click", () => {
  const labels = loadLabels();
  if (labels.length === 0) {
    alert("No labels to export.");
    return;
  }
  const jsonl = labels.map((l) => JSON.stringify(l)).join("\n");
  const blob = new Blob([jsonl], { type: "application/jsonl" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "labels.jsonl";
  a.click();
  URL.revokeObjectURL(url);
});

document.getElementById("btn-clear-labels").addEventListener("click", () => {
  if (confirm("Clear all labels?")) {
    saveLabels([]);
    updateReviewerStats();
  }
});

// ---------------------------------------------------------------------------
// Batch eval
// ---------------------------------------------------------------------------
document.getElementById("btn-load-all-seeds").addEventListener("click", async () => {
  const resp = await fetch(`${API}/api/seeds`);
  const seeds = await resp.json();
  const plans = [];
  for (const s of seeds) {
    const detail = await fetch(`${API}/api/seeds/${s.id}`);
    plans.push(await detail.json());
  }
  document.getElementById("batch-input").value = JSON.stringify(plans, null, 2);
});

document.getElementById("btn-run-eval").addEventListener("click", async () => {
  const text = document.getElementById("batch-input").value.trim();
  if (!text) return;
  let plans;
  try {
    plans = JSON.parse(text);
  } catch (e) {
    alert(`Invalid JSON: ${e.message}`);
    return;
  }
  if (!Array.isArray(plans)) {
    alert("Input must be a JSON array of plans.");
    return;
  }

  const resp = await fetch(`${API}/api/eval`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ plans }),
  });

  const resultsEl = document.getElementById("batch-results");
  if (resp.status === 413) {
    const err = await resp.json();
    resultsEl.innerHTML = `<p class="notice">${err.error}</p>`;
    return;
  }
  if (!resp.ok) {
    resultsEl.innerHTML = `<p class="notice">Request failed (${resp.status}).</p>`;
    return;
  }

  const report = await resp.json();
  resultsEl.innerHTML = `
    <div class="batch-summary">
      <div class="stat"><div class="value">${report.n}</div><div class="label">Plans</div></div>
      <div class="stat"><div class="value">${(report.pass_rate * 100).toFixed(0)}%</div><div class="label">Pass rate</div></div>
      <div class="stat"><div class="value">${report.mean_score.toFixed(2)}</div><div class="label">Mean score</div></div>
    </div>
    <h3>Per-rule failures</h3>
    <ul>${Object.entries(report.per_rule).map(([k, v]) => `<li>${k}: ${v}</li>`).join("")}</ul>
    <h3>Results</h3>
    <table border="1" cellpadding="4" style="width:100%;font-size:0.85rem;">
      <tr><th>Plan</th><th>Passed</th><th>Score</th><th>Violations</th></tr>
      ${report.results.map((r) => `<tr><td>${r.plan_id}</td><td>${r.passed ? "✓" : "✗"}</td><td>${r.score}</td><td>${r.violations.length}</td></tr>`).join("")}
    </table>
  `;
});

// ---------------------------------------------------------------------------
// About
// ---------------------------------------------------------------------------
async function loadAbout() {
  const resp = await fetch(`${API}/api/schema`);
  const data = await resp.json();
  const cat = document.getElementById("rule-catalogue");
  cat.innerHTML = `
    <table>
      <tr><th>ID</th><th>Severity</th><th>Description</th></tr>
      ${data.rules.map((r) => `<tr><td>${r.id}</td><td>${r.severity}</td><td>${r.description}</td></tr>`).join("")}
    </table>
  `;

  const mcpUrl = `${window.location.origin}/mcp`;
  document.getElementById("mcp-config").textContent = JSON.stringify(
    {
      mcpServers: {
        "floor-plans": {
          url: mcpUrl,
        },
      },
    },
    null,
    2,
  );
}

// ---------------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------------
loadSeeds();
loadAbout();
updateReviewerStats();
checkHash();
