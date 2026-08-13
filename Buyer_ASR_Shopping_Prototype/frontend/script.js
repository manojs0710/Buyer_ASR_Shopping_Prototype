/* =====================================================================
   Buyer App — Frontend Application Logic
   Vanilla JS. Talks to the FastAPI backend at /api/*.
   Voice recording captures raw PCM via the Web Audio API and encodes a
   16kHz mono WAV client-side, so the backend can read it exactly the way
   the notebook reads WAV files with soundfile - no ffmpeg required.
   ===================================================================== */

const API_BASE = "";

// ---------------------------------------------------------------------
// Icon mapping (emoji stand-ins for product art)
// ---------------------------------------------------------------------
const PRODUCT_ICONS = {
  tomato: "🍅", potato: "🥔", onion: "🧅", carrot: "🥕", cabbage: "🥬",
  beans: "🫘", brinjal: "🍆", cucumber: "🥒", spinach: "🥬",
  apple: "🍎", banana: "🍌", orange: "🍊", mango: "🥭", grapes: "🍇", watermelon: "🍉",
  milk: "🥛", curd: "🥣", butter: "🧈", cheese: "🧀", paneer: "🧀",
  coriander: "🌿", mint: "🌿", curry_leaves: "🌿",
  rice: "🍚", wheat_flour: "🌾", sugar: "🧂", salt: "🧂", dal: "🫘", cooking_oil: "🛢️",
  water: "💧", juice: "🧃", tea: "🍵",
};
function iconFor(productId) { return PRODUCT_ICONS[productId] || "🛒"; }

// ---------------------------------------------------------------------
// App state
// ---------------------------------------------------------------------
const state = {
  allProducts: [],
  categories: [],
  activeCategory: "All",
  qtyDraft: {},   // product_id -> pending quantity for the stepper before Add
};

function money(n) { return "₹" + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 }); }

// ---------------------------------------------------------------------
// Toasts
// ---------------------------------------------------------------------
const toastContainer = document.getElementById("toast-container");
function showToast(message, type = "default") {
  const el = document.createElement("div");
  el.className = `toast ${type === "success" ? "toast-success" : type === "error" ? "toast-error" : ""}`;
  el.textContent = message;
  toastContainer.appendChild(el);
  setTimeout(() => el.remove(), 3200);
}

