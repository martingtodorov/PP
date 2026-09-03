import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LOCALES, DEFAULT_LOCALE, LOCALE_META, translate, applyLocaleRoutes, applyUiOverrides, isProdHost, localeFromHost } from "./locales";
import { api, setFx } from "../lib/api";
import { setLinks } from "../lib/links";

const LocaleContext = createContext({ locale: DEFAULT_LOCALE });

export const localeFromPath = (pathname) => {
  const seg = (pathname || "/").split("/")[1];
  return LOCALES.includes(seg) && seg !== DEFAULT_LOCALE ? seg : DEFAULT_LOCALE;
};

export function LocaleProvider({ children }) {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const [routesVersion, setRoutesVersion] = useState(0);
  const host = typeof window !== "undefined" ? window.location.host : "";
  /* purepeptide.gr / .ro / .bg serve one language from their root — the domain decides there,
     the URL prefix only matters on the shared purepeptide.eu (and in the preview pod). */
  const hostLocale = useMemo(() => localeFromHost(host), [host, routesVersion]);
  const pathLocale = localeFromPath(pathname);
  const locale = pathLocale !== DEFAULT_LOCALE ? pathLocale : (hostLocale || DEFAULT_LOCALE);

  /* admin-configurable domains / prefixes / homepage paths */
  useEffect(() => {
    api.get("/locales").then(({ data }) => {
      applyLocaleRoutes(data.routes);
      setRoutesVersion((v) => v + 1);
    }).catch(() => {});
    api.get("/ui-strings").then(({ data }) => {
      applyUiOverrides(data.strings);
      setRoutesVersion((v) => v + 1);
    }).catch(() => {});
  }, []);

  /* the storefront currency (EUR, or the local one for CZ/HU/PL/RO) with today's ECB rate */
  useEffect(() => {
    api.get("/currency", { params: { locale } })
      .then(({ data }) => { setFx(data); setRoutesVersion((v) => v + 1); })
      .catch(() => {});
    api.get("/links", { params: { locale } })
      .then(({ data }) => { setLinks(data); setRoutesVersion((v) => v + 1); })
      .catch(() => {});
  }, [locale]);

  /* one language per domain: purepeptide.eu serves English under /en, purepeptide.gr / .ro serve
     their language from the root, and a foreign prefix jumps to the domain that owns it */
  useEffect(() => {
    const seg = pathname.split("/")[1];
    if (host.includes("purepeptide.eu") && !LOCALES.includes(seg)) {
      nav(`/en${pathname === "/" ? "" : pathname}`, { replace: true });
      return;
    }
    if (!hostLocale) return;
    const rest = LOCALES.includes(seg) ? (pathname.slice(seg.length + 1) || "/") : null;
    if (rest === null) return;
    if (seg === hostLocale) {
      nav(rest, { replace: true });                       // /gr/... on purepeptide.gr -> /...
    } else if (isProdHost(host)) {
      const meta = LOCALE_META[seg];
      window.location.replace(`${meta.origin}${meta.prefix}${rest === "/" ? "" : rest}`);
    }
  }, [pathname, hostLocale, host, nav]);

  const value = useMemo(() => {
    const rootLocale = hostLocale || DEFAULT_LOCALE;
    const prefix = locale === rootLocale ? "" : `/${locale}`;
    /* locale-prefixed internal link */
    const lp = (path = "/") => {
      const clean = path.startsWith("/") ? path : `/${path}`;
      return prefix + (clean === "/" ? "/" : clean);
    };
    /* absolute URL for another locale (cross-domain in production, prefix in preview) */
    const localeUrl = (target, path = "/") => {
      const meta = LOCALE_META[target];
      const onProdDomain = isProdHost(host);
      const p = path.startsWith("/") ? path : `/${path}`;
      if (onProdDomain) return `${meta.origin}${meta.prefix}${p === "/" ? "" : p}`;
      const localPrefix = target === rootLocale ? "" : `/${target}`;
      return `${localPrefix}${p === "/" ? "/" : p}`;
    };
    /* strip the locale prefix from the current path -> canonical path */
    const basePath = prefix ? (pathname.slice(prefix.length) || "/") : pathname;

    const homePath = LOCALE_META[locale]?.home_path || "/";
    return { locale, prefix, lp, localeUrl, basePath, homePath, t: (k, vars) => translate(locale, k, vars) };
  }, [locale, hostLocale, host, pathname, routesVersion]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export const useLocaleCtx = () => useContext(LocaleContext);
