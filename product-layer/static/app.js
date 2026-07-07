const state = {
  products: [],
  selected: null,
  agents: null,
  lastAssessment: null,
  lastAvatar: null,
  lastAssessmentText: "",
  selectedProductRecord: null,
};

const $ = (id) => document.getElementById(id);

function headers(contentType) {
  const result = {
    "X-Region": "EU",
    "X-Purpose": "analytics",
  };
  if (contentType) result["Content-Type"] = contentType;
  return result;
}

async function api(path, options = {}) {
  const timeoutMs = options.timeoutMs;
  const controller = timeoutMs ? new AbortController() : null;
  const timeoutId = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
  const { contentType, headers: optionHeaders, timeoutMs: _timeoutMs, ...fetchOptions } = options;
  try {
    const response = await fetch(path, {
      ...fetchOptions,
      signal: controller ? controller.signal : options.signal,
      headers: { ...headers(contentType), ...(optionHeaders || {}) },
    });
    const text = await response.text();
    const payload = text ? JSON.parse(text) : null;
    if (!response.ok) throw new Error(payload?.error || response.statusText);
    return payload;
  } catch (error) {
    if (error.name === "AbortError") {
      throw new Error(`Request timed out after ${Math.round(timeoutMs / 1000)}s: ${path}`);
    }
    throw error;
  } finally {
    if (timeoutId) clearTimeout(timeoutId);
  }
}

function query() {
  const params = new URLSearchParams();
  if ($("search").value) params.set("search", $("search").value);
  if ($("family").value) params.set("family", $("family").value);
  if ($("status").value) params.set("status", $("status").value);
  params.set("limit", "250");
  return params.toString();
}

async function loadProducts() {
  const data = await api(`/api/products?${query()}`);
  state.products = data.products;
  $("count").textContent = `${state.products.length} shown`;
  renderProducts();
  if (state.products.length && !state.selected) selectProduct(state.products[0].id);
  if (state.selected && !state.products.some((p) => p.id === state.selected)) selectProduct(state.products[0]?.id);
}

async function loadSummary() {
  const data = await api("/api/summary");
  const familyCount = Object.keys(data.families).length;
  const needsReview = data.certification_statuses.needs_review || 0;
  const certified = data.certification_statuses.certified || 0;
  $("summary").innerHTML = `
    <div class="metric"><strong>${data.total_products}</strong><span>Total products</span></div>
    <div class="metric"><strong>${familyCount}</strong><span>Product families</span></div>
    <div class="metric"><strong>${certified}</strong><span>Certified</span></div>
    <div class="metric"><strong>${needsReview}</strong><span>Needs review</span></div>
  `;
}

async function loadGovernance() {
  const [contract, catalog, lineage] = await Promise.all([
    api("/api/integrations/data-layer"),
    api("/api/catalog/data-products"),
    api("/api/lineage"),
  ]);
  const dataProduct = catalog.data_products[0];
  $("governance").innerHTML = `
    <div class="governance-grid">
      <div>
        <h3>Data-layer contract</h3>
        <table>
          <tr><th>Source</th><td>${escapeHtml(contract.source_endpoint)}</td></tr>
          <tr><th>URL</th><td>${escapeHtml(contract.export_url)}</td></tr>
          <tr><th>Flow</th><td>${escapeHtml(contract.source_layer)} -> ${escapeHtml(contract.target_layer)}</td></tr>
          <tr><th>Permission</th><td>${escapeHtml(contract.sync_permission)}</td></tr>
        </table>
      </div>
      <div>
        <h3>Curated data product</h3>
        <table>
          <tr><th>Name</th><td>${escapeHtml(dataProduct.name)}</td></tr>
          <tr><th>Owner</th><td>${escapeHtml(dataProduct.owner)}</td></tr>
          <tr><th>Target</th><td>${escapeHtml(dataProduct.interfaces.target_lakehouse.table)}</td></tr>
          <tr><th>Format</th><td>${escapeHtml(dataProduct.interfaces.target_lakehouse.format)}</td></tr>
        </table>
      </div>
    </div>
    <p class="muted">${escapeHtml(lineage.layers.map((layer) => layer.name).join(" -> "))}</p>
  `;
}

