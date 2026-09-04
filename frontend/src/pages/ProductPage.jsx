import { useEffect, useRef, useState } from "react";
import { link } from "../lib/links";
import { useParams, Link } from "react-router-dom";
import { Truck, Minus, Plus, ShieldCheck, Droplets } from "lucide-react";
import { toast } from "sonner";
import Layout, { USPRow } from "../components/Layout";
import NotFoundBlock from "../components/NotFoundBlock";
import ProductsCarousel from "../components/ProductsCarousel";
import Breadcrumbs from "../components/Breadcrumbs";
import StickyBuyBar from "../components/StickyBuyBar";
import { api, fmtPrice, fmtBGN, showsBGN, img } from "../lib/api";
import { useCart } from "../context/CartContext";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { PRODUCT_BLOCKS, pick, LOCALES } from "../i18n/locales";
import { useSeo } from "../lib/seo";
import { graph, productLd, breadcrumbLd, organizationLd } from "../lib/schema";
import { isAllCollection } from "../lib/collections";

/** Size token of a variant name, e.g. "5 mg" -> "5mg" */
const sizeToken = (name) => (name || "").toLowerCase().replace(/\s+/g, "");

/** Which variant sizes does this image filename mention? ("bpc-157br5mg10mg" mentions both) */
const tokensInUrl = (url, tokens) => {
  const flat = decodeURIComponent(url || "").toLowerCase().replace(/[^a-z0-9]/g, "");
  return tokens.filter((tok) => {
    const i = flat.indexOf(tok);
    return i >= 0 && !/[0-9]/.test(flat[i - 1] || "");
  });
};

/**
 * Gallery for the selected variant: its own photos first, then the shared ones
 * (lab tests / COA / photos that mention every size), never the other variants' designs.
 */
export const variantGallery = (images, variants, index) => {
  if (!variants || variants.length < 2) return images;
  const own = variants[index]?.image;
  if (own) {
    const others = variants.filter((_, i) => i !== index).map((v) => v.image).filter(Boolean);
    const rest = images.filter((u) => u !== own && !others.includes(u));
    return [own, ...rest];
  }
  const tokens = variants.map((v) => sizeToken(v.name)).filter(Boolean);
  const current = tokens[index];
  if (!current || tokens.length < 2) return images;
  const mine = [];
  const shared = [];
  images.forEach((url) => {
    const hits = tokensInUrl(url, tokens);
    if (hits.length === 1) {
      if (hits[0] === current) mine.push(url);
    } else {
      shared.push(url);
    }
  });
  const gallery = [...mine, ...shared];
  return gallery.length ? gallery : images;
};