// ---------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------
async function api(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = "Request failed.";
    try { detail = (await res.json()).detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return res.json();
}

// ---------------------------------------------------------------------
// CATALOG
// ---------------------------------------------------------------------
const productGrid = document.getElementById("product-grid");
const categoryNav = document.getElementById("category-nav");
const catalogTitle = document.getElementById("catalog-title");
const catalogCount = document.getElementById("catalog-count");
const emptyState = document.getElementById("empty-state");
const emptyStateText = document.getElementById("empty-state-text");

async function loadCatalog() {
  try {
    const data = await api("/api/products");
    state.allProducts = data.products;
    state.categories = data.categories;
    renderCategoryNav();
    renderProducts(state.allProducts);
  } catch (err) {
    showToast("Backend unavailable. Please make sure the server is running.", "error");
    console.error(err);
  }
}

function renderCategoryNav() {
  categoryNav.innerHTML = "";
  const all = document.createElement("button");
  all.className = "category-pill active";
  all.dataset.category = "All";
  all.textContent = "All";
  all.addEventListener("click", () => selectCategory("All"));
  categoryNav.appendChild(all);

  state.categories.forEach((cat) => {
    const btn = document.createElement("button");
    btn.className = "category-pill";
    btn.dataset.category = cat;
    btn.textContent = cat;
    btn.addEventListener("click", () => selectCategory(cat));
    categoryNav.appendChild(btn);
  });
}

function selectCategory(category) {
  state.activeCategory = category;
  searchInput.value = "";
  searchClearBtn.hidden = true;

  categoryNav.querySelectorAll(".category-pill").forEach((el) => {
    el.classList.toggle("active", el.dataset.category === category);
  });

  const filtered = category === "All"
    ? state.allProducts
    : state.allProducts.filter((p) => p.category === category);

  catalogTitle.textContent = category === "All" ? "All Products" : category;
  renderProducts(filtered);
}

function renderProducts(products) {
  catalogCount.textContent = `${products.length} item${products.length === 1 ? "" : "s"}`;
  productGrid.innerHTML = "";

  if (products.length === 0) {
    emptyState.hidden = false;
    emptyStateText.textContent = "Try a different search term or category.";
    return;
  }
  emptyState.hidden = true;

  products.forEach((p) => {
    if (!(p.id in state.qtyDraft)) state.qtyDraft[p.id] = 1;

    const card = document.createElement("div");
    card.className = "product-card";
    card.innerHTML = `
      <div class="product-card-top">
        <div class="product-icon">${iconFor(p.id)}</div>
        <span class="stock-tag ${p.available ? "stock-yes" : "stock-no"}">${p.available ? "In Stock" : "Out of Stock"}</span>
      </div>
      <div class="product-name">${p.name}</div>
      <div class="product-meta">${p.category}</div>
      <div class="product-price-row">
        <span class="product-price mono">${money(p.price)}</span>
        <span class="product-unit">/ ${p.unit}</span>
      </div>
      <div class="qty-stepper">
        <button type="button" class="qty-minus" aria-label="Decrease quantity">−</button>
        <span class="qty-value">${state.qtyDraft[p.id]}</span>
        <button type="button" class="qty-plus" aria-label="Increase quantity">+</button>
      </div>
      <button type="button" class="add-btn" ${p.available ? "" : "disabled"}>
        ${p.available ? "Add to Cart" : "Unavailable"}
      </button>
    `;

    const qtyValueEl = card.querySelector(".qty-value");
    card.querySelector(".qty-minus").addEventListener("click", () => {
      state.qtyDraft[p.id] = Math.max(1, state.qtyDraft[p.id] - 1);
      qtyValueEl.textContent = state.qtyDraft[p.id];
    });
    card.querySelector(".qty-plus").addEventListener("click", () => {
      state.qtyDraft[p.id] = Math.min(99, state.qtyDraft[p.id] + 1);
      qtyValueEl.textContent = state.qtyDraft[p.id];
    });
    card.querySelector(".add-btn").addEventListener("click", async () => {
      await addToCart(p.id, state.qtyDraft[p.id]);
      state.qtyDraft[p.id] = 1;
      qtyValueEl.textContent = 1;
    });

    productGrid.appendChild(card);
  });
}

// ---------------------------------------------------------------------
// SEARCH
// ---------------------------------------------------------------------
const searchInput = document.getElementById("search-input");
const searchClearBtn = document.getElementById("search-clear");
let searchDebounce = null;

searchInput.addEventListener("input", () => {
  const query = searchInput.value.trim();
  searchClearBtn.hidden = query.length === 0;

  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(async () => {
    if (!query) {
      catalogTitle.textContent = state.activeCategory === "All" ? "All Products" : state.activeCategory;
      const filtered = state.activeCategory === "All"
        ? state.allProducts
        : state.allProducts.filter((p) => p.category === state.activeCategory);
      renderProducts(filtered);
      return;
    }
    try {
      const data = await api("/api/search", { method: "POST", body: JSON.stringify({ query }) });
      catalogTitle.textContent = `Results for "${query}"`;
      categoryNav.querySelectorAll(".category-pill").forEach((el) => el.classList.remove("active"));
      emptyStateText.textContent = `No products match "${query}".`;
      renderProducts(data.products);
    } catch (err) {
      showToast("Search failed. Please try again.", "error");
      console.error(err);
    }
  }, 220);
});

searchClearBtn.addEventListener("click", () => {
  searchInput.value = "";
  searchClearBtn.hidden = true;
  searchInput.dispatchEvent(new Event("input"));
});

// ---------------------------------------------------------------------
// CART
// ---------------------------------------------------------------------
const cartBtn = document.getElementById("cart-btn");
const cartBadge = document.getElementById("cart-badge");
const cartOverlay = document.getElementById("cart-overlay");
const cartPanel = document.getElementById("cart-panel");
const cartCloseBtn = document.getElementById("cart-close");
const cartItemsEl = document.getElementById("cart-items");
const cartEmptyEl = document.getElementById("cart-empty");
const cartFooterEl = document.getElementById("cart-footer");
const cartSubtotalEl = document.getElementById("cart-subtotal");
const cartTotalEl = document.getElementById("cart-total");
const cartClearBtn = document.getElementById("cart-clear-btn");
const cartCheckoutBtn = document.getElementById("cart-checkout-btn");

function openCart() {
  cartOverlay.hidden = false;
  cartPanel.classList.add("open");
  refreshCart();
}
function closeCart() {
  cartPanel.classList.remove("open");
  setTimeout(() => { cartOverlay.hidden = true; }, 300);
}
cartBtn.addEventListener("click", openCart);
cartCloseBtn.addEventListener("click", closeCart);
cartOverlay.addEventListener("click", closeCart);

async function refreshCart() {
  try {
    const cart = await api("/api/cart");
    renderCart(cart);
    return cart;
  } catch (err) {
    showToast("Couldn't load your cart.", "error");
    console.error(err);
  }
}

function renderCart(cart) {
  cartBadge.hidden = cart.count === 0;
  cartBadge.textContent = cart.count;

  cartItemsEl.innerHTML = "";
  if (cart.items.length === 0) {
    cartEmptyEl.hidden = false;
    cartFooterEl.style.display = "none";
    return;
  }
  cartEmptyEl.hidden = true;
  cartFooterEl.style.display = "block";

  cart.items.forEach((item) => {
    const row = document.createElement("div");
    row.className = "cart-item";
    row.innerHTML = `
      <div class="cart-item-icon">${iconFor(item.product_id)}</div>
      <div class="cart-item-info">
        <div class="cart-item-name">${item.name}</div>
        <div class="cart-item-price mono">${money(item.price)} / ${item.unit}</div>
        <button type="button" class="cart-item-remove">Remove</button>
      </div>
      <div class="cart-item-controls">
        <div class="cart-item-total mono">${money(item.line_total)}</div>
        <div class="cart-item-qty">
          <button type="button" class="cart-qty-minus" aria-label="Decrease">−</button>
          <span>${item.quantity}</span>
          <button type="button" class="cart-qty-plus" aria-label="Increase">+</button>
        </div>
      </div>
    `;
    row.querySelector(".cart-qty-minus").addEventListener("click", () =>
      updateCartQuantity(item.product_id, item.quantity - 1));
    row.querySelector(".cart-qty-plus").addEventListener("click", () =>
      updateCartQuantity(item.product_id, item.quantity + 1));
    row.querySelector(".cart-item-remove").addEventListener("click", () =>
      removeCartItem(item.product_id));
    cartItemsEl.appendChild(row);
  });

  cartSubtotalEl.textContent = money(cart.subtotal);
  cartTotalEl.textContent = money(cart.total);
}

async function addToCart(productId, quantity) {
  try {
    const cart = await api("/api/cart/add", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity }),
    });
    renderCart(cart);
    const product = state.allProducts.find((p) => p.id === productId);
    showToast(`Added ${quantity} × ${product ? product.name : productId}`, "success");
  } catch (err) {
    showToast(err.message || "Couldn't add item to cart.", "error");
  }
}

