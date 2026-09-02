"use strict";
/* PRODUCT-03 dashboard client, hardened by PRODUCT-04A. Presentation-only:
 * the single fetch() call that can execute a scenario is runScenario()
 * below, fired only from the RUN button handler. Every other function here
 * only reshapes/toggles data already returned by that one call — selecting
 * a profile, expanding the Evidence Passport, expanding the Decision
 * Inspector, viewing the receipt, or resetDashboard() (POST /api/reset,
 * which clears state but never executes) never issues a request that can
 * execute a scenario. There is no autorun: page load and every URL query
 * parameter (including the old ?autorun=1) are presentation-only — see
 * init() below. */

const seed = JSON.parse(document.getElementById("catalog-data").textContent);

const state = {
  profiles: seed.profiles,
  scenarios: seed.scenarios,
  catalog: null, // filled in from GET /api/catalog (manifest metadata)
  lastRunKey: null,
  requestToken: 0,
  running: false,
};

const $ = (id) => document.getElementById(id);

function scenarioTitle(idx) {
  const s = state.scenarios.find((x) => x.index === idx);
  return s ? s.title : String(idx);
}

function profileLabel(id) {
  const p = state.profiles.find((x) => x.id === id);
  return p ? p.label : id;
}

function supportedScenarios(profileId) {
  return state.scenarios.filter((s) => s.supported_profiles.includes(profileId));
}

function selectionKey() {
  return `${$("profileSelect").value}::${$("scenarioSelect").value}`;
}

// ---------------------------------------------------------------------------
// Selectors
// ---------------------------------------------------------------------------

function populateProfileSelect() {
  const sel = $("profileSelect");
  sel.innerHTML = "";
  for (const p of state.profiles) {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = p.label;
    sel.appendChild(opt);
  }
}

function populateScenarioSelect() {
  const profileId = $("profileSelect").value;
  const sel = $("scenarioSelect");
  const prevValue = sel.value;
  sel.innerHTML = "";
  const supported = supportedScenarios(profileId);
  for (const s of supported) {
    const opt = document.createElement("option");
    opt.value = String(s.index);
    opt.textContent = s.hero ? `${s.title}  (hero)` : s.title;
    sel.appendChild(opt);
  }
  // Prefer the hero scenario, else keep the previous selection if still
  // valid under this profile, else fall back to the first supported one.
  const hero = supported.find((s) => s.hero);
  if (supported.some((s) => String(s.index) === prevValue)) {
    sel.value = prevValue;
  } else if (hero) {
    sel.value = String(hero.index);
  } else if (supported.length) {
    sel.value = String(supported[0].index);
  }
}

function renderProfileMeta() {
  const profileId = $("profileSelect").value;
  const target = $("profileMeta");
  if (!state.catalog) {
    target.textContent = "";
    return;
  }
  const p = state.catalog.profiles.find((x) => x.id === profileId);
  if (!p) {
    target.textContent = "";
    return;
  }
  const m = p.manifest;
  const rows = [
    ["Tool", m.tool],
    ["Risk tier", m.risk_tier_default],
    ["Refund window (days)", m.window_days === null ? "N/A" : m.window_days],
    ["Authority ceiling (paise)", m.authority_ceiling_paise],
    ["Latency budget (ms)", m.latency_budget_ms],
    ["Escalation budget (%)", m.escalation_budget_pct],
    ["Reliability floor", m.reliability_floor],
    ["Compensability", m.compensability],
  ];
  target.innerHTML =
    `<div class="profile-meta-title">SAME CONTROLPLANE ENGINE &middot; DIFFERENT USE-CASE MANIFEST</div>` +
    `<div class="profile-meta-grid">` +
    rows.map(([k, v]) => `<div class="pm-cell"><span class="pm-k">${escapeHtml(String(k))}</span><span class="pm-v">${escapeHtml(String(v))}</span></div>`).join("") +
    `</div>`;
}

function escapeHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// ---------------------------------------------------------------------------
// Stale-result guarding (section 8): a result stays visible only for the
// exact profile+scenario it was produced under.
// ---------------------------------------------------------------------------

function markStaleIfNeeded() {
  const key = selectionKey();
  if (state.lastRunKey === null) {
    showOnly("emptyState");
    return;
  }
  if (key !== state.lastRunKey) {
    showOnly("staleBanner");
    collapseExpandables();
  }
}

function showOnly(idToShow) {
  const ids = ["emptyState", "staleBanner", "notApplicable", "notAvailable", "errorState", "resultPanel"];
  for (const id of ids) {
    $(id).hidden = id !== idToShow;
  }
}

function collapseExpandables() {
  for (const id of ["inspectorPanel", "passportPanel", "receiptPanel"]) {
    $(id).hidden = true;
  }
}

// ---------------------------------------------------------------------------
// RUN — the only function in this file that executes a scenario.
// ---------------------------------------------------------------------------

