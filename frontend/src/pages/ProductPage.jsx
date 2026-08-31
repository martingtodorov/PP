import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Truck, Minus, Plus, ShieldCheck, Droplets } from "lucide-react";
import { toast } from "sonner";
import Layout, { USPRow } from "../components/Layout";
import ProductsCarousel from "../components/ProductsCarousel";
import Breadcrumbs from "../components/Breadcrumbs";
import { api, fmtEUR, fmtBGN, showsBGN } from "../lib/api";
import { useCart } from "../context/CartContext";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { PRODUCT_BLOCKS, pick, LOCALES } from "../i18n/locales";
import { useSeo } from "../lib/seo";

export default function ProductPage() {
  const { handle } = useParams();
  const [data, setData] = useState({ product: null, related: [], collections: [], articles: [] });
  const [variantIdx, setVariantIdx] = useState(0);
  const [imgIdx, setImgIdx] = useState(0);
  const [qty, setQty] = useState(1);
  const { add } = useCart();
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    setVariantIdx(0);
    setImgIdx(0);
    setQty(1);
    api.get(`/products/${handle}`).then(({ data }) => setData(data));
  }, [handle, locale]);

  const p = data.product;
  const v = p?.variants?.[variantIdx];
  const alternates = {};
  if (p?.handles) LOCALES.forEach((l) => { alternates[l] = `/products/${p.handles[l]}`; });

  useSeo({
    title: p ? `${p.title} | PurePeptide` : "PurePeptide",
    description: p ? (p.description || "").replace(/<[^>]+>/g, "").slice(0, 155) : "",
    locale,
    path: `/products/${handle}`,
    alternates,
    image: p?.image,
    jsonLd: p && {
      "@context": "https://schema.org",
      "@type": "Product",
      name: p.title,
      image: p.images || [p.image],
      description: (p.description || "").replace(/<[^>]+>/g, "").slice(0, 300),
      sku: v?.sku,
      brand: { "@type": "Brand", name: "PurePeptide" },
      offers: (p.variants || []).map((va) => ({
        "@type": "Offer",
        price: va.price_eur,
        priceCurrency: "EUR",
        availability: (va.stock || 0) > 0 ? "https://schema.org/InStock" : "https://schema.org/OutOfStock",
      })),
    },
  });

  if (!p) return <Layout><div className="max-w-7xl mx-auto px-4 py-20 text-slate-500">{t("loading")}</div></Layout>;

  const images = p.images?.length ? p.images : [p.image];
  const out = !v || (v.stock || 0) <= 0;
  const primaryCollection = data.collections?.[0];
  const specs = p.specs || {};

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-12">
        <Breadcrumbs
          items={[
            { label: t("catalog"), to: lp("/collections/all-peptides") },
            ...(primaryCollection ? [{ label: primaryCollection.title, to: lp(`/collections/${primaryCollection.handle}`) }] : []),
            { label: p.title },
          ]}
        />

        <div className="grid lg:grid-cols-2 gap-10 lg:gap-14 mt-5">
          {/* Gallery */}
          <div>
            <div className="aspect-square bg-white border border-slate-200 rounded-xl overflow-hidden">
              <img src={images[imgIdx]} alt={p.title} className="w-full h-full object-contain p-6" data-testid="product-main-image" />
            </div>
            {images.length > 1 && (
              <div className="flex gap-3 mt-4 overflow-x-auto no-scrollbar">
                {images.map((src, i) => (
                  <button key={i} onClick={() => setImgIdx(i)}
                    className={`w-20 h-20 flex-shrink-0 bg-white border rounded-lg overflow-hidden transition-colors ${i === imgIdx ? "border-coral-600" : "border-slate-200"}`}
                    aria-label={`Image ${i + 1}`} data-testid={`product-thumb-${i}`}>
                    <img src={src} alt="" className="w-full h-full object-contain p-1.5" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Purchase panel */}
          <div className="space-y-5">
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 tracking-tight" data-testid="product-title">
              {p.title}
            </h1>
            {p.subtitle && <p className="text-sm text-slate-500 -mt-3">{p.subtitle}</p>}

            <div className="space-y-1.5 text-sm text-slate-700">
              <p className="flex items-center gap-2"><Truck className="h-4 w-4 text-coral-600" /> {t("fastShipping")}</p>
              <p className="flex items-center gap-2 font-semibold"><Droplets className="h-4 w-4 text-coral-600" /> {t("withWater")}</p>
            </div>

            <div className="text-2xl font-bold text-slate-900" data-testid="product-price">
              {fmtEUR(v?.price_eur || 0)}
              {showsBGN() && <span className="text-base font-normal text-slate-500 ml-2">({fmtBGN(v?.price_eur || 0)})</span>}
            </div>

            {p.variants.length > 1 && (
              <div>
                <p className="text-sm text-slate-600 mb-2">{t("package")}:</p>
                <div className="flex flex-wrap gap-2" data-testid="variant-selector">
                  {p.variants.map((va, i) => (
                    <button key={va.sku} type="button" onClick={() => setVariantIdx(i)}
                      className={`px-4 py-2 rounded-md border text-sm font-medium transition-colors ${
                        i === variantIdx ? "border-coral-600 bg-coral-50 text-coral-700" : "border-slate-300 text-slate-700 hover:border-slate-500"
                      }`}
                      data-testid={`variant-${va.sku}`}>
                      {va.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="flex items-stretch gap-3">
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
          </div>
        </div>

        {/* Long description */}
        {p.description && (
          <section className="mt-14 max-w-3xl">
            <div className="pp-rte" dangerouslySetInnerHTML={{ __html: p.description }} data-testid="product-description" />
          </section>
        )}

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
              <Link to={lp("/collections/all-peptides")}
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
    </Layout>
  );
}