async function updateCartQuantity(productId, quantity) {
  try {
    const cart = await api("/api/cart/update", {
      method: "POST",
      body: JSON.stringify({ product_id: productId, quantity }),
    });
    renderCart(cart);
  } catch (err) {
    showToast(err.message || "Couldn't update quantity.", "error");
  }
}

async function removeCartItem(productId) {
  try {
    const cart = await api(`/api/cart/${productId}`, { method: "DELETE" });
    renderCart(cart);
    showToast("Item removed.", "default");
  } catch (err) {
    showToast("Couldn't remove item.", "error");
  }
}

cartClearBtn.addEventListener("click", async () => {
  try {
    const cart = await api("/api/cart", { method: "DELETE" });
    renderCart(cart);
    showToast("Cart cleared.", "default");
  } catch (err) {
    showToast("Couldn't clear cart.", "error");
  }
});

cartCheckoutBtn.addEventListener("click", async () => {
  const cart = await refreshCart();
  if (!cart || cart.items.length === 0) {
    showToast("Your cart is empty.", "error");
    return;
  }
  showToast("Demo checkout — order ready for confirmation.", "success");
  setTimeout(async () => {
    const cleared = await api("/api/cart", { method: "DELETE" });
    renderCart(cleared);
    closeCart();
  }, 1400);
});