async function runScenario() {
  if (state.running) return;
  const profileId = $("profileSelect").value;
  const scenarioIndex = parseInt($("scenarioSelect").value, 10);
  const key = `${profileId}::${scenarioIndex}`;
  const token = ++state.requestToken;

  state.running = true;
  $("runBtn").disabled = true;
  $("runBtn").textContent = "RUNNING…";

  try {
    const resp = await fetch("/api/run", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id: profileId, scenario_index: scenarioIndex }),
    });
    const body = await resp.json();

    // Discard results for a selection the user has since changed away from.
    if (token !== state.requestToken) return;

    if (body.status === "RUN_IN_PROGRESS") {
      // A RUN was rejected, not queued — no new result exists for `key`, so
      // the previously displayed result (if any) stays authoritative.
      render(body);
      return;
    }

    if (!resp.ok && body.status !== "NOT_APPLICABLE_FOR_PROFILE") {
      state.lastRunKey = key;
      renderError(body);
      return;
    }

    state.lastRunKey = key;
    render(body);
  } catch (err) {
    if (token !== state.requestToken) return;
    state.lastRunKey = key;
    renderError({ message: String(err) });
  } finally {
    if (token === state.requestToken) {
      state.running = false;
      $("runBtn").disabled = false;
      $("runBtn").textContent = "RUN";
    }
  }
}

// ---------------------------------------------------------------------------
// RESET (PRODUCT-04A, section 11) — clears demo-local server state (POST
// /api/reset) and returns the dashboard to its initial, pre-RUN display.
// Executes no scenario.
// ---------------------------------------------------------------------------

async function resetDashboard() {
  if (state.running) return;
  $("resetBtn").disabled = true;
  try {
    await fetch("/api/reset", { method: "POST" });
  } catch (err) {
    // Best-effort: even if the network call fails, still clear local state
    // below so the UI never shows a stale result as current.
  } finally {
    $("resetBtn").disabled = false;
  }
  state.lastRunKey = null;
  state.requestToken++; // discard any in-flight RUN's response once it lands
  collapseExpandables();
  showOnly("emptyState");
}

// ---------------------------------------------------------------------------
// Rendering
// ---------------------------------------------------------------------------

function render(body) {
  collapseExpandables();
  if (body.status === "OK") {
    showOnly("resultPanel");
    renderResult(body);
  } else if (body.status === "NOT_APPLICABLE_FOR_PROFILE") {
    showOnly("notApplicable");
    $("notApplicable").textContent =
      `NOT APPLICABLE FOR PROFILE — ${body.scenario.title} is not supported under ${body.profile.label}.`;
  } else if (body.status === "NOT_AVAILABLE") {
    showOnly("notAvailable");
    $("notAvailable").textContent = `NOT AVAILABLE — ${body.reason || "this result is not available."}`;
  } else if (body.status === "RUN_IN_PROGRESS") {
    showOnly("errorState");
    $("errorState").textContent = "RUN ALREADY IN PROGRESS — please wait for the current run to finish.";
  } else {
    renderError(body);
  }
}

function renderError(body) {
  showOnly("errorState");
  $("errorState").textContent = `INTERNAL APPLICATION ERROR — ${body.message || "unknown error"}`;
}

function badge(el, text, kind) {
  el.textContent = text;
  el.className = "badge " + kind + "-badge badge-" + slug(text);
}

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/(^-|-$)/g, "");
}

