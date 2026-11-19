/**
 * Floors — main application module.
 */

import { FloorPlan3D, isWebGLAvailable } from "./viewer3d.js";

const API = "";

// ---------------------------------------------------------------------------
// Tab switching
// ---------------------------------------------------------------------------
function navigateTo(tabId) {
  document.querySelectorAll(".site-nav .nav-link").forEach((l) => l.classList.remove("active"));
  document.querySelectorAll(".tab-content").forEach((c) => c.classList.remove("active"));

  const tabEl = document.getElementById(`tab-${tabId}`);
  if (tabEl) tabEl.classList.add("active");

  const navLink = document.querySelector(`.nav-link[data-nav="${tabId}"]`);
  if (navLink) navLink.classList.add("active");

  window.scrollTo({ top: 0, behavior: "instant" });

  if (tabId === "editor" && !editor.value.trim() && seedPicker.value === "") {
    loadFirstSeed();
  }

  if (tabId === "editor") {
    const active3dBtn = document.querySelector(".view-tab[data-view='3d'].active");
    if (active3dBtn && !viewer3d) {
      requestAnimationFrame(() => initViewer3D());
    }
  }
}

document.querySelectorAll("[data-nav]").forEach((el) => {
  el.addEventListener("click", (e) => {
    e.preventDefault();
    navigateTo(el.dataset.nav);
  });
});

// View tabs (2D / 3D) inside the editor.
document.querySelectorAll(".view-tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".view-tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".view-content").forEach((c) => c.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById(`view-${btn.dataset.view}`).classList.add("active");

    if (btn.dataset.view === "3d" && !viewer3d) {
      requestAnimationFrame(() => initViewer3D());
    }
    if (btn.dataset.view === "3d" && viewer3d && currentPlan) {
      requestAnimationFrame(() => viewer3d.loadPlan(currentPlan, currentViolations));
    }
  });
});

async function loadFirstSeed() {
  if (!seedCache) {
    const resp = await fetch(`${API}/api/seeds`);
    seedCache = await resp.json();
  }
  if (seedCache.length > 0) {
    seedPicker.value = seedCache[0].id;
    seedPicker.dispatchEvent(new Event("change"));
  }
}

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
  const toolbar = document.createElement("div");
  toolbar.className = "view-3d-toolbar";
  toolbar.innerHTML = `
    <button id="btn-3d-top" class="view-3d-btn" title="Top-down view">TOP</button>
    <button id="btn-3d-perspective" class="view-3d-btn" title="Perspective view">3D</button>
  `;
  container.appendChild(toolbar);
  const canvasWrap = document.createElement("div");
  canvasWrap.className = "view-3d-canvas";
  container.appendChild(canvasWrap);

  viewer3d = new FloorPlan3D(canvasWrap);
  viewer3d.init();

  document.getElementById("btn-3d-top").addEventListener("click", () => viewer3d.resetTopDown());
  document.getElementById("btn-3d-perspective").addEventListener("click", () => viewer3d.resetPerspective());

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

  // Violations — grouped into errors and warnings sections.
  violationsList.innerHTML = "";
  const errors = data.errors || [];
  const warnings = data.warnings || [];

  if (errors.length === 0 && warnings.length === 0) {
    violationsList.innerHTML = "<li class='notice'>No violations. Plan is valid.</li>";
  } else {
    // Build a lookup from violations for suggested_fix + region.
    const violationMap = {};
    (data.violations || []).forEach((v) => {
      const key = `${v.rule}: ${v.message}`;
      violationMap[key] = v;
    });

    if (errors.length > 0) {
      const heading = document.createElement("li");
      heading.className = "violation-group-heading";
      heading.innerHTML = `<span>ERRORS (${errors.length})</span>`;
      violationsList.appendChild(heading);

      errors.forEach((msg) => {
        const li = document.createElement("li");
        li.className = "violation error";
        const v = violationMap[msg] || {};
        const ruleId = msg.split(":")[0] || "";
        const messageText = msg.slice(ruleId.length + 2);
        const roomTags = (v.room_ids || [])
          .map((rid) => `<span class="room-tag">${rid}</span>`)
          .join("");
        li.innerHTML = `
          <div class="violation-header">
            <span class="rule-id">${ruleId}</span>
            ${roomTags}
          </div>
          <p class="violation-message">${messageText}</p>
          ${v.suggested_fix ? `<p class="violation-fix">${v.suggested_fix}</p>` : ""}
        `;
        li.addEventListener("click", () => highlightRegion(v));
        violationsList.appendChild(li);
      });
    }

    if (warnings.length > 0) {
      const heading = document.createElement("li");
      heading.className = "violation-group-heading";
      heading.innerHTML = `<span>WARNINGS (${warnings.length})</span>`;
      violationsList.appendChild(heading);

      warnings.forEach((msg) => {
        const li = document.createElement("li");
        li.className = "violation warning";
        const v = violationMap[msg] || {};
        const ruleId = msg.split(":")[0] || "";
        const messageText = msg.slice(ruleId.length + 2);
        const roomTags = (v.room_ids || [])
          .map((rid) => `<span class="room-tag">${rid}</span>`)
          .join("");
        li.innerHTML = `
          <div class="violation-header">
            <span class="rule-id">${ruleId}</span>
            ${roomTags}
          </div>
          <p class="violation-message">${messageText}</p>
          ${v.suggested_fix ? `<p class="violation-fix">${v.suggested_fix}</p>` : ""}
        `;
        li.addEventListener("click", () => highlightRegion(v));
        violationsList.appendChild(li);
      });
    }
  }

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

  if (viewer3d && currentPlan) {
    viewer3d.loadPlan(currentPlan, currentViolations);
  }
}

