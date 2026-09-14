/*
 * Head office dashboard.
 *
 * Code and comments are in English; every string the reader sees is Spanish.
 *
 * nginx proxies /api to the central API, so this page stays on one origin and
 * knows nothing about which host port the API is published on. See nginx.conf.
 */

const API_BASE_URL = "/api";

const CURRENCY_FORMATTER = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

const UNITS_FORMATTER = new Intl.NumberFormat("es-CO");

const salesChart = document.getElementById("sales-chart");
const productsChart = document.getElementById("products-chart");
const storeFilter = document.getElementById("store-filter");
const refreshButton = document.getElementById("refresh-button");
const updatedLabel = document.getElementById("updated-label");
const message = document.getElementById("message");

/** Store display names, keyed by id, so charts can label a store properly. */
let storeNames = new Map();

function showMessage(text, kind) {
  message.textContent = text;
  message.className = "message";
  if (kind) {
    message.classList.add(`is-${kind}`);
  }
}

function clearMessage() {
  showMessage("", null);
}

function formatCurrency(value) {
  return CURRENCY_FORMATTER.format(Number(value));
}

function formatUnits(value) {
  return `${UNITS_FORMATTER.format(Number(value))} und`;
}

async function fetchJson(path) {
  const response = await fetch(`${API_BASE_URL}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return response.json();
}

/**
 * Fill the store filter from the API.
 *
 * The "all stores" option is the one thing declared in the HTML; every real
 * store comes from here, so adding a store at head office needs no edit to
 * this page.
 */
async function loadStores() {
  const stores = await fetchJson("/stores");
  storeNames = new Map(stores.map((store) => [store.id, store.name]));

  const selected = storeFilter.value;
  // Keep the first option ("Todas las tiendas"), replace the rest.
  while (storeFilter.options.length > 1) {
    storeFilter.remove(1);
  }
  for (const store of stores) {
    const option = document.createElement("option");
    option.value = store.id;
    option.textContent = store.name;
    storeFilter.appendChild(option);
  }
  storeFilter.value = selected;
}

/** Chart 1: total sales per store, in Colombian pesos. */
async function loadSalesByStore() {
  const rows = await fetchJson("/reports/sales-by-store");

  // Every store is returned, including one that has forwarded nothing. A
  // store missing from a comparison reads as a bug; a store at zero reads as
  // information — so nothing is filtered out here.
  if (!rows.length) {
    renderChartMessage(salesChart, "Aún no hay tiendas registradas.");
    return;
  }

  const everythingIsZero = rows.every((row) => Number(row.total) === 0);
  if (everythingIsZero) {
    renderChartMessage(
      salesChart,
      "Aún no hay ventas registradas. Las tiendas envían sus ventas por lotes; " +
        "la primera compra puede tardar hasta un minuto en aparecer aquí."
    );
    return;
  }

  renderBarChart(
    salesChart,
    rows.map((row) => ({
      label: row.store_name,
      sublabel: `${row.invoice_count} factura(s)`,
      value: Number(row.total),
      valueText: formatCurrency(row.total),
      className: `bar-${row.store_id}`,
    }))
  );
}

/** Chart 2: the ten best-selling products, chain-wide or for one store. */
async function loadTopProducts() {
  const storeId = storeFilter.value;
  const query = storeId ? `?store_id=${encodeURIComponent(storeId)}` : "";
  const rows = await fetchJson(`/reports/top-products${query}`);

  if (!rows.length) {
    if (storeId) {
      const name = storeNames.get(storeId) || storeId;
      renderChartMessage(
        productsChart,
        `${name} aún no tiene ventas registradas.`
      );
    } else {
      renderChartMessage(productsChart, "Aún no hay ventas registradas.");
    }
    return;
  }

  renderBarChart(
    productsChart,
    rows.map((row) => ({
      label: row.product_name,
      sublabel: formatCurrency(row.revenue),
      value: Number(row.units_sold),
      valueText: formatUnits(row.units_sold),
    }))
  );
}

/** Whether the charts have ever been drawn with real data. */
let hasRendered = false;

function stampUpdatedNow() {
  const time = new Date().toLocaleTimeString("es-CO", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
  updatedLabel.textContent = `Actualizado ${time}`;
}

/**
 * Reload everything.
 *
 * On failure the behaviour depends on whether anything is on screen yet:
 *
 * - Nothing drawn yet — say plainly that the data could not be fetched, and
 *   put that in the chart areas too.
 * - Charts already showing — KEEP them and warn discreetly. This runs on a
 *   timer, so a single failed poll is a blip; wiping a working dashboard over
 *   one dropped request would be worse than showing data a few seconds stale.
 */
async function loadAll() {
  try {
    await loadStores();
    await Promise.all([loadSalesByStore(), loadTopProducts()]);
    hasRendered = true;
    clearMessage();
    stampUpdatedNow();
  } catch (error) {
    if (hasRendered) {
      showMessage(
        "No se pudo contactar la central en la última actualización; " +
          "los datos mostrados pueden estar desactualizados.",
        "info"
      );
      return;
    }

    // Two blank chart areas with no explanation is the worst possible answer
    // to "the central API is down".
    showMessage(
      "No se pudieron obtener los datos de la central. Verifique que el " +
        "servicio esté arriba e intente de nuevo.",
      "error"
    );
    renderChartMessage(salesChart, "Sin datos.");
    renderChartMessage(productsChart, "Sin datos.");
    updatedLabel.textContent = "";
  }
}

/**
 * Changing the filter redraws ONLY the products chart.
 *
 * The store comparison always shows every store: filtering it to one store
 * would leave a comparison with nothing to compare against.
 */
storeFilter.addEventListener("change", async () => {
  try {
    await loadTopProducts();
    clearMessage();
  } catch (error) {
    showMessage("No se pudo actualizar el top de productos.", "error");
  }
});

refreshButton.addEventListener("click", loadAll);

// --- Keeping the dashboard live ------------------------------------------
//
// A dashboard that only loads once is not a dashboard: a sale rung up while
// the page sits open would never appear, and the figures would quietly go
// stale with nothing on screen admitting it.
//
// The poll is deliberately faster than the stores' batching cadence, so the
// delay a reader actually sees is the forwarding delay (up to about a minute)
// and not this interval on top of it. The two requests are small aggregate
// queries; at classroom volume this costs nothing.
const REFRESH_INTERVAL_MS = 10000;

let refreshTimer = null;

function startAutoRefresh() {
  if (refreshTimer === null) {
    refreshTimer = window.setInterval(loadAll, REFRESH_INTERVAL_MS);
  }
}

function stopAutoRefresh() {
  if (refreshTimer !== null) {
    window.clearInterval(refreshTimer);
    refreshTimer = null;
  }
}

// Stop polling while the tab is in the background — nobody is reading it, and
// a forgotten tab should not keep asking the central API for reports. Coming
// back refreshes immediately, so the first thing you see is current rather
// than up to ten seconds old.
document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopAutoRefresh();
  } else {
    loadAll();
    startAutoRefresh();
  }
});

loadAll();
startAutoRefresh();