function renderResult(body) {
  $("aiIntent").textContent = body.ai_intent;
  const action = body.proposed_action;
  $("proposedAction").textContent =
    action && typeof action === "object"
      ? `tool=${action.tool}  args=${JSON.stringify(action.args)}`
      : String(action);

  const rows = $("ceRows");
  rows.innerHTML = "";
  for (const r of body.claim_evidence_rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.claim_kind)}<div class="sub">tier ${escapeHtml(String(r.tier))} &middot; ${r.load_bearing ? "load-bearing" : "supporting"}</div></td>
      <td class="mono">${escapeHtml(String(r.asserted_value))}</td>
      <td><span class="cmp cmp-${slug(r.comparison_result)}">${escapeHtml(r.comparison_result)}</span></td>
      <td class="mono">${escapeHtml(String(r.evidence_value))}</td>
      <td>${escapeHtml(r.evidence_source)}</td>
      <td>${escapeHtml(r.reliability)}</td>
      <td>${escapeHtml(String(r.freshness_ms))}</td>
      <td class="mono query">${escapeHtml(r.evidence_query)}</td>
    `;
    rows.appendChild(tr);
  }

  $("policyVersion").textContent = body.policy_version;
  const pl = $("policyLines");
  pl.innerHTML = "";
  for (const line of body.policy_lines) {
    const li = document.createElement("li");
    const okMatch = line.includes("[OK]");
    const failMatch = line.includes("[FAIL]");
    li.className = okMatch ? "ok" : failMatch ? "fail" : "warn";
    li.textContent = line.replace(/^\s*\[(OK|FAIL|WARN)\]\s*/, "");
    pl.appendChild(li);
  }
  if (!body.policy_lines.length) {
    pl.innerHTML = '<li class="warn">(no policy predicate evaluated)</li>';
  }

  badge($("verdictBadge"), body.verdict, "verdict");
  badge($("interventionBadge"), body.intervention, "intervention");
  $("rootCause").textContent = body.root_cause || "NOT AVAILABLE";
  $("latency").textContent =
    body.runtime_latency_ms && typeof body.runtime_latency_ms === "object"
      ? Object.entries(body.runtime_latency_ms).map(([k, v]) => `${k}=${v}ms`).join("  ")
      : String(body.runtime_latency_ms);

  const rl = $("reasonLines");
  rl.innerHTML = "";
  for (const line of body.reason_lines) {
    const li = document.createElement("li");
    li.textContent = line.trim();
    li.className = line.includes("FAILED") ? "fail" : "ok";
    rl.appendChild(li);
  }

  badge($("executionState"), body.execution_state, "execution");
  $("callCount").textContent = body.call_count;
  $("idempotencyKey").textContent = body.idempotency_key;

  $("receiptReference").textContent = body.receipt_reference;
  $("traceId").textContent = body.trace_id;
  badge($("receiptVerification"), body.receipt_verification, "receipt");

  $("evidenceOrigin").textContent = `EVIDENCE ORIGIN: ${body.evidence_origin}`;
  $("unavailableFields").textContent = body.unavailable_fields.length
    ? `UNAVAILABLE FIELDS: ${body.unavailable_fields.join(", ")}`
    : "";
  $("unavailableFields").hidden = body.unavailable_fields.length === 0;

  renderExplanationChain(body.inspector);
  $("passportJson").textContent = JSON.stringify(body.passport, null, 2);
  renderReceiptDetail(body);
}

function renderExplanationChain(inspector) {
  const el = $("explanationChain");
  el.innerHTML = "";
  const steps = [];
  steps.push({ label: "AI CLAIM", value: inspector.ai_claim });
  for (const entry of inspector.claim_evidence_chain) {
    steps.push({
      label: entry.claim_field,
      value: `${entry.evidence_field}  →  ${entry.comparison_rule}  →  ${entry.comparison_result}`,
    });
  }
  steps.push({ label: "POLICY", value: inspector.policy_version });
  steps.push({ label: "PREDICATE", value: JSON.stringify(inspector.predicate_result) });
  steps.push({ label: "VERDICT", value: inspector.verdict });
  steps.push({ label: "INTERVENTION", value: inspector.intervention });
  steps.push({ label: "EXECUTION", value: inspector.execution_state });

  for (const s of steps) {
    const div = document.createElement("div");
    div.className = "chain-step";
    div.innerHTML = `<span class="chain-label">${escapeHtml(s.label)}</span><span class="chain-value">${escapeHtml(String(s.value))}</span>`;
    el.appendChild(div);
  }
}

function renderReceiptDetail(body) {
  const dl = $("receiptDetail");
  const rows = [
    ["Receipt reference", body.receipt_reference],
    ["Trace ID", body.trace_id],
    ["Idempotency key", body.idempotency_key],
    ["Policy version", body.policy_version],
    ["Verdict", body.verdict],
    ["Intervention", body.intervention],
    ["Execution state", body.execution_state],
    ["Verification", body.receipt_verification],
  ];
  dl.innerHTML = rows.map(([k, v]) => `<dt>${escapeHtml(k)}</dt><dd class="mono">${escapeHtml(String(v))}</dd>`).join("");
}

// ---------------------------------------------------------------------------
// Wiring
// ---------------------------------------------------------------------------

function initExpandButtons() {
  document.querySelectorAll(".action-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const target = $(btn.dataset.target);
      target.hidden = !target.hidden;
    });
  });
}

async function init() {
  populateProfileSelect();
  populateScenarioSelect();
  initExpandButtons();

  $("profileSelect").addEventListener("change", () => {
    populateScenarioSelect();
    renderProfileMeta();
    markStaleIfNeeded();
  });
  $("scenarioSelect").addEventListener("change", markStaleIfNeeded);
  $("runBtn").addEventListener("click", runScenario);
  $("resetBtn").addEventListener("click", resetDashboard);

  try {
    const resp = await fetch("/api/catalog");
    state.catalog = await resp.json();
  } catch (err) {
    state.catalog = null;
  }
  renderProfileMeta();
  showOnly("emptyState");

  // Optional deep-link convenience for sharing/QA: ?profile=<id>&scenario=<n>
  // pre-selects the dropdowns. Presentation only — PRODUCT-04A (section 6)
  // removed the old ?autorun=1 behavior entirely: page load, refresh, and
  // every query parameter combination must never execute a scenario. Only
  // the explicit RUN button (runScenario(), wired below) may do that.
  const params = new URLSearchParams(location.search);
  const qProfile = params.get("profile");
  const qScenario = params.get("scenario");
  if (qProfile && state.profiles.some((p) => p.id === qProfile)) {
    $("profileSelect").value = qProfile;
    populateScenarioSelect();
    renderProfileMeta();
  }
  if (qScenario && [...$("scenarioSelect").options].some((o) => o.value === qScenario)) {
    $("scenarioSelect").value = qScenario;
  }
  const qExpand = params.get("expand");
  if (qExpand) {
    for (const id of qExpand.split(",")) {
      if (["inspectorPanel", "passportPanel", "receiptPanel"].includes(id)) {
        $(id).hidden = false;
      }
    }
  }
}

init();
