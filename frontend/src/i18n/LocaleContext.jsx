import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { LOCALES, DEFAULT_LOCALE, LOCALE_META, translate, applyLocaleRoutes } from "./locales";
import { api } from "../lib/api";

const LocaleContext = createContext({ locale: DEFAULT_LOCALE });

export const localeFromPath = (pathname) => {
  const seg = (pathname || "/").split("/")[1];
  return LOCALES.includes(seg) && seg !== DEFAULT_LOCALE ? seg : DEFAULT_LOCALE;
};

export function LocaleProvider({ children }) {
  const { pathname } = useLocation();
  const nav = useNavigate();
  const [routesVersion, setRoutesVersion] = useState(0);
  const locale = localeFromPath(pathname);

  /* admin-configurable domains / prefixes / homepage paths */
  useEffect(() => {
    api.get("/locales").then(({ data }) => {
      applyLocaleRoutes(data.routes);
      setRoutesVersion((v) => v + 1);
    }).catch(() => {});
  }, []);

  /* the .eu apex is unused — English lives under /en */
  useEffect(() => {
    const host = window.location.host;
    const seg = pathname.split("/")[1];
    if (host.includes("purepeptide.eu") && !LOCALES.includes(seg)) {
      nav(`/en${pathname === "/" ? "" : pathname}`, { replace: true });
    }
  }, [pathname, nav]);

  const value = useMemo(() => {
    const prefix = locale === DEFAULT_LOCALE ? "" : `/${locale}`;
    /* locale-prefixed internal link */
    const lp = (path = "/") => {
      const clean = path.startsWith("/") ? path : `/${path}`;
      return prefix + (clean === "/" ? "/" : clean);
    };
    /* absolute URL for another locale (cross-domain in production, prefix in preview) */
    const localeUrl = (target, path = "/") => {
      const meta = LOCALE_META[target];
      const host = typeof window !== "undefined" ? window.location.host : "";
      const onProdDomain = host.includes("purepeptide.");
      const p = path.startsWith("/") ? path : `/${path}`;
      if (onProdDomain) return `${meta.origin}${meta.prefix}${p === "/" ? "" : p}`;
      const localPrefix = target === DEFAULT_LOCALE ? "" : `/${target}`;
      return `${localPrefix}${p === "/" ? "/" : p}`;
    };
    /* strip the locale prefix from the current path -> canonical path */
    const basePath = (() => {
      if (locale === DEFAULT_LOCALE) return pathname;
      return pathname.slice(`/${locale}`.length) || "/";
    })();

    const homePath = LOCALE_META[locale]?.home_path || "/";
    return { locale, prefix, lp, localeUrl, basePath, homePath, t: (k) => translate(locale, k) };
  }, [locale, pathname, routesVersion]);

  return <LocaleContext.Provider value={value}>{children}</LocaleContext.Provider>;
}

export const useLocaleCtx = () => useContext(LocaleContext);
