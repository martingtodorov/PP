/* Google Analytics 4 (gtag.js).
   The measurement ID comes from the shop settings (admin panel), never from the build, so the
   owner can change it without a deploy. One ID may serve every storefront, or each domain can
   have its own — see settings.ga4_ids.
   GA loads only after the visitor accepted analytics cookies (Consent Mode v2 defaults to denied). */

const CONSENT_KEY = "pp_cookie_consent_v1";
let loadedId = null;
let pending = null; // page_view waiting for the consent/ID to arrive

export const hasAnalyticsConsent = () => {
  try {
    const raw = window.localStorage.getItem(CONSENT_KEY);
    return Boolean(raw && JSON.parse(raw).analytics);
  } catch {
    return false;
  }
};

const queue = () => {
  window.dataLayer = window.dataLayer || [];
  if (!window.gtag) window.gtag = function gtag() { window.dataLayer.push(arguments); };
  return window.gtag;
};

/** Consent Mode v2 defaults — must run before any config/event command. */
export const initConsentDefaults = () => {
  const gtag = queue();
  gtag("consent", "default", {
    analytics_storage: "denied",
    ad_storage: "denied",
    ad_user_data: "denied",
    ad_personalization: "denied",
    wait_for_update: 500,
  });
};

export const updateConsent = (prefs) => {
  const gtag = queue();
  const ads = Boolean(prefs?.marketing);
  gtag("consent", "update", {
    analytics_storage: prefs?.analytics ? "granted" : "denied",
    ad_storage: ads ? "granted" : "denied",
    ad_user_data: ads ? "granted" : "denied",
    ad_personalization: ads ? "granted" : "denied",
  });
};

/** The ID of this storefront: a per-domain override wins, otherwise the shop-wide one. */
export const measurementId = (settings, locale) => {
  const perLocale = (settings?.ga4_ids || {})[locale];
  const id = String(perLocale || settings?.ga4_measurement_id || "").trim();
  return /^G-[A-Z0-9]+$/i.test(id) ? id : "";
};

export const loadGa = (id) => {
  if (!id || loadedId || typeof document === "undefined") return;
  const gtag = queue();
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${encodeURIComponent(id)}`;
  document.head.appendChild(s);
  gtag("js", new Date());
  // the router sends exactly one page_view per route — automatic ones would double-count
  gtag("config", id, { send_page_view: false });
  loadedId = id;
  if (pending) {
    const p = pending;
    pending = null;
    pageView(p);
  }
};

export const pageView = (path) => {
  if (!loadedId || !hasAnalyticsConsent()) {
    pending = path;
    return;
  }
  queue()("event", "page_view", {
    page_location: window.location.origin + path,
    page_path: path,
    page_title: document.title,
  });
};

const send = (name, params) => {
  if (!loadedId || !hasAnalyticsConsent()) return;
  queue()("event", name, params);
};

const lineItem = (x, quantity) => ({
  item_id: String(x.variant_sku || x.sku || x.product_handle || x.handle || ""),
  item_name: x.title || x.name || "",
  item_variant: x.variant_name || undefined,
  price: Number(x.price_eur || x.price || 0),
  quantity: quantity || x.quantity || 1,
});

export const gaViewItem = (product, variant) => send("view_item", {
  currency: "EUR",
  value: Number(variant?.price_eur || 0),
  items: [lineItem({ ...product, ...variant, product_handle: product?.handle }, 1)],
});

export const gaAddToCart = (product, variant, quantity = 1) => send("add_to_cart", {
  currency: "EUR",
  value: Number(variant?.price_eur || 0) * quantity,
  items: [lineItem({ ...product, ...variant, product_handle: product?.handle }, quantity)],
});

export const gaBeginCheckout = (items, total) => send("begin_checkout", {
  currency: "EUR",
  value: Number(total || 0),
  items: (items || []).map((x) => lineItem(x)),
});

/** Sent once per order: a refresh of the thank-you page must not duplicate the revenue. */
export const gaPurchase = (order) => {
  if (!order?.order_number) return;
  const key = `pp_ga_purchase_${order.order_number}`;
  try {
    if (window.sessionStorage.getItem(key)) return;
    window.sessionStorage.setItem(key, "1");
  } catch { /* private mode: send it anyway, GA dedupes on transaction_id */ }
  send("purchase", {
    transaction_id: String(order.order_number),
    currency: "EUR",
    value: Number(order.total_eur || 0),
    shipping: Number(order.shipping_eur || 0),
    coupon: order.discount_code || undefined,
    items: (order.items || []).map((x) => lineItem(x)),
  });
};