// =======================================================================
// VOICE SHOPPING
// =======================================================================
const micBtn = document.getElementById("mic-btn");
const voiceOverlay = document.getElementById("voice-modal-overlay");
const voiceCloseBtn = document.getElementById("voice-modal-close");

const voiceStates = {
  idle: document.getElementById("voice-state-idle"),
  recording: document.getElementById("voice-state-recording"),
  processing: document.getElementById("voice-state-processing"),
  result: document.getElementById("voice-state-result"),
  error: document.getElementById("voice-state-error"),
};
function showVoiceState(name) {
  Object.entries(voiceStates).forEach(([key, el]) => { el.hidden = key !== name; });
}

const startBtn = document.getElementById("voice-start-btn");
const stopBtn = document.getElementById("voice-stop-btn");
const cancelBtn = document.getElementById("voice-cancel-btn");
const againBtn = document.getElementById("voice-again-btn");
const doneBtn = document.getElementById("voice-done-btn");
const retryBtn = document.getElementById("voice-retry-btn");
const recTimerEl = document.getElementById("rec-timer");
const voiceErrorText = document.getElementById("voice-error-text");
const youSaidText = document.getElementById("you-said-text");
const resultItemsEl = document.getElementById("result-items");
const resultErrorsEl = document.getElementById("result-errors");
const resultIcon = document.getElementById("result-icon");

let mediaStream = null;
let audioContext = null;
let sourceNode = null;
let processorNode = null;
let recordedChunks = [];
let recTimerInterval = null;
let recSeconds = 0;

function openVoiceModal() {
  voiceOverlay.hidden = false;
  showVoiceState("idle");
}
function closeVoiceModal() {
  stopMediaTracks();
  showVoiceState("idle");
  voiceOverlay.hidden = true;
}
micBtn.addEventListener("click", openVoiceModal);
voiceCloseBtn.addEventListener("click", closeVoiceModal);
cancelBtn.addEventListener("click", closeVoiceModal);
retryBtn.addEventListener("click", () => showVoiceState("idle"));
againBtn.addEventListener("click", () => showVoiceState("idle"));
doneBtn.addEventListener("click", closeVoiceModal);

function stopMediaTracks() {
  if (processorNode) { processorNode.disconnect(); processorNode = null; }
  if (sourceNode) { sourceNode.disconnect(); sourceNode = null; }
  if (mediaStream) { mediaStream.getTracks().forEach((t) => t.stop()); mediaStream = null; }
  if (audioContext) { audioContext.close().catch(() => {}); audioContext = null; }
  clearInterval(recTimerInterval);
}

// --- Recording: raw PCM capture via Web Audio API -----------------------
startBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecordingAndSend);

async function startRecording() {
  try {
    mediaStream = await navigator.mediaDevices.getUserMedia({ audio: true });
  } catch (err) {
    voiceErrorText.textContent =
      "Microphone permission was denied. Please allow microphone access and try again.";
    showVoiceState("error");
    return;
  }

  audioContext = new (window.AudioContext || window.webkitAudioContext)();
  sourceNode = audioContext.createMediaStreamSource(mediaStream);
  processorNode = audioContext.createScriptProcessor(4096, 1, 1);
  recordedChunks = [];

  processorNode.onaudioprocess = (e) => {
    const channelData = e.inputBuffer.getChannelData(0);
    recordedChunks.push(new Float32Array(channelData)); // copy - buffer is reused by the browser
  };

  // A muted gain node keeps the processor firing in browsers that require
  // a path to destination, without the user hearing their own mic.
  const muteGain = audioContext.createGain();
  muteGain.gain.value = 0;
  sourceNode.connect(processorNode);
  processorNode.connect(muteGain);
  muteGain.connect(audioContext.destination);

  recSeconds = 0;
  recTimerEl.textContent = "00:00";
  recTimerInterval = setInterval(() => {
    recSeconds += 1;
    const m = String(Math.floor(recSeconds / 60)).padStart(2, "0");
    const s = String(recSeconds % 60).padStart(2, "0");
    recTimerEl.textContent = `${m}:${s}`;
    if (recSeconds >= 15) stopRecordingAndSend(); // safety cap for the demo
  }, 1000);

  showVoiceState("recording");
}