export default function ProductPage() {
  const { handle } = useParams();
  const [data, setData] = useState({ product: null, related: [], collections: [], articles: [] });
  const [gone, setGone] = useState(false);
  const [variantIdx, setVariantIdx] = useState(0);
  const [imgIdx, setImgIdx] = useState(0);
  const ctaRef = useRef(null);
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    setVariantIdx(0);
    setImgIdx(0);
    setQty(1);
    setGone(false);
    api.get(`/products/${handle}`).then(({ data }) => setData(data)).catch(() => setGone(true));
  }, [handle, locale]);

  const p = data.product;
  const v = p?.variants?.[variantIdx];
  const alternates = {};
  if (p?.handles) LOCALES.forEach((l) => { alternates[l] = `/products/${p.handles[l]}`; });

  useSeo({
    title: p ? (p.seo_title || `${p.title} | PurePeptide`) : "PurePeptide",
    description: p
      ? p.seo_description || (p.description || "").replace(/<[^>]+>/g, "").slice(0, 155)
      : "",
    ogType: "product",
    locale,
    path: `/products/${handle}`,
    alternates,
    image: p?.image,
    jsonLd: p && graph(
      productLd({ product: p, variant: v, path: `/products/${handle}` }),
      breadcrumbLd([
        { name: t("home"), path: "/" },
        { name: t("allPeptides"), path: link("catalog") },
        { name: p.title, path: `/products/${handle}` },
      ]),
      organizationLd(),
    ),
  });

  if (gone) return <Layout><NotFoundBlock /></Layout>;

  /* Skeleton mirrors the real layout AND reserves the full page height, so nothing that is visible
     in the viewport moves when the product arrives (CLS) */
  if (!p) return (
    <Layout>
      <div key="product-skeleton" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-12 min-h-[3200px]"
        data-testid="product-skeleton" aria-busy="true">
        <div className="pp-skel pp-skel-block h-3 w-56" />
        <div className="pp-skel pp-skel-block h-3 w-40 mt-2 sm:hidden" />
        <div className="grid lg:grid-cols-2 gap-5 lg:gap-14 mt-4 lg:items-start">
          <div className="min-w-0">
            <div className="pp-skel aspect-square w-full rounded-xl" />
            <div className="flex gap-2 mt-2">
              {Array.from({ length: 4 }).map((_, i) => <div key={i} className="pp-skel h-16 w-16 rounded-lg" />)}
            </div>
          </div>
          <div className="space-y-5">
            <div className="pp-skel pp-skel-block h-9 w-3/4" />
            <div className="pp-skel pp-skel-block h-4 w-52" />
            <div className="pp-skel pp-skel-block h-4 w-44" />
            <div className="pp-skel pp-skel-block h-8 w-40" />
            <div className="flex gap-2">
              {Array.from({ length: 3 }).map((_, i) => <div key={i} className="pp-skel h-11 flex-1 rounded-md" />)}
            </div>
            <div className="flex gap-3">
              <div className="pp-skel h-12 w-32 rounded-md" />
              <div className="pp-skel h-12 flex-1 rounded-md" />
            </div>
            <div className="pp-skel pp-skel-block h-28 w-full" />
            {Array.from({ length: 6 }).map((_, i) => <div key={i} className="pp-skel pp-skel-block h-12 w-full" />)}
            <div className="pp-skel pp-skel-block h-96 w-full" />
          </div>
        </div>
      </div>
    </Layout>
  );

  const allImages = p.images?.length ? p.images : [p.image];
  const images = variantGallery(allImages, p.variants || [], variantIdx);
  const out = !v || (v.stock || 0) <= 0;
  const primaryCollection = (data.collections || []).find(
    (c) => !isAllCollection(c) && c.title !== t("catalog") && !c.nav_hidden,
  );
  const specs = p.specs || {};

  return (
    <Layout>
      <div key="product-content" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-12">
        <Breadcrumbs
          items={[
            { label: t("catalog"), to: lp(link("catalog")) },
            ...(primaryCollection ? [{ label: primaryCollection.title, to: lp(`/collections/${primaryCollection.handle}`) }] : []),
            { label: p.title },
          ]}
        />

        <div className="grid lg:grid-cols-[1.15fr_1fr] gap-5 lg:gap-12 mt-0 lg:items-start">
          {/* Gallery — sticks while the text on the right scrolls (desktop) */}
          <div className="min-w-0 lg:sticky lg:top-24 lg:self-start" data-testid="product-gallery">
            <div className="aspect-square w-full max-w-full bg-white rounded-xl overflow-hidden">
              <img src={img(images[imgIdx], 1200)} alt={p.title} className="w-full h-full object-contain" data-testid="product-main-image" />
            </div>
            {images.length > 1 && (
              <div className="pp-thumbs -mx-4 px-4 sm:mx-0 sm:px-0 mt-1 sm:mt-1.5" data-testid="product-thumbs">
                {images.map((src, i) => (
                  <button key={i} onClick={() => setImgIdx(i)}
                    className={`pp-thumb${i === imgIdx ? " pp-thumb--active" : ""}`}
                    aria-label={`Image ${i + 1}`} data-testid={`product-thumb-${i}`}>
                    <img src={img(src, 160)} alt="" className="w-full h-full object-contain px-1.5 py-0" loading="lazy" decoding="async" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Purchase panel */}
          <div className="space-y-5">
            {/* like purepeptide.bg: the body's "Какво е X?" is the H1, the product name an H2 */}
            {/<h1[\s>]/i.test(p.description || "") ? (
              <h2 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight py-1.5" data-testid="product-title">
                {p.title}
              </h2>
            ) : (
              <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight py-1.5" data-testid="product-title">
                {p.title}
              </h1>
            )}
            {p.subtitle && <p className="text-sm text-slate-500 -mt-3">{p.subtitle}</p>}

            <div className="space-y-1.5 text-sm text-slate-700">
              <p className="flex items-center gap-2"><Truck className="h-4 w-4 text-coral-600" /> {t("fastShipping")}</p>
              <p className="flex items-center gap-2 font-semibold"><Droplets className="h-4 w-4 text-coral-600" /> {t("withWater")}</p>
            </div>

            <div className="text-2xl font-bold text-slate-900 flex flex-wrap items-baseline gap-2" data-testid="product-price">
              <span>{fmtPrice(v?.price_eur || 0)}</span>
              {(v?.compare_at_eur || 0) > (v?.price_eur || 0) && (
                <>
                  <s className="text-lg font-normal text-slate-400" data-testid="product-compare-price">{fmtPrice(v.compare_at_eur)}</s>
                  <span className="text-xs font-bold uppercase tracking-wide bg-coral-600 text-white rounded-md px-2 py-1" data-testid="product-sale-badge">
                    −{Math.round(((v.compare_at_eur - v.price_eur) / v.compare_at_eur) * 100)}%
                  </span>
                </>
              )}
              {showsBGN() && <span className="text-base font-normal text-slate-500">({fmtBGN(v?.price_eur || 0)})</span>}
            </div>

            {p.variants.length > 0 && (
              <div>
                <p className="text-sm text-slate-600 mb-2">{t("package")}:</p>
                <div className="pp-variants" data-testid="variant-selector">
                  {p.variants.map((va, i) => (
                    <button key={va.sku || va.name} type="button" onClick={() => { setVariantIdx(i); setImgIdx(0); }}
                      className={`pp-variant${i === variantIdx ? " pp-variant--active" : ""}${(va.stock || 0) <= 0 ? " pp-variant--out" : ""}`}
                      data-testid={`variant-${va.sku || va.name}`}>
                      {va.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {v?.sku && (
              <p className="text-xs text-slate-500" data-testid="product-sku">
                SKU: <span className="font-mono text-slate-700">{v.sku}</span>
              </p>
            )}

            <div className="flex items-stretch gap-3 pt-1.5 pb-1" ref={ctaRef}>
              <div className="flex items-center border border-slate-300 rounded-md">
                <button onClick={() => setQty(Math.max(1, qty - 1))} className="px-3 py-2.5 text-slate-600" aria-label="-"><Minus className="h-4 w-4" /></button>
                <span className="w-10 text-center text-sm font-medium" data-testid="qty-value">{qty}</span>
                <button onClick={() => setQty(qty + 1)} className="px-3 py-2.5 text-slate-600" aria-label="+"><Plus className="h-4 w-4" /></button>
              </div>
              <button type="button" disabled={out}
                className="flex-1 bg-coral-600 hover:bg-coral-700 disabled:bg-slate-300 text-white font-semibold rounded-md px-6 py-3 transition-colors"
                onClick={() => { add(p, v, qty); toast.success(t("addToCart"), { description: `${p.title} × ${qty}` }); }}
                data-testid="add-to-cart-btn">
                {out ? t("soldOut") : t("addToCart")}
              </button>
            </div>

            {/* Specs */}
            {(specs.cas || specs.formula) && (
              <dl className="grid grid-cols-2 gap-x-4 gap-y-2 text-sm bg-slate-50 border border-slate-200 rounded-lg p-4" data-testid="product-specs">
                {specs.cas && (<><dt className="text-slate-500">{t("cas")}</dt><dd className="text-slate-900 font-medium">{specs.cas}</dd></>)}
                {specs.formula && (<><dt className="text-slate-500">{t("formula")}</dt><dd className="text-slate-900 font-medium break-all">{specs.formula}</dd></>)}
                {specs.mw && (<><dt className="text-slate-500">{t("mw")}</dt><dd className="text-slate-900 font-medium">{specs.mw}</dd></>)}
                {specs.purity && (<><dt className="text-slate-500">{t("purity")}</dt><dd className="text-slate-900 font-medium">{specs.purity}</dd></>)}
              </dl>
            )}

            {/* Shared accordions */}
            <div className="pp-acc" data-testid="product-accordions">
              {pick(PRODUCT_BLOCKS, locale).map((b, i) => (
                <details key={b.title} className="pp-acc__row" open={i === 0}>
                  <summary>{b.title}</summary>
                  <div className="pp-acc__body pp-rte" dangerouslySetInnerHTML={{ __html: b.html }} />
                </details>
              ))}
            </div>

            <p className="text-xs text-slate-500 leading-relaxed flex gap-2">
              <ShieldCheck className="h-4 w-4 text-slate-400 flex-shrink-0" />
              {t("disclaimer")}
            </p>

            {/* Long description — in the right column under the buy panel, like purepeptide.bg */}
            {p.description && (
              <section className="pt-6 border-t border-slate-200">
                <div className="pp-rte" dangerouslySetInnerHTML={{ __html: p.description }} data-testid="product-description" />
              </section>
            )}
          </div>
        </div>

        {/* Internal linking: collections this product belongs to */}
        {data.collections?.length > 0 && (
          <section className="mt-12">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-3">{t("alsoBrowse")}</p>
            <div className="flex flex-wrap gap-2" data-testid="product-collection-links">
              {data.collections.map((c) => (
                <Link key={c.handle} to={lp(`/collections/${c.handle}`)}
                  className="px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-coral-600 hover:text-coral-700 transition-colors">
                  {c.title}
                </Link>
              ))}
              <Link to={lp(link("catalog"))}
                className="px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-coral-600 hover:text-coral-700 transition-colors">
                {t("catalog")}
              </Link>
            </div>
          </section>
        )}

        {/* Related articles */}
        {data.articles?.length > 0 && (
          <section className="mt-10">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-3">{t("articles")}</p>
            <ul className="space-y-2" data-testid="product-article-links">
              {data.articles.map((a) => (
                <li key={a.handle}>
                  <Link to={lp(`/articles/${a.handle}`)} className="text-sm text-slate-800 hover:text-coral-600 underline-offset-4 hover:underline">
                    {a.title}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {/* Related products */}
        {data.related.length > 0 && (
          <section className="mt-14">
            <h2 className="text-xl sm:text-2xl font-semibold text-slate-900 mb-6">{t("relatedProducts")}</h2>
            <ProductsCarousel products={data.related} />
          </section>
        )}
      </div>
      <USPRow />
      <StickyBuyBar
        product={p}
        variant={v}
        anchorRef={ctaRef}
        soldOut={out}
        onAdd={() => { add(p, v, qty); toast.success(t("addToCart"), { description: `${p.title} × ${qty}` }); }}
      />
    </Layout>
  );
}
