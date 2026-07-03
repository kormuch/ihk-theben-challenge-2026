const state = {
  products: [],
  selected: null,
};

const $ = (id) => document.getElementById(id);

function headers(contentType) {
  const result = {
    "X-Role": $("role").value,
    "X-Region": "EU",
    "X-Purpose": "analytics",
  };
  if (contentType) result["Content-Type"] = contentType;
  return result;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { ...headers(options.contentType), ...(options.headers || {}) },
  });
  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;
  if (!response.ok) throw new Error(payload?.error || response.statusText);
  return payload;
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
  $("htmlExport").href = `/api/export/passport/${product.id}.html`;
  $("svgExport").href = `/api/export/passport/${product.id}.svg`;
  $("detail").innerHTML = `
    <h3>${escapeHtml(product.name)}</h3>
    <p class="muted">${escapeHtml(product.sku)} | ${escapeHtml(product.family)}</p>
    <p>${(product.certifications || []).map((c) => `<span class="badge">${escapeHtml(c)}</span>`).join(" ")}</p>
    <h3>Attribute editor</h3>
    <table>${Object.entries(attrs).map(([key, value]) => `
      <tr>
        <th>${escapeHtml(key)}</th>
        <td><input data-attr="${escapeHtml(key)}" value="${escapeHtml(String(value))}"></td>
      </tr>
    `).join("")}</table>
    <div class="actions"><button id="saveAttrs">Save attributes</button></div>
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
      <tr><th>Documents</th><td>${(product.documents || []).map((d) => escapeHtml(d.name)).join("<br>")}</td></tr>
    </table>
  `;
  $("saveAttrs").addEventListener("click", saveAttributes);
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

async function refreshAll() {
  await Promise.all([loadSummary(), loadProducts(), loadGovernance()]);
}

function coerce(value) {
  if (value.trim() === "") return "";
  const number = Number(value);
  return Number.isNaN(number) ? value : number;
}

function escapeHtml(value) {
  return value.replace(/[&<>"']/g, (char) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#039;",
  }[char]));
}

["search", "family", "status", "role"].forEach((id) => {
  $(id).addEventListener("input", refreshAll);
});
$("refresh").addEventListener("click", refreshAll);
$("importJson").addEventListener("click", () => importPayload("application/json"));
$("importCsv").addEventListener("click", () => importPayload("text/csv"));
$("validate").addEventListener("click", runValidation);
$("loadGovernance").addEventListener("click", loadGovernance);
$("syncDataLayer").addEventListener("click", syncDataLayer);

refreshAll().catch((error) => {
  $("products").innerHTML = `<p>${escapeHtml(error.message)}</p>`;
});