async function stopRecordingAndSend() {
  if (!audioContext) return;
  const nativeSampleRate = audioContext.sampleRate;
  const merged = mergeFloat32(recordedChunks);
  stopMediaTracks();

  if (merged.length === 0) {
    voiceErrorText.textContent = "No audio was captured. Please try recording again.";
    showVoiceState("error");
    return;
  }

  showVoiceState("processing");
  document.getElementById("processing-label").textContent = "Understanding your voice…";

  const downsampled = downsampleBuffer(merged, nativeSampleRate, 16000);
  const wavBlob = encodeWAV(downsampled, 16000);

  const formData = new FormData();
  formData.append("audio", wavBlob, "voice-command.wav");

  try {
    const res = await fetch(`${API_BASE}/api/voice-command`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      voiceErrorText.textContent = err.detail || "Sorry, I couldn't understand the audio. Please try again.";
      showVoiceState("error");
      return;
    }
    const data = await res.json();
    renderVoiceResult(data);
    renderCart(data.cart);
  } catch (err) {
    voiceErrorText.textContent = "Backend unavailable. Please make sure the server is running.";
    showVoiceState("error");
    console.error(err);
  }
}

function renderVoiceResult(data) {
  youSaidText.textContent = `"${data.transcription}"`;
  resultIcon.textContent = data.success ? "✅" : "⚠️";

  resultItemsEl.innerHTML = "";
  data.items_added.forEach((item) => {
    const row = document.createElement("div");
    row.className = "result-item-row";
    row.textContent = `✓ Added ${item.quantity} ${item.product}${item.quantity > 1 ? "s" : ""}`;
    resultItemsEl.appendChild(row);
  });

  if (data.errors && data.errors.length > 0) {
    resultErrorsEl.hidden = false;
    resultErrorsEl.innerHTML = "";
    data.errors.forEach((msg) => {
      const row = document.createElement("div");
      row.className = "result-error-row";
      row.textContent = msg;
      resultErrorsEl.appendChild(row);
    });
  } else {
    resultErrorsEl.hidden = true;
  }

  showVoiceState("result");
}

// --- Audio helpers: merge, downsample, WAV-encode ------------------------
function mergeFloat32(chunks) {
  let total = 0;
  for (const c of chunks) total += c.length;
  const out = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) { out.set(c, offset); offset += c.length; }
  return out;
}

function downsampleBuffer(buffer, inputSampleRate, targetSampleRate) {
  if (targetSampleRate === inputSampleRate) return buffer;
  const ratio = inputSampleRate / targetSampleRate;
  const newLength = Math.round(buffer.length / ratio);
  const result = new Float32Array(newLength);
  let offsetResult = 0;
  let offsetBuffer = 0;
  while (offsetResult < newLength) {
    const nextOffsetBuffer = Math.round((offsetResult + 1) * ratio);
    let accum = 0, count = 0;
    for (let i = offsetBuffer; i < nextOffsetBuffer && i < buffer.length; i++) {
      accum += buffer[i];
      count++;
    }
    result[offsetResult] = count > 0 ? accum / count : 0;
    offsetResult++;
    offsetBuffer = nextOffsetBuffer;
  }
  return result;
}

function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  function writeString(offset, str) {
    for (let i = 0; i < str.length; i++) view.setUint8(offset + i, str.charCodeAt(i));
  }

  writeString(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(8, "WAVE");
  writeString(12, "fmt ");
  view.setUint32(16, 16, true);          // PCM chunk size
  view.setUint16(20, 1, true);           // audio format = PCM
  view.setUint16(22, 1, true);           // mono
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * 2, true); // byte rate
  view.setUint16(32, 2, true);           // block align
  view.setUint16(34, 16, true);          // bits per sample
  writeString(36, "data");
  view.setUint32(40, samples.length * 2, true);

  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }

  return new Blob([view], { type: "audio/wav" });
}

// ---------------------------------------------------------------------
// Init
// ---------------------------------------------------------------------
loadCatalog();
refreshCart();
