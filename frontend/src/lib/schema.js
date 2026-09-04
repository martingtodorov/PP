/** Shared JSON-LD builders (schema.org) — Organization, WebSite, Breadcrumbs, Product, Article, FAQ. */

import { siteMedia, shippingInfo } from "./media";
import { currencyCode, nicePrice } from "./money";
import { currentLocale } from "./api";
import { translate } from "../i18n/locales";

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
  description: settings.tagline || translate(currentLocale(), "brandDesc"),
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
  // a ListItem without a name is invalid — titles can still be loading when the crumb is built
  itemListElement: items
    .filter((it) => (it.name || "").trim())
    .map((it, i) => ({
      "@type": "ListItem",
      position: i + 1,
      name: it.name.trim(),
      ...(it.path ? { item: `${ORIGIN()}${it.path}` } : {}),
    })),
});

/* Google's merchant listings require the return policy and the delivery terms inside every offer. */
const merchantTerms = () => {
  const s = shippingInfo();
  if (!s) return {};
  const country = s.country || "BG";
  return {
    hasMerchantReturnPolicy: {
      "@type": "MerchantReturnPolicy",
      applicableCountry: country,
      returnPolicyCountry: country,
      returnPolicyCategory: "https://schema.org/MerchantReturnFiniteReturnWindow",
      merchantReturnDays: s.return_days || 14,
      returnMethod: "https://schema.org/ReturnByMail",
      returnFees: "https://schema.org/ReturnShippingFees",
    },
    ...(typeof s.price === "number" ? {
      shippingDetails: {
        "@type": "OfferShippingDetails",
        shippingRate: { "@type": "MonetaryAmount", value: s.price, currency: s.currency || "EUR" },
        shippingDestination: { "@type": "DefinedRegion", addressCountry: country },
        deliveryTime: {
          "@type": "ShippingDeliveryTime",
          handlingTime: {
            "@type": "QuantitativeValue", unitCode: "DAY",
            minValue: (s.handling_days || [1, 3])[0], maxValue: (s.handling_days || [1, 3])[1],
          },
          transitTime: {
            "@type": "QuantitativeValue", unitCode: "DAY",
            minValue: (s.transit_days || [1, 3])[0], maxValue: (s.transit_days || [1, 3])[1],
          },
        },
      },
    } : {}),
  };
};

export const productLd = ({ product, variant, path }) => {
  const strip = (html) => (html || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const variants = product.variants || [];
  /* the storefront currency: EUR, or the local one on the CZ/HU/PL/RO shops */
  const cur = currencyCode();
  const amount = (eur) => (cur === "EUR" ? eur : nicePrice(eur));
  const prices = variants.map((v) => v.price_eur).filter((n) => typeof n === "number").map(amount);
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
            priceCurrency: cur,
            lowPrice: Math.min(...prices),
            highPrice: Math.max(...prices),
            offerCount: variants.length,
            availability: inStock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
            url: `${ORIGIN()}${path}`,
            ...merchantTerms(),
            offers: variants.map((v) => ({
              "@type": "Offer",
              name: v.name,
              sku: v.sku,
              price: amount(v.price_eur),
              priceCurrency: cur,
              availability: (v.stock || 0) > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
              url: `${ORIGIN()}${path}`,
              itemCondition: "https://schema.org/NewCondition",
              seller: { "@id": ORG_ID() },
              ...merchantTerms(),
            })),
          }
        : {
            "@type": "Offer",
            price: prices[0] || 0,
            priceCurrency: cur,
            availability: inStock ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
            url: `${ORIGIN()}${path}`,
            itemCondition: "https://schema.org/NewCondition",
            seller: { "@id": ORG_ID() },
            ...merchantTerms(),
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