async function loadAgents() {
  try {
    const data = await api("/api/agents-layer/agents");
    state.agents = data;
    renderAgents(data);
  } catch (error) {
    $("agentsLayerStatus").textContent = error.message;
    $("agentsCatalog").innerHTML = "";
    $("agentApiExamples").innerHTML = "";
  }
}

function renderAgents(data) {
  const integration = data.integration || {};
  const layers = data.layers || {};
  const source = data.source || {};
  const statusClass = data.status === "live" ? "ok" : data.status === "disabled" ? "bad" : "warn";
  $("agentsLayerStatus").innerHTML = `
    <span class="badge ${statusClass}">${escapeHtml(data.status || "unknown")}</span>
    <span>${escapeHtml(source.url || integration.base_url || "")}</span>
    <span>${escapeHtml(integration.source_layer || "curated")} -> ${escapeHtml(integration.target_layer || "advisory_agents")}</span>
  `;
  $("agentsCatalog").innerHTML = Object.entries(layers).map(([layerName, agents]) => `
    <div class="agent-layer">
      <h3>${escapeHtml(layerLabel(layerName))}</h3>
      <div class="agents-grid">
        ${(agents || []).map((agent) => `
          <article class="agent-card">
            <div>
              <strong>${escapeHtml(agent.name || agent.id)}</strong>
              <p class="muted">${escapeHtml(agent.id)} | v${escapeHtml(agent.version || "0.1.0")}</p>
            </div>
            <p>${(agent.scope || []).map((item) => `<span class="badge">${escapeHtml(item)}</span>`).join(" ")}</p>
            <button class="agent-call" data-agent-id="${escapeHtml(agent.id)}">Assess</button>
          </article>
        `).join("")}
      </div>
    </div>
  `).join("");
  const apiCalls = [
    ...(integration.rest_api_calls || []),
    ...((integration.avatar_layer && integration.avatar_layer.rest_api_calls) || []),
  ];
  $("agentApiExamples").innerHTML = `
    <div class="api-grid">
      ${apiCalls.map((call) => `
        <div class="api-call">
          <strong>${escapeHtml(call.name)}</strong>
          <p class="muted">${escapeHtml(call.method)} ${escapeHtml(call.url)}</p>
          <pre>${escapeHtml(call.curl)}</pre>
        </div>
      `).join("")}
    </div>
  `;
  document.querySelectorAll("[data-agent-id]").forEach((button) => {
    button.addEventListener("click", () => runAgentAssessment(button.dataset.agentId));
  });
}

function layerLabel(layerName) {
  const labels = {
    "compliance-agents-layer": "Compliance agents layer",
    "expert-agents-layer": "Expert agents layer",
  };
  return labels[layerName] || layerName;
}

function renderProducts() {
  $("products").innerHTML = state.products.map((product) => {
    const status = product.metadata?.certification_status || "unknown";
    const statusClass = status === "certified" ? "ok" : status === "needs_review" ? "warn" : "";
    return `
      <button class="product ${state.selected === product.id ? "active" : ""}" data-id="${product.id}">
        <span>
          <strong>${escapeHtml(product.name)}</strong><br>
          <small>${escapeHtml(product.sku)} | ${escapeHtml(product.family)} | ${escapeHtml(product.lifecycle_status)}</small>
        </span>
        <span class="badge ${statusClass}">${escapeHtml(status)}</span>
      </button>
    `;
  }).join("");
  document.querySelectorAll(".product").forEach((button) => {
    button.addEventListener("click", () => selectProduct(button.dataset.id));
  });
}

async function selectProduct(id) {
  if (!id) {
    $("detail").innerHTML = "<p>No product selected.</p>";
    return;
  }
  state.selected = id;
  renderProducts();
  const product = await api(`/api/products/${id}`);
  const passport = await api(`/api/passport/${id}`);
  renderDetail(product, passport);
}

