/* purepeptide.eu has no language of its own: the apex sends the visitor to the version that matches
   his IP country (or to the domain that owns that language), unless he picked a language himself. */
import { LOCALES, DEFAULT_LOCALE, LOCALE_META } from "./locales";

const KEY = "pp_lang_v1";

export const COUNTRY_LOCALE = {
  BG: "bg",
  GR: "gr", CY: "gr",
  RO: "ro", MD: "ro",
  CZ: "cz", HU: "hu", PL: "pl", SK: "sk", SI: "si",
  DE: "de", AT: "de", CH: "de", LI: "de",
  FR: "fr", BE: "fr", LU: "fr", MC: "fr",
};

export const localeForCountry = (country) => COUNTRY_LOCALE[(country || "").toUpperCase()] || "en";

export const rememberLocale = (locale) => {
  try {
    if (LOCALES.includes(locale)) window.localStorage.setItem(KEY, locale);
  } catch (e) { /* private mode */ }
};

export const rememberedLocale = () => {
  try {
    const v = window.localStorage.getItem(KEY);
    return LOCALES.includes(v) ? v : "";
  } catch (e) {
    return "";
  }
};

/** Where a visitor of the shared apex should land: same-domain prefix or another domain. */
export const targetForLocale = (locale, path = "/") => {
  const meta = LOCALE_META[locale] || LOCALE_META[DEFAULT_LOCALE];
  const rest = path === "/" ? "" : path;
  if (meta.prefix) return { internal: `${meta.prefix}${rest || ""}` || "/" };
  return { external: `${meta.origin}${rest}` };
};
