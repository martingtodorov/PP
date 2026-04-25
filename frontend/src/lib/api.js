import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

// EUR -> BGN conversion (peg)
export const FX = 1.95583;
export const fmtEUR = (n) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "EUR" }).format(Number(n) || 0);
export const fmtBGN = (eur) =>
  new Intl.NumberFormat("bg-BG", { style: "currency", currency: "BGN" }).format((Number(eur) || 0) * FX);

export const formatErr = (e) => {
  const d = e?.response?.data?.detail;
  if (!d) return e?.message || "Възникна грешка";
  if (typeof d === "string") return d;
  if (Array.isArray(d)) return d.map((x) => x?.msg || JSON.stringify(x)).join(" • ");
  return String(d);
};
