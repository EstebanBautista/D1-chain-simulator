/*
 * Point of sale logic.
 *
 * Code and comments are in English; every string the cashier sees is Spanish.
 *
 * The cart lives in memory here only to show the cashier what she is ringing
 * up. On payment we send just barcodes and quantities: the backend re-reads
 * prices from the database and charges its own total, so nothing here is
 * trusted as money.
 */

// Nginx proxies /api to the backend container, so the browser stays on one
// origin and the site does not depend on which host port the backend is
// published on. See frontend/nginx.conf.
const API_BASE_URL = "/api";

// Which register this screen belongs to.
//
// It comes from register-config.js, which the register itself serves. So the
// identity is decided by the URL the cashier opened — that is, by the machine
// she walked up to — and not by anything this page could choose. If it is
// missing, the site was reached without going through a register.
const REGISTER_ID = window.REGISTER_ID || null;

// Which store this register belongs to. Same source, same reasoning: the page
// cannot claim to be a store it is not. With both stores open side by side,
// this is what keeps two otherwise identical screens apart.
const STORE_ID = window.STORE_ID || null;
const STORE_NAME = window.STORE_NAME || null;

const CURRENCY_FORMATTER = new Intl.NumberFormat("es-CO", {
  style: "currency",
  currency: "COP",
  maximumFractionDigits: 0,
});

/** @type {{ean: string, name: string, quantity: number, unitPrice: number, subtotal: number}[]} */
let cart = [];

const scanForm = document.getElementById("scan-form");
const eanInput = document.getElementById("ean-input");
const quantityInput = document.getElementById("quantity-input");
const payButton = document.getElementById("pay-button");
const cartBody = document.getElementById("cart-body");
const cartTotal = document.getElementById("cart-total");
const message = document.getElementById("message");
const registerLabel = document.getElementById("register-label");
const storeLabel = document.getElementById("store-label");

function formatCurrency(value) {
  return CURRENCY_FORMATTER.format(value);
}

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

function calculateTotal() {
  return cart.reduce((sum, item) => sum + item.subtotal, 0);
}

function renderCart() {
  cartBody.innerHTML = "";

  if (cart.length === 0) {
    const row = document.createElement("tr");
    row.innerHTML =
      '<td colspan="5" class="empty-cart">La compra está vacía</td>';
    cartBody.appendChild(row);
  } else {
    cart.forEach((item, index) => {
      const row = document.createElement("tr");

      const nameCell = document.createElement("td");
      nameCell.textContent = item.name;

      const quantityCell = document.createElement("td");
      quantityCell.className = "numeric";
      quantityCell.textContent = String(item.quantity);

      const unitPriceCell = document.createElement("td");
      unitPriceCell.className = "numeric";
      unitPriceCell.textContent = formatCurrency(item.unitPrice);

      const subtotalCell = document.createElement("td");
      subtotalCell.className = "numeric";
      subtotalCell.textContent = formatCurrency(item.subtotal);

      const actionCell = document.createElement("td");
      const removeButton = document.createElement("button");
      removeButton.type = "button";
      removeButton.className = "remove-button";
      removeButton.textContent = "Quitar";
      removeButton.addEventListener("click", () => removeItem(index));
      actionCell.appendChild(removeButton);

      row.append(nameCell, quantityCell, unitPriceCell, subtotalCell, actionCell);
      cartBody.appendChild(row);
    });
  }

  // Recomputed from the cart on every render, so the figure can never drift
  // away from the list above it.
  cartTotal.textContent = formatCurrency(calculateTotal());
}

function removeItem(index) {
  cart.splice(index, 1);
  renderCart();
}

function addItemToCart(product, quantity) {
  const unitPrice = Number(product.price);
  const existing = cart.find((item) => item.ean === product.ean);

  if (existing) {
    existing.quantity += quantity;
    existing.subtotal = existing.unitPrice * existing.quantity;
  } else {
    cart.push({
      ean: product.ean,
      name: product.name,
      quantity: quantity,
      unitPrice: unitPrice,
      subtotal: unitPrice * quantity,
    });
  }

  renderCart();
}

async function lookUpProduct(ean) {
  const response = await fetch(`${API_BASE_URL}/products/${encodeURIComponent(ean)}`);

  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(`Product lookup failed with status ${response.status}`);
  }

  return response.json();
}

async function handleScan(event) {
  event.preventDefault();
  clearMessage();

  const ean = eanInput.value.trim();
  const quantity = Number.parseInt(quantityInput.value, 10);

  if (!ean) {
    showMessage("Ingrese un código de barras", "error");
    return;
  }
  if (!Number.isInteger(quantity) || quantity <= 0) {
    showMessage("La cantidad debe ser un número entero mayor a cero", "error");
    return;
  }

  try {
    const product = await lookUpProduct(ean);

    if (product === null) {
      showMessage(`No se encontró ningún producto con el código ${ean}`, "error");
      return;
    }

    addItemToCart(product, quantity);
    showMessage(`Se agregó ${product.name}`, "success");
  } catch (error) {
    console.error(error);
    showMessage("No se pudo consultar el producto. Intente de nuevo.", "error");
  } finally {
    // Reset for the next scan without making the cashier reach for the mouse.
    eanInput.value = "";
    quantityInput.value = "1";
    eanInput.focus();
  }
}

async function handlePayment() {
  clearMessage();

  if (REGISTER_ID === null) {
    showMessage(
      "No se puede cobrar sin una caja registradora identificada.",
      "error"
    );
    return;
  }

  if (cart.length === 0) {
    showMessage("La compra está vacía. Agregue productos antes de pagar.", "error");
    return;
  }

  payButton.disabled = true;

  try {
    const response = await fetch(`${API_BASE_URL}/payments`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        register_id: REGISTER_ID,
        items: cart.map((item) => ({ ean: item.ean, quantity: item.quantity })),
      }),
    });

    const result = await response.json();

    if (!response.ok) {
      // 400 carries a validation problem, 503 an unreachable gateway. Either
      // way the cart is kept so the cashier can retry.
      const detail = result.detail || "No se pudo procesar el pago";
      showMessage(detail, "error");
      return;
    }

    if (result.status === "APPROVED") {
      showMessage(
        `Pago aprobado por ${formatCurrency(Number(result.total))}. Venta número ${result.sale_id}.`,
        "success"
      );
      cart = [];
      renderCart();
    } else {
      showMessage(
        `Pago rechazado${result.decline_reason ? `: ${result.decline_reason}` : ""}. La compra se conserva.`,
        "error"
      );
    }
  } catch (error) {
    console.error(error);
    showMessage("No se pudo contactar el servidor. Intente de nuevo.", "error");
  } finally {
    payButton.disabled = false;
    eanInput.focus();
  }
}

function start() {
  if (REGISTER_ID === null) {
    // Reached without going through a register. There is no register to
    // attribute a sale to, so selling is not possible from here.
    registerLabel.textContent = "sin caja identificada";
    storeLabel.textContent = "";
    payButton.disabled = true;
    showMessage(
      "Esta pantalla no está asociada a ninguna caja registradora. " +
        "Abra el sitio desde la URL de una caja.",
      "error"
    );
  } else {
    registerLabel.textContent = REGISTER_ID;
    // The store's name in Spanish, so a cashier can tell at a glance which
    // store this screen belongs to without reading the address bar.
    storeLabel.textContent = STORE_NAME || STORE_ID || "";
  }

  scanForm.addEventListener("submit", handleScan);
  payButton.addEventListener("click", handlePayment);
  renderCart();
}

start();
