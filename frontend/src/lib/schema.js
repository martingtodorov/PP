/** Shared JSON-LD builders (schema.org) — Organization, WebSite, Breadcrumbs, Product, Article, FAQ. */

import { siteMedia } from "./media";

const ORIGIN = () => (typeof window !== "undefined" ? window.location.origin : "https://purepeptide.bg");
const asset = (key, fallback) => {
  const url = siteMedia(key, fallback);
  return url.startsWith("http") ? url : `${ORIGIN()}${url}`;
};

export const ORG_ID = () => `${ORIGIN()}/#organization`;
export const SITE_ID = () => `${ORIGIN()}/#website`;

export const organizationLd = (settings = {}) => ({
  "@type": "Organization",
  "@id": ORG_ID(),
  name: settings.site_name || "PurePeptide",
  url: `${ORIGIN()}/`,
  logo: { "@type": "ImageObject", url: asset("icon", "/favicon-512.png"), width: 512, height: 512 },
  image: asset("og", "/og-image.jpg"),
  email: settings.contact_email || "contact@purepeptide.bg",
  description:
    settings.tagline ||
    "Лиофилизирани изследователски пептиди с чистота над 99%, потвърдена от независима лаборатория.",
});

export const websiteLd = (locale = "bg") => ({
  "@type": "WebSite",
  "@id": SITE_ID(),
  url: `${ORIGIN()}/`,
  name: "PurePeptide",
  inLanguage: locale,
  publisher: { "@id": ORG_ID() },
  potentialAction: {
    "@type": "SearchAction",
    target: { "@type": "EntryPoint", urlTemplate: `${ORIGIN()}/search?q={search_term_string}` },
    "query-input": "required name=search_term_string",
  },
});

export const breadcrumbLd = (items = []) => ({
  "@type": "BreadcrumbList",
  itemListElement: items.map((it, i) => ({
    "@type": "ListItem",
    position: i + 1,
    name: it.name,
    ...(it.path ? { item: `${ORIGIN()}${it.path}` } : {}),
  })),
});

export const productLd = ({ product, variant, path }) => {
  const strip = (html) => (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const variants = product.variants || [];
  const prices = variants.map((v) => v.price_eur).filter((n) => typeof n === "number");
  const inStock = variants.some((v) => (v.stock || 0) > 0);
  return {
    "@type": "Product",
    "@id": `${ORIGIN()}${path}#product`,
    name: product.title,
    url: `${ORIGIN()}${path}`,
    image: (product.images && product.images.length ? product.images : [product.image]).map((src) =>
      src && src.startsWith("/") ? `${ORIGIN()}${src}` : src
    ),
    description: product.seo_description || strip(product.description).slice(0, 500),
    sku: variant?.sku || variants[0]?.sku,
    mpn: variant?.sku || variants[0]?.sku,
    brand: { "@type": "Brand", name: "PurePeptide" },
    category: "Research peptides",
    ...(product.specs?.cas ? { additionalProperty: [{ "@type": "PropertyValue", name: "CAS", value: product.specs.cas }] } : {}),
    offers:
      variants.length > 1
        ? {
            "@type": "AggregateOffer",
            priceCurrency: "EUR",
            lowPrice: Math.min(...prices),
            highPrice: Math.max(...prices),
            offerCount: variants.length,
            availability: inStock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
            url: `${ORIGIN()}${path}`,
            offers: variants.map((v) => ({
              "@type": "Offer",
              name: v.name,
              sku: v.sku,
              price: v.price_eur,
              priceCurrency: "EUR",
              availability: (v.stock || 0) > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
              url: `${ORIGIN()}${path}`,
            })),
          }
        : {
            "@type": "Offer",
            price: prices[0] || 0,
            priceCurrency: "EUR",
            availability: inStock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
            url: `${ORIGIN()}${path}`,
            itemCondition: "https://schema.org/NewCondition",
            seller: { "@id": ORG_ID() },
          },
  };
};

export const itemListLd = (products = [], pathFor) => ({
  "@type": "ItemList",
  numberOfItems: products.length,
  itemListElement: products.slice(0, 30).map((p, i) => ({
    "@type": "ListItem",
    position: i + 1,
    url: `${ORIGIN()}${pathFor(p)}`,
    name: p.title,
  })),
});

export const faqLd = (items = []) => ({
  "@type": "FAQPage",
  mainEntity: items.map((f) => ({
    "@type": "Question",
    name: f.q,
    acceptedAnswer: { "@type": "Answer", text: f.a },
  })),
});

export const articleLd = ({ article, path }) => ({
  "@type": "BlogPosting",
  "@id": `${ORIGIN()}${path}#article`,
  headline: article.title,
  description: article.seo_description || article.excerpt,
  image: article.image && article.image.startsWith("/") ? `${ORIGIN()}${article.image}` : article.image,
  datePublished: article.published_at,
  dateModified: article.updated_at || article.published_at,
  author: article.author
    ? { "@type": "Person", name: article.author }
    : { "@id": ORG_ID() },
  publisher: { "@id": ORG_ID() },
  mainEntityOfPage: { "@type": "WebPage", "@id": `${ORIGIN()}${path}` },
  inLanguage: "bg",
});

export const graph = (...nodes) => ({
  "@context": "https://schema.org",
  "@graph": nodes.flat().filter(Boolean),
});
