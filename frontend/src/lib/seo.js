import { useEffect } from "react";
import { LOCALES, LOCALE_META, DEFAULT_LOCALE, isProdHost, localeFromHost, translate } from "../i18n/locales";
import { siteMedia } from "./media";

const setMeta = (attr, key, content) => {
  let el = document.head.querySelector(`meta[${attr}="${key}"]`);
  if (!el) {
    el = document.createElement("meta");
    el.setAttribute(attr, key);
    document.head.appendChild(el);
  }
  el.setAttribute("content", content || "");
};

const setLink = (rel, href, hreflang) => {
  const selector = hreflang ? `link[rel="${rel}"][hreflang="${hreflang}"]` : `link[rel="${rel}"]`;
  let el = document.head.querySelector(selector);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    if (hreflang) el.setAttribute("hreflang", hreflang);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
};

/**
 * SEO head manager: title, description, canonical, hreflang alternates and JSON-LD.
 * `alternates` maps locale -> path (localised handles), falling back to `path`.
 */
export function useSeo({ title, description, locale = DEFAULT_LOCALE, path = "/", alternates = {}, jsonLd, image, ogType = "website", robots = "index,follow,max-image-preview:large,max-snippet:-1" }) {
  useEffect(() => {
    const full = title ? `${title}` : "PurePeptide";
    document.title = full;
    document.documentElement.lang = LOCALE_META[locale]?.hreflang || locale;
    const skip = document.getElementById("pp-skip");   // ships in index.html before React
    if (skip) skip.textContent = translate(locale, "skipToContent");
    setMeta("name", "description", description);
    setMeta("name", "robots", robots);
    setMeta("property", "og:title", full);
    setMeta("property", "og:description", description);
    setMeta("property", "og:type", ogType);
    setMeta("property", "og:locale", (LOCALE_META[locale]?.hreflang || locale).replace("-", "_"));
    setMeta("name", "twitter:title", full);
    setMeta("name", "twitter:description", description);
    const origin = window.location.origin;
    const rawImage = image || siteMedia("og", "/og-image.jpg");
    const ogImage = rawImage.startsWith("http") ? rawImage : `${origin}${rawImage}`;
    setMeta("property", "og:image", ogImage);
    setMeta("property", "og:site_name", "PurePeptide");
    setMeta("name", "twitter:image", ogImage);
    setMeta("name", "twitter:card", "summary_large_image");

    /* a domain that owns a language (purepeptide.gr/.ro/.bg) gets the configured origins too */
    const rootLocale = localeFromHost(window.location.host);
    const onProd = isProdHost(window.location.host) || !!rootLocale;
    const abs = (loc, p) => {
      const meta = LOCALE_META[loc];
      if (onProd) return `${meta.origin}${meta.prefix}${p === "/" ? "" : p}`;
      const prefix = loc === (rootLocale || DEFAULT_LOCALE) ? "" : `/${loc}`;
      return `${window.location.origin}${prefix}${p === "/" ? "/" : p}`;
    };

    setLink("canonical", abs(locale, alternates[locale] || path));
    setMeta("property", "og:url", abs(locale, alternates[locale] || path));
    document.head.querySelectorAll('link[rel="alternate"][hreflang]').forEach((el) => el.remove());
    LOCALES.forEach((loc) => {
      const el = document.createElement("link");
      el.setAttribute("rel", "alternate");
      el.setAttribute("hreflang", LOCALE_META[loc].hreflang);
      el.setAttribute("href", abs(loc, alternates[loc] || path));
      document.head.appendChild(el);
    });
    const xd = document.createElement("link");
    xd.setAttribute("rel", "alternate");
    xd.setAttribute("hreflang", "x-default");
    xd.setAttribute("href", abs("en", alternates.en || path));
    document.head.appendChild(xd);

    document.querySelectorAll("script[data-pp-jsonld]").forEach((el) => el.remove());
    if (jsonLd) {
      const s = document.createElement("script");
      s.type = "application/ld+json";
      s.setAttribute("data-pp-jsonld", "1");
      s.text = JSON.stringify(jsonLd);
      document.head.appendChild(s);
    }
  }, [title, description, locale, path, ogType, robots, JSON.stringify(alternates), JSON.stringify(jsonLd), image]);
}