function renderDetail(product, passport) {
  const attrs = product.attributes || {};
  const identity = passport.identity || {};
  const documents = product.documents || [];
  state.selectedProductRecord = product;
  $("htmlExport").href = `/api/export/passport/${product.id}.html`;
  $("svgExport").href = `/api/export/passport/${product.id}.svg`;
  $("detail").innerHTML = `
    <div class="detail-hero">
      <div>
        <h3>${escapeHtml(product.name)}</h3>
        <p class="muted">${escapeHtml(product.sku)} | ${escapeHtml(product.family)}</p>
      </div>
      <div class="detail-badges">${(product.certifications || []).map((c) => `<span class="badge">${escapeHtml(c)}</span>`).join(" ")}</div>
    </div>
    <section class="detail-section">
      <h3>Attributes</h3>
      <div class="attribute-list">${Object.entries(attrs).sort(([left], [right]) => left.localeCompare(right)).map(([key, value]) => `
        <div class="attribute-row">
          <div class="attribute-label">
            <button class="attribute-name attribute-name-button" data-history-attr="${escapeHtml(key)}" type="button">
              ${escapeHtml(formatAttributeLabel(key))}
            </button>
            <div class="attribute-source">${escapeHtml(attributeSource(product, key))}</div>
          </div>
          <div class="attribute-value">
            <input data-attr="${escapeHtml(key)}" value="${escapeHtml(formatAttributeValue(value))}">
          </div>
        </div>
      `).join("")}</div>
      <div class="actions"><button id="saveAttrs">Save attributes</button></div>
    </section>
    <section class="detail-section">
      <h3>Digital Product Passport preview</h3>
    <div class="actions">
      <a href="/dpp/${encodeURIComponent(product.id)}" target="_blank">Public DPP</a>
      <a href="/api/dpp/${encodeURIComponent(product.id)}?view=consumer" target="_blank">Consumer JSON</a>
      <a href="/api/dpp/${encodeURIComponent(product.id)}?view=authority" target="_blank">Authority JSON</a>
    </div>
    <table>
      <tr><th>GTIN</th><td>${escapeHtml(identity.gtin || "")}</td></tr>
      <tr><th>Batch/Lot</th><td>${escapeHtml(identity.batch_lot_number || "")}</td></tr>
      <tr><th>Serial</th><td>${escapeHtml(identity.serial_number || "")}</td></tr>
      <tr><th>Instance ID</th><td>${escapeHtml(identity.globally_unique_instance_id || "")}</td></tr>
      <tr><th>Data Matrix</th><td>${escapeHtml(identity.data_matrix?.payload || "")}</td></tr>
      <tr><th>Owner</th><td>${escapeHtml(product.metadata?.owner || "")}</td></tr>
      <tr><th>Lineage</th><td>${escapeHtml(product.metadata?.lineage || "")}</td></tr>
      <tr><th>Classification</th><td>${escapeHtml(product.metadata?.classification || "")}</td></tr>
      <tr><th>Documents</th><td>${documents.map((d) => escapeHtml(d.name)).join("<br>")}</td></tr>
    </table>
    </section>
  `;
  $("saveAttrs").addEventListener("click", saveAttributes);
  document.querySelectorAll("[data-history-attr]").forEach((button) => {
    button.addEventListener("click", () => showAttributeHistory(product, button.dataset.historyAttr));
  });
}

