import axios from "axios";
import { LOCALES, DEFAULT_LOCALE, localeFromHost, translate } from "../i18n/locales";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

/* Every request carries the language of the page. purepeptide.gr / .ro serve their language from
   the root, so the domain decides there; on purepeptide.eu the /xx prefix does. */
export const currentLocale = () => {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const seg = window.location.pathname.split("/")[1];
  if (LOCALES.includes(seg)) return seg;
  return localeFromHost(window.location.host) || DEFAULT_LOCALE;
};

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

api.interceptors.request.use((cfg) => {
  cfg.params = { locale: currentLocale(), ...(cfg.params || {}) };
  return cfg;
});

// EUR -> BGN conversion (peg)
export const FX = 1.95583;
/** Ask the API for a resized WebP variant (big win on mobile). */
/**
 * Media revision. nginx used to stamp a one-year "immutable" Cache-Control on 404s too, so every
 * missing image got cached as broken by Cloudflare and by the visitors' browsers. Bumping this
 * changes the cache key and serves the fixed files immediately, without waiting for a purge.
 */
const MEDIA_REV = "2";

export const img = (url, w = 600) =>
  url && url.startsWith("/api/files/")
    ? `${url}${url.includes("?") ? "&" : "?"}w=${w}&v=${MEDIA_REV}`
    : url;

export const fmtEUR = (n) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "EUR" }).format(Number(n) || 0);
/* Orders imported from Shopify can be in RON/BGN/… — show them in their original currency */
export const fmtMoney = (n, currency = "EUR") =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: (currency || "EUR").toUpperCase() })
    .format(Number(n) || 0);
export const fmtBGN = (eur) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "BGN" }).format((Number(eur) || 0) * FX);

/* Local-currency storefronts (CZ/HU/PL/RO) — see lib/money.js */
export { fmtPrice, fmtAmount, amountOf, cartAmounts, convertPlain, setFx, currencyCode, isLocalCurrency, nicePrice } from "./money";

/* BGN is only shown on the Bulgarian storefront (dual-pricing requirement) */
export const showsBGN = () => currentLocale() === "bg";

const FIELD_KEY = {
  full_name: "fldName", phone: "fldPhone", email: "fldEmail", line1: "fldAddress",
  city: "fldCity", postal_code: "fldPostal", country: "fldCountry",
  customer_email: "fldEmail", customer_name: "fldName", customer_phone: "fldPhone",
};
const tr = (key, vars) => translate(currentLocale(), key, vars);

export const formatErr = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || tr("errGeneric");
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const fields = [...new Set(d.map((x) => {
      const loc = Array.isArray(x?.loc) ? x.loc[x.loc.length - 1] : "";
      return FIELD_KEY[loc] ? tr(FIELD_KEY[loc]) : loc;
    }).filter(Boolean))];
    if (fields.length) return tr("errPleaseFill", { fields: fields.join(", ") });
    return d.map((x) => x?.msg || JSON.stringify(x)).join(" • ");
  }
  return String(d);
};
