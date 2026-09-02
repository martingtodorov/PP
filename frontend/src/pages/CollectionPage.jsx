import { useEffect, useState } from "react";
import { link } from "../lib/links";
import { useParams, Link } from "react-router-dom";
import Layout, { USPRow } from "../components/Layout";
import ProductCard from "../components/ProductCard";
import NotFoundBlock from "../components/NotFoundBlock";
import Breadcrumbs from "../components/Breadcrumbs";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { LOCALES } from "../i18n/locales";
import { isAllCollection } from "../lib/collections";
import { useSeo } from "../lib/seo";
import { graph, itemListLd, breadcrumbLd, organizationLd } from "../lib/schema";

export default function CollectionPage() {
  const { handle = "2all-the-peptides-1" } = useParams();
  const [data, setData] = useState({ collection: null, products: [], siblings: [] });
  const [sort, setSort] = useState("featured");
  const [gone, setGone] = useState(false);
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    setGone(false);
    api.get(`/collections/${handle}`).then(({ data }) => setData(data)).catch(() => setGone(true));
  }, [handle, locale]);

  const c = data.collection;
  const descText = (c?.description || "").replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
  const alternates = {};
  if (c?.handles) LOCALES.forEach((l) => { alternates[l] = `/collections/${c.handles[l]}`; });

  useSeo({
    title: c ? (c.seo_title || `${c.title} | PurePeptide`) : "PurePeptide",
    description: c?.seo_description || descText,
    locale,
    path: `/collections/${handle}`,
    alternates,
    jsonLd: c && graph(
      {
        "@type": "CollectionPage",
        name: c.title,
        description: c.seo_description || descText,
        url: `${window.location.origin}/collections/${handle}`,
        isPartOf: { "@id": `${window.location.origin}/#website` },
        mainEntity: itemListLd(data.products || [], (p) => `/products/${p.handle}`),
      },
      breadcrumbLd([
        { name: "Начало", path: "/" },
        { name: c.title, path: `/collections/${handle}` },
      ]),
      organizationLd(),
    ),
  });

  const sorted = data.products;
  const loading = !c && !gone;

  if (gone) return <Layout><NotFoundBlock /></Layout>;

  if (loading) {
    return (
      <Layout>
        <div key="collection-skeleton" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 min-h-[2400px]" data-testid="collection-skeleton">
          <div className="h-3 w-40 bg-slate-100 rounded animate-pulse" />
          <div className="h-9 w-72 bg-slate-100 rounded mt-5 animate-pulse" />
          <div className="h-4 w-full max-w-2xl bg-slate-100 rounded mt-4 animate-pulse" />
          <div className="flex gap-2 mt-8">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="h-9 w-28 bg-slate-100 rounded-full animate-pulse" />
            ))}
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-3 gap-y-6 mt-10">
            {Array.from({ length: 8 }).map((_, i) => (
              <div key={i}>
                <div className="aspect-square bg-slate-100 rounded-xl animate-pulse" />
                <div className="h-4 w-3/4 bg-slate-100 rounded mt-3 animate-pulse" />
                <div className="h-4 w-1/3 bg-slate-100 rounded mt-2 animate-pulse" />
              </div>
            ))}
          </div>
        </div>
      </Layout>
    );
  }

  const isAll = isAllCollection(c);   // base_handle survives URL rotation

  return (
    <Layout>
      <div key="collection-content" className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-4">
        <Breadcrumbs
          items={isAll
            ? [{ label: t("catalog") }]
            : [{ label: t("catalog"), to: lp(link("catalog")) }, { label: c.title }]}
        />
        {/* like purepeptide.bg: the description carries the page H1 ("Пептиди, изследвани за…") */}
        {!/<h1[\s>]/i.test(c.description || "") && (
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-3"
            data-testid="collection-title">{isAll ? t("catalog") : c.title}</h1>
        )}
        {c.description && (
          <div className="pp-rte pp-rte--tight text-slate-600 mt-2 max-w-3xl leading-relaxed"
            dangerouslySetInnerHTML={{ __html: c.description }} data-testid="collection-description" />
        )}
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-3 pb-8">
        <div className="flex flex-wrap gap-2 mb-4 overflow-x-auto no-scrollbar" data-testid="collection-tabs">
          <Link to={lp(link("catalog"))}
            className={`px-4 py-2 rounded-full text-sm font-medium border whitespace-nowrap transition-colors ${
              isAll ? "bg-coral-600 text-white border-coral-600" : "bg-white text-slate-700 border-slate-200 hover:border-coral-400"
            }`}>
            {t("catalog")}
          </Link>
          {(data.siblings || []).map((s) => (
            <Link key={s.handle} to={lp(`/collections/${s.handle}`)}
              className="px-4 py-2 rounded-full text-sm font-medium border whitespace-nowrap bg-white text-slate-700 border-slate-200 hover:border-coral-400 transition-colors"
              data-testid={`sibling-${s.handle}`}>
              {s.title}
            </Link>
          ))}
        </div>

        <div className="flex justify-between items-center mb-4 text-sm">
          <span className="text-slate-500" data-testid="collection-count">{sorted.length} {t("productsCount")}</span>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-x-2 sm:gap-x-3 gap-y-6">
          {sorted.map((p) => <ProductCard key={p.id} product={p} showAddToCart />)}
        </div>
        {sorted.length === 0 && <p className="text-center text-slate-500 py-20">{t("emptyCollection")}</p>}
      </div>
      <USPRow />
    </Layout>
  );
}
