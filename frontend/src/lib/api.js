import axios from "axios";
import { LOCALES, DEFAULT_LOCALE } from "../i18n/locales";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
export const API = `${BACKEND_URL}/api`;

export const currentLocale = () => {
  if (typeof window === "undefined") return DEFAULT_LOCALE;
  const seg = window.location.pathname.split("/")[1];
  return LOCALES.includes(seg) ? seg : DEFAULT_LOCALE;
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
export const img = (url, w = 600) =>
  url && url.startsWith("/api/files/") ? `${url}${url.includes("?") ? "&" : "?"}w=${w}` : url;

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

const FIELD_BG = {
  full_name: "име и фамилия", phone: "телефон", email: "имейл", line1: "адрес",
  city: "град", postal_code: "пощенски код", country: "държава",
  customer_email: "имейл", customer_name: "име и фамилия", customer_phone: "телефон",
};

export const formatErr = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Възникна грешка";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) {
    const fields = [...new Set(d.map((x) => {
      const loc = Array.isArray(x?.loc) ? x.loc[x.loc.length - 1] : "";
      return FIELD_BG[loc] || loc;
    }).filter(Boolean))];
    if (fields.length) return `Моля, попълнете: ${fields.join(", ")}`;
    return d.map((x) => x?.msg || JSON.stringify(x)).join(" • ");
  }
  return String(d);
};
