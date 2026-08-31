import axios from "axios";
import { LOCALES, DEFAULT_LOCALE } from "../i18n/locales";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
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
export const fmtEUR = (n) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "EUR" }).format(Number(n) || 0);
export const fmtBGN = (eur) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "BGN" }).format((Number(eur) || 0) * FX);

/* BGN is only shown on the Bulgarian storefront (dual-pricing requirement) */
export const showsBGN = () => currentLocale() === "bg";

export const formatErr = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Възникна грешка";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" • ");
  return String(d);
};