function formatAttributeLabel(key) {
  return String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function formatAttributeValue(value) {
  if (Array.isArray(value)) return value.join(", ");
  if (value && typeof value === "object") return JSON.stringify(value);
  return String(value ?? "");
}

function attributeSource(product, key) {
  const metadata = product.metadata || {};
  const explicitSources = product.attribute_sources || metadata.attribute_sources || product.sources || {};
  if (explicitSources[key]) return explicitSources[key];
  const citations = product.citations || metadata.citations || {};
  if (citations[key]) return citations[key];
  const document = (product.documents || [])[0];
  if (document?.source_uri) return `${metadata.source_system || "data-layer"} -> ${document.source_uri} -> attributes.${key}`;
  if (document?.name) return `${metadata.source_system || "data-layer"} -> ${document.name} -> attributes.${key}`;
  if (metadata.upstream_export_url) return `${metadata.source_system || "data-layer"} -> ${metadata.upstream_export_url} -> attributes.${key}`;
  return `${metadata.source_system || "product-layer"} -> attributes.${key}`;
}

function attributeHistory(product, key) {
  const history = product.attribute_history || product.metadata?.attribute_history || {};
  const entries = Array.isArray(history[key]) ? history[key] : [];
  if (entries.length) return entries;
  const value = (product.attributes || {})[key];
  return [{
    value,
    previous_value: null,
    changed_at: product.updated_at || product.created_at || "",
    operation: "current_value",
    source_system: product.metadata?.source_system || "product-layer",
    source_name: attributeSource(product, key),
    source_type: "current_curated_value",
    source_uri: product.metadata?.upstream_export_url || "",
    lineage: product.metadata?.lineage || "",
    owner: product.metadata?.owner || "",
    domain: product.metadata?.domain || "product",
    classification: product.metadata?.classification || "",
    changed_by: "",
  }];
}

function showAttributeHistory(product, key) {
  const modal = $("attributeHistoryModal");
  const body = $("attributeHistoryBody");
  if (!modal || !body || !key) return;
  const entries = attributeHistory(product, key);
  $("attributeHistoryTitle").textContent = `${formatAttributeLabel(key)} value history`;
  body.innerHTML = `
    <div class="attribute-history-head">
      <div>
        <strong>${escapeHtml(formatAttributeLabel(key))}</strong>
        <span>${entries.length} value ${entries.length === 1 ? "event" : "events"}</span>
      </div>
    </div>
    <div class="attribute-history-list">
      ${entries.map((entry, index) => {
        const nextEntry = entries[index + 1];
        const sourceChanged = Boolean(nextEntry) && sourceSignature(entry) !== sourceSignature(nextEntry);
        return `
        <div class="attribute-history-item">
          <div class="attribute-history-row-head">
            <div class="attribute-history-value">${escapeHtml(formatAttributeValue(entry.value))}</div>
            ${sourceChanged ? '<span class="badge warn">Source changed</span>' : ""}
          </div>
          <div class="attribute-history-meta">
            <span>${escapeHtml(formatTimestamp(entry.changed_at))}</span>
            <span>${escapeHtml(entry.operation || "value")}</span>
            <span>${escapeHtml(entry.source_system || "")}</span>
          </div>
          <div class="attribute-history-source">
            Data source: ${escapeHtml([entry.source_name, entry.source_uri].filter(Boolean).join(" | ") || attributeSource(product, key))}
          </div>
          ${entry.previous_value !== null && entry.previous_value !== undefined ? `
            <div class="attribute-history-previous">Previous: ${escapeHtml(formatAttributeValue(entry.previous_value))}</div>
          ` : ""}
          ${entry.lineage ? `<div class="attribute-history-lineage">Lineage: ${escapeHtml(entry.lineage)}</div>` : ""}
        </div>
      `; }).join("")}
    </div>
  `;
  modal.classList.remove("hidden");
}

function closeAttributeHistoryModal() {
  $("attributeHistoryModal").classList.add("hidden");
}

function sourceSignature(entry) {
  return [
    entry.source_system || "",
    entry.source_name || "",
    entry.source_uri || "",
    entry.source_type || "",
  ].join("|");
}

function formatTimestamp(value) {
  if (!value) return "unknown time";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

async function saveAttributes() {
  const attributes = {};
  document.querySelectorAll("[data-attr]").forEach((input) => {
    attributes[input.dataset.attr] = coerce(input.value);
  });
  try {
    await api(`/api/products/${state.selected}/attributes`, {
      method: "PATCH",
      contentType: "application/json",
      body: JSON.stringify({ attributes }),
    });
    await loadProducts();
    await selectProduct(state.selected);
  } catch (error) {
    alert(error.message);
  }
}

async function importPayload(contentType) {
  try {
    const data = await api("/api/import", {
      method: "POST",
      contentType,
      body: $("importText").value,
    });
    $("importResult").textContent = `Imported ${data.imported}; errors ${data.errors.length}`;
    await refreshAll();
  } catch (error) {
    $("importResult").textContent = error.message;
  }
}

async function syncDataLayer() {
  try {
    const data = await api("/api/sync/data-layer", {
      method: "POST",
      contentType: "application/json",
      body: "{}",
    });
    $("importResult").textContent = `Synced ${data.result.imported} from data-layer`;
    await refreshAll();
  } catch (error) {
    $("importResult").textContent = error.message;
  }
}

async function runValidation() {
  const data = await api("/api/validation/status?limit=1000");
  $("validation").innerHTML = `
    <p><strong>${data.counts.certified || 0}</strong> certified, <strong>${data.counts.needs_review || 0}</strong> needs review.</p>
    <table>
      ${data.results.slice(0, 100).map((result) => `
        <tr>
          <th>${escapeHtml(result.sku)}</th>
          <td><span class="badge ${result.status === "certified" ? "ok" : "warn"}">${escapeHtml(result.status)}</span></td>
          <td>${escapeHtml(result.issues.map((issue) => `${issue.field}: ${issue.message}`).join("; "))}</td>
        </tr>
      `).join("")}
    </table>
  `;
}

async function runAgentAssessment(agentId) {
  if (!state.selected) {
    openAgentModal("Agent assessment", "<p>Select a product first.</p>", "");
    return;
  }
  const label = agentId || "all advisory agents";
  openAgentModal(`Assessment: ${label}`, "<p>Running assessment...</p>", "");
  const body = { product_id: state.selected };
  if (agentId) body.agent_ids = [agentId];
  try {
    const data = await api("/api/agents-layer/assessments", {
      method: "POST",
      contentType: "application/json",
      body: JSON.stringify(body),
    });
    renderAgentAssessment(data, agentId);
  } catch (error) {
    const message = `Assessment failed: ${error.message}`;
    $("agentAssessmentResult").innerHTML = `<p class="badge bad">${escapeHtml(message)}</p>`;
    openAgentModal(`Assessment: ${label}`, `<p class="badge bad">${escapeHtml(message)}</p>`, message);
  }
}

function renderAgentAssessment(data, agentId) {
  const readiness = data.readiness || {};
  const findings = data.findings || [];
  const context = data.product_context || {};
  const statusClass = readiness.status === "ready_for_human_review" ? "ok" : readiness.status === "blocked" ? "bad" : "warn";
  const html = `
    <h3>Assessment result${agentId ? `: ${escapeHtml(agentId)}` : ""}</h3>
    <div class="assessment-context">
      <span>Product ${escapeHtml(context.product_id || state.selected || "unknown")}</span>
      <span>${escapeHtml(context.product_family || "unknown family")}</span>
      <span>Lifecycle ${escapeHtml(context.lifecycle_state || "unknown")}</span>
      <span>Market ${escapeHtml(context.target_market || "EU")}</span>
    </div>
    <div class="assessment-summary">
      <span class="badge ${statusClass}">${escapeHtml(readiness.status || "unknown")}</span>
      <span>Score ${escapeHtml(String(readiness.score ?? ""))}</span>
      <span>${escapeHtml(String(readiness.failed_checks ?? 0))} failed checks</span>
      <span>${escapeHtml(data.assessment_id || "")}</span>
    </div>
    <table>
      ${findings.map((finding) => `
        <tr>
          <th>${escapeHtml(finding.agent_name || finding.agent_id)}</th>
          <td><span class="badge ${finding.status === "passed" ? "ok" : "warn"}">${escapeHtml(finding.status)}</span></td>
          <td>${escapeHtml(finding.criterion || "")}<br><span class="muted">${escapeHtml(finding.recommended_action || "")}</span></td>
        </tr>
      `).join("")}
    </table>
    <div class="avatar-assessment" data-avatar-assessment-panel>
      <div class="avatar-visual" data-avatar-state="thinking" aria-hidden="true">
        <span></span><span></span><span></span>
      </div>
      <div>
        <h3>Assess avatar</h3>
        <p class="muted">Preparing spoken assessment...</p>
      </div>
    </div>
  `;
  state.lastAssessment = data;
  state.lastAssessmentText = "";
  $("agentAssessmentResult").innerHTML = html;
  openAgentModal(`Assessment: ${agentId || "all advisory agents"}`, html, "");
  runAvatarAssessment(data, agentId).catch((error) => {
    renderAvatarAssessmentError(error);
  });
}

async function runAvatarAssessment(assessment, agentId) {
  if (!state.selected) return;
  const body = {
    product_id: state.selected,
    assessment,
    assessment_mode: assessmentModeForAgent(agentId),
  };
  if (agentId) body.agent_ids = [agentId];
  const data = await api("/api/avatar-layer/assessments", {
    method: "POST",
    contentType: "application/json",
    timeoutMs: 12000,
    body: JSON.stringify(body),
  });
  renderAvatarAssessment(data);
}

function assessmentModeForAgent(agentId) {
  if (!agentId) return "portfolio";
  const raw = String(agentId || "").toLowerCase();
  if (raw.includes("cyber") || raw.includes("security")) return "cybersecurity";
  if (raw.includes("dpp") || raw.includes("passport")) return "dpp";
  if (raw.includes("compliance")) return "compliance";
  return "general";
}

function renderAvatarAssessment(data) {
  state.lastAvatar = data;
  state.lastAssessmentText = data.spoken_summary || state.lastAssessmentText;
  const severity = data.severity || "none";
  const stateName = severity === "critical" || severity === "high" ? "warning" : "speaking";
  const html = `
    <div class="avatar-visual" data-avatar-state="${escapeHtml(stateName)}" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>
    <div>
      <h3>Assess avatar</h3>
      <div class="assessment-summary">
        <span class="badge ${severity === "high" || severity === "critical" ? "bad" : severity === "none" ? "" : "warn"}">${escapeHtml(data.assessment_status || "unknown")}</span>
        <span>Severity ${escapeHtml(severity)}</span>
        <span>${escapeHtml(String(Math.round((data.confidence || 0) * 100)))}% confidence</span>
      </div>
      <p>${escapeHtml(data.display_summary || data.spoken_summary || "")}</p>
      <p class="muted">Transcript ${escapeHtml((data.transcript?.entries || []).length)} entries | restricted refs hidden ${escapeHtml(data.restricted_refs_hidden || 0)}</p>
      ${renderAvatarTraceability(data)}
    </div>
  `;
  renderAvatarPanels(html);
}

function recordAvatarEvent(action) {
  if (!state.selected) return;
  const avatar = state.lastAvatar || {};
  const session = avatar.session || {};
  api("/api/avatar-layer/events", {
    method: "POST",
    contentType: "application/json",
    body: JSON.stringify({
      action,
      product_id: avatar.product_id || state.selected,
      session_id: session.session_id,
      transcript_id: session.transcript_id,
      assessment_mode: avatar.assessment_mode,
    }),
  }).catch(() => {});
}

function renderAvatarAssessmentError(error) {
  state.lastAssessmentText = "";
  const configuredUrl = state.agents?.integration?.avatar_layer?.base_url || "configured avatar-layer URL";
  const html = `
    <div class="avatar-visual" data-avatar-state="error" aria-hidden="true">
      <span></span><span></span><span></span>
    </div>
    <div>
      <h3>Assess avatar</h3>
      <p class="badge bad">${escapeHtml(error.message)}</p>
      <p class="muted">Avatar runtime: ${escapeHtml(configuredUrl)}. Start or restart the avatar-layer service, then run the assessment again.</p>
    </div>
  `;
  renderAvatarPanels(html);
}

function renderAvatarPanels(html) {
  document.querySelectorAll("[data-avatar-assessment-panel]").forEach((target) => {
    target.innerHTML = html;
  });
}

function renderAvatarTraceability(data) {
  const transcript = data.transcript?.entries || [];
  const evidence = data.evidence_refs || [];
  const missing = data.missing_evidence || [];
  const actions = data.next_actions || [];
  const versions = Object.entries(data.agent_versions || {});
  const rules = data.rule_traceability || [];
  const product = data.product_context || {};
  return `
    <div class="avatar-traceability">
      <div>
        <strong>Product context</strong>
        <ul>
          <li>${escapeHtml(product.id || data.product_id || "unknown-product")}</li>
          <li>Lifecycle ${escapeHtml(product.lifecycle_state || "unknown")}</li>
          <li>Classification ${escapeHtml(product.classification || "internal")}</li>
          <li>Layer ${escapeHtml(product.lakehouse_layer || "curated")}</li>
        </ul>
      </div>
      <div>
        <strong>Transcript</strong>
        <ol>${transcript.map((entry) => `<li>${escapeHtml(entry.kind || "entry")}: ${escapeHtml(entry.text || "")}</li>`).join("") || "<li>none</li>"}</ol>
      </div>
      <div>
        <strong>Evidence</strong>
        <ul>${evidence.map((ref) => `<li>${escapeHtml(ref.type || "evidence")} | ${escapeHtml(ref.reference || "")} | ${escapeHtml(ref.redacted ? "redacted" : ref.classification || "internal")}</li>`).join("") || "<li>none</li>"}</ul>
      </div>
      <div>
        <strong>Missing evidence</strong>
        <ul>${missing.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>none</li>"}</ul>
      </div>
      <div>
        <strong>Next actions</strong>
        <ul>${actions.map((item) => `<li>${escapeHtml(item)}</li>`).join("") || "<li>none</li>"}</ul>
      </div>
      <div>
        <strong>Agent versions</strong>
        <ul>${versions.map(([id, version]) => `<li>${escapeHtml(id)} v${escapeHtml(version)}</li>`).join("") || "<li>none</li>"}</ul>
      </div>
      <div>
        <strong>Rule traceability</strong>
        <ul>${rules.map((rule) => `<li>${escapeHtml(rule.agent_id || "agent")} | ${escapeHtml(rule.rule_id || "rule")} v${escapeHtml(rule.rule_version || "unknown")} | ${escapeHtml((rule.standard_refs || []).join(", ") || "no standards")} | review ${escapeHtml(rule.human_review_state || "required")}</li>`).join("") || "<li>none</li>"}</ul>
      </div>
      <p class="muted">Human review required: ${escapeHtml(data.human_review_required ? "yes" : "no")}</p>
    </div>
  `;
}

function openAgentModal(title, bodyHtml, voiceText) {
  $("agentModalTitle").textContent = title;
  $("agentModalBody").innerHTML = bodyHtml;
  state.lastAssessmentText = voiceText || state.lastAssessmentText || "";
  $("agentModal").classList.remove("hidden");
}

function closeAgentModal() {
  recordAvatarEvent("close");
  stopAgentSpeech();
  $("agentModal").classList.add("hidden");
}

function speakAgentAssessment() {
  if (!state.lastAssessmentText) {
    $("agentModalBody").insertAdjacentHTML("afterbegin", '<p class="badge warn">Avatar spoken summary is not available yet.</p>');
    return;
  }
  if (!("speechSynthesis" in window) || typeof SpeechSynthesisUtterance === "undefined") {
    $("agentModalBody").insertAdjacentHTML("afterbegin", '<p class="badge warn">Voice output is not supported in this browser.</p>');
    return;
  }
  stopAgentSpeech();
  const utterance = new SpeechSynthesisUtterance(state.lastAssessmentText);
  utterance.rate = 0.95;
  utterance.pitch = 1;
  window.speechSynthesis.speak(utterance);
  recordAvatarEvent("speak");
}

function stopAgentSpeech() {
  if ("speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
  recordAvatarEvent("stop");
}

async function refreshAll() {
  await Promise.all([loadSummary(), loadProducts(), loadGovernance()]);
}

function coerce(value) {
  if (value.trim() === "") return "";
  const number = Number(value);
  return Number.isNaN(number) ? value : number;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

["family", "status"].forEach((id) => {
  $(id).addEventListener("input", refreshAll);
});
$("search").addEventListener("keydown", (event) => {
  if (event.key !== "Enter") return;
  event.preventDefault();
  refreshAll();
});
$("importJson").addEventListener("click", () => importPayload("application/json"));
$("importCsv").addEventListener("click", () => importPayload("text/csv"));
$("validate").addEventListener("click", runValidation);
$("loadGovernance").addEventListener("click", loadGovernance);
$("syncDataLayer").addEventListener("click", syncDataLayer);
$("loadAgents").addEventListener("click", loadAgents);
$("runAgentAssessment").addEventListener("click", () => runAgentAssessment());
$("closeAgentModal").addEventListener("click", closeAgentModal);
$("closeAttributeHistoryModal").addEventListener("click", closeAttributeHistoryModal);
$("speakAgentAssessment").addEventListener("click", speakAgentAssessment);
$("stopAgentSpeech").addEventListener("click", stopAgentSpeech);
$("agentModal").addEventListener("click", (event) => {
  if (event.target === $("agentModal")) closeAgentModal();
});
$("attributeHistoryModal").addEventListener("click", (event) => {
  if (event.target === $("attributeHistoryModal")) closeAttributeHistoryModal();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !$("agentModal").classList.contains("hidden")) closeAgentModal();
  if (event.key === "Escape" && !$("attributeHistoryModal").classList.contains("hidden")) closeAttributeHistoryModal();
});

Promise.all([refreshAll(), loadAgents()]).catch((error) => {
  $("products").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
});