function highlightRegion(v) {
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
      showSchemaError("Could not decode plan from URL. It may be corrupt.");
    }
  }
}

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
  renderBatchResults(resultsEl, report);
});

function renderBatchResults(el, report) {
  // Rule descriptions for the per-rule breakdown.
  const ruleDescriptions = {
    R01: "No room overlap",
    R02: "Has entrance",
    R03: "All rooms reachable",
    R04: "Habitable rooms have windows",
    R05: "Doors on real walls",
    R06: "Windows on exterior walls",
    R07: "Minimum room areas",
    R08: "Plausible proportions",
    R09: "Door widths",
    R10: "Bathroom privacy",
  };

  // Summary stats.
  let html = `
    <div class="batch-summary">
      <div class="stat"><div class="stat-num">${report.n}</div><div class="stat-label">PLANS</div></div>
      <div class="stat"><div class="stat-num">${(report.pass_rate * 100).toFixed(0)}%</div><div class="stat-label">PASS RATE</div></div>
      <div class="stat"><div class="stat-num">${report.mean_score.toFixed(2)}</div><div class="stat-label">MEAN SCORE</div></div>
    </div>
  `;

  // Per-rule breakdown with descriptions.
  const ruleEntries = Object.entries(report.per_rule).sort((a, b) => a[0].localeCompare(b[0]));
  if (ruleEntries.length > 0) {
    html += `<h3>PER-RULE FAILURES</h3><ul class="batch-rule-list">`;
    for (const [ruleId, count] of ruleEntries) {
      const desc = ruleDescriptions[ruleId] || ruleId;
      html += `<li><span class="rule-id">${ruleId}</span> <span class="rule-desc">${desc}</span> <span class="rule-count">${count}</span></li>`;
    }
    html += `</ul>`;
  }

  // Per-plan table with expandable details.
  html += `<h3>PER-PLAN RESULTS</h3>`;
  html += `<table><thead><tr><th>PLAN</th><th>STATUS</th><th>SCORE</th><th>DETAILS</th></tr></thead><tbody>`;
  report.results.forEach((r, idx) => {
    const status = r.passed ? "PASS" : "FAIL";
    const statusClass = r.passed ? "batch-pass" : "batch-fail";
    const errorCount = (r.errors || []).length;
    const warnCount = (r.warnings || []).length;
    const detailText = r.passed
      ? (warnCount > 0 ? `${warnCount} warning${warnCount > 1 ? "s" : ""}` : "Clean")
      : `${errorCount} error${errorCount > 1 ? "s" : ""}${warnCount > 0 ? `, ${warnCount} warning${warnCount > 1 ? "s" : ""}` : ""}`;

    html += `<tr>
      <td class="batch-plan-id">${r.plan_id}</td>
      <td><span class="batch-status ${statusClass}">${status}</span></td>
      <td>${r.score}</td>
      <td>
        <button class="btn btn-ghost batch-toggle-detail" data-idx="${idx}">${detailText}</button>
        <div class="batch-detail hidden" id="batch-detail-${idx}">
          ${renderPlanDetail(r)}
        </div>
      </td>
    </tr>`;
  });
  html += `</tbody></table>`;

  el.innerHTML = html;

  // Wire up expand/collapse buttons.
  el.querySelectorAll(".batch-toggle-detail").forEach((btn) => {
    btn.addEventListener("click", (e) => {
      e.stopPropagation();
      const idx = btn.dataset.idx;
      const detail = document.getElementById(`batch-detail-${idx}`);
      detail.classList.toggle("hidden");
      btn.textContent = detail.classList.contains("hidden")
        ? btn.textContent
        : "HIDE";
    });
  });
}

function renderPlanDetail(r) {
  let html = "";
  if (r.errors && r.errors.length > 0) {
    html += `<div class="detail-section"><span class="detail-heading">ERRORS</span><ul>`;
    r.errors.forEach((msg) => {
      const ruleId = msg.split(":")[0];
      const text = msg.slice(ruleId.length + 2);
      html += `<li><span class="rule-id">${ruleId}</span> ${text}</li>`;
    });
    html += `</ul></div>`;
  }
  if (r.warnings && r.warnings.length > 0) {
    html += `<div class="detail-section"><span class="detail-heading">WARNINGS</span><ul>`;
    r.warnings.forEach((msg) => {
      const ruleId = msg.split(":")[0];
      const text = msg.slice(ruleId.length + 2);
      html += `<li><span class="rule-id">${ruleId}</span> ${text}</li>`;
    });
    html += `</ul></div>`;
  }
  if (!html) {
    html = `<p class="notice">No violations.</p>`;
  }
  return html;
}

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
      ${data.rules.map((r) => `<tr class="${r.severity}"><td>${r.id}</td><td>${r.severity.toUpperCase()}</td><td>${r.description}</td></tr>`).join("")}
    </table>
  `;

  const mcpUrl = `${window.location.origin}/mcp`;
  document.getElementById("mcp-config").textContent = JSON.stringify(
    {
      mcpServers: {
        "floors": {
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
checkHash();
