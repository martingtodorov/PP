import { useEffect } from "react";
import { LOCALES, LOCALE_META, DEFAULT_LOCALE } from "../i18n/locales";

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
export function useSeo({ title, description, locale = DEFAULT_LOCALE, path = "/", alternates = {}, jsonLd, image }) {
  useEffect(() => {
    const full = title ? `${title}` : "PurePeptide";
    document.title = full;
    document.documentElement.lang = LOCALE_META[locale]?.hreflang || locale;
    setMeta("name", "description", description);
    setMeta("property", "og:title", full);
    setMeta("property", "og:description", description);
    setMeta("property", "og:type", "website");
    if (image) setMeta("property", "og:image", image);
    setMeta("name", "twitter:card", "summary_large_image");

    const onProd = window.location.host.includes("purepeptide.");
    const abs = (loc, p) => {
      const meta = LOCALE_META[loc];
      if (onProd) return `${meta.origin}${meta.prefix}${p === "/" ? "" : p}`;
      const prefix = loc === DEFAULT_LOCALE ? "" : `/${loc}`;
      return `${window.location.origin}${prefix}${p === "/" ? "/" : p}`;
    };

    setLink("canonical", abs(locale, alternates[locale] || path));
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
  }, [title, description, locale, path, JSON.stringify(alternates), JSON.stringify(jsonLd), image]);
}
