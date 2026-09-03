/* Warms up everything the accelerated checkout needs while the cart drawer is open,
   so the modal renders instantly instead of firing 4-5 requests on mount. */
import { api, currentLocale } from "./api";
import { countryForLocale } from "../i18n/locales";

export const STORE_KEY = "pp_checkout_v1";
const NINETY_DAYS = 90 * 24 * 60 * 60 * 1000;

export const loadSaved = () => {
  try {
    const raw = JSON.parse(window.localStorage.getItem(STORE_KEY) || "null");
    if (raw && raw.saved_at && Date.now() - raw.saved_at < NINETY_DAYS) return raw;
  } catch (e) { /* ignore */ }
  return null;
};

export const saveCheckout = (data) => {
  try {
    window.localStorage.setItem(STORE_KEY, JSON.stringify({ ...data, saved_at: Date.now() }));
    document.cookie = `pp_checkout_seen=1;max-age=${NINETY_DAYS / 1000};path=/;SameSite=Lax`;
  } catch (e) { /* ignore */ }
};

const cache = {};
const TTL = 5 * 60 * 1000;
const once = (key, fn) => {
  const hit = cache[key];
  if (hit && Date.now() - hit.at < TTL) return hit.p;
  const p = fn().catch((e) => { delete cache[key]; throw e; });
  cache[key] = { p, at: Date.now() };
  return p;
};

export const pfBank = () => once("bank", () => api.get("/bank-details").then((r) => r.data));
export const pfCountries = () => once("countries", () => api.get("/nextcart/countries").then((r) => r.data));
export const pfGeo = () => once("geo", () => api.get("/geo/country").then((r) => r.data));

/* The IP only tells us the country, so the city (which orders the courier offices) comes from the
   device position, reverse-geocoded into the local spelling the courier database uses. */
const DEVICE_KEY = "pp_geo_device_v1";
const DEVICE_TTL = 30 * 60 * 1000;

const readDevice = () => {
  try {
    const d = JSON.parse(window.localStorage.getItem(DEVICE_KEY) || "null");
    if (d && Date.now() - d.at < DEVICE_TTL) return d.geo;
  } catch (e) { /* ignore */ }
  return null;
};

export const pfDeviceGeo = async ({ prompt = false } = {}) => {
  const cached = readDevice();
  if (cached) return cached;
  if (!navigator.geolocation) throw new Error("geolocation-unavailable");
  if (!window.isSecureContext) throw new Error("geolocation-insecure");
  const st = navigator.permissions?.query
    ? await navigator.permissions.query({ name: "geolocation" }).catch(() => null) : null;
  if (!prompt) {
    // warm-up only: reuse an already granted permission, never open the browser dialog
    if (!st || st.state !== "granted") throw new Error("geolocation-not-granted");
  }
  // inside a cross-origin iframe (e.g. a preview panel) the browser refuses silently — no dialog ever shows
  if (st?.state !== "granted" && window.self !== window.top) throw new Error("geolocation-framed");
  if (st?.state === "denied") {
    const e = new Error("geolocation-denied");
    e.code = 1;
    e.remembered = true;
    throw e;
  }
  const pos = await new Promise((res, rej) => navigator.geolocation.getCurrentPosition(res, rej, {
    enableHighAccuracy: false, timeout: 12000, maximumAge: 5 * 60 * 1000,
  }));
  const { data } = await api.get("/geo/reverse", {
    params: { lat: pos.coords.latitude, lon: pos.coords.longitude },
  });
  try {
    window.localStorage.setItem(DEVICE_KEY, JSON.stringify({ at: Date.now(), geo: data }));
  } catch (e) { /* ignore */ }
  return data;
};

export const pfConfig = (country) =>
  once(`cfg:${country}`, () =>
    api.get("/nextcart/config", { params: { country } }).then((r) => r.data));

export const pfPickups = (providerKey, destinationType, country) =>
  once(`pk:${providerKey}:${destinationType}:${country}`, () =>
    api.get("/nextcart/pickups", {
      params: { provider_key: providerKey, destination_type: destinationType, country },
    }).then((r) => r.data));

/** Fire-and-forget warm-up: countries, bank, geo, courier config and the default pickup list. */
export const prefetchCheckout = async () => {
  pfBank();
  pfCountries();
  const saved = loadSaved();
  let country = saved?.contact?.country || countryForLocale(currentLocale());
  if (!country) {
    try {
      const [geo, list] = await Promise.all([pfGeo(), pfCountries()]);
      const supported = (list.countries || []).some((c) => c.iso2 === geo.country);
      country = supported ? geo.country : (list.default || "BG");
    } catch (e) {
      country = "BG";
    }
  } else {
    pfGeo();
  }
  try {
    const cfg = await pfConfig(country);
    const list = cfg.delivery_methods || [];
    const def = list.find((m) => m.key === saved?.methodKey) || list.find((m) => m.is_default) || list[0];
    if (def && def.destination_type !== "address") {
      pfPickups(def.provider_key, def.destination_type, country);
    }
  } catch (e) { /* the modal will surface the error */ }
};
