import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Layout, { USPRow } from "../components/Layout";
import ProductCard from "../components/ProductCard";
import Breadcrumbs from "../components/Breadcrumbs";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { LOCALES } from "../i18n/locales";
import { useSeo } from "../lib/seo";
import { graph, itemListLd, breadcrumbLd, organizationLd } from "../lib/schema";

export default function CollectionPage() {
  const { handle = "2all-the-peptides-1" } = useParams();
  const [data, setData] = useState({ collection: null, products: [], siblings: [] });
  const [sort, setSort] = useState("featured");
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    api.get(`/collections/${handle}`).then(({ data }) => setData(data));
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

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 pt-5">
        <Breadcrumbs
          items={[{ label: t("catalog"), to: lp("/collections/2all-the-peptides-1") }, { label: c?.title || handle }]}
        />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4" data-testid="collection-title">
          {c?.title || handle}
        </h1>
        {c?.description && (
          <div className="pp-rte text-slate-600 mt-3 max-w-3xl leading-relaxed"
            dangerouslySetInnerHTML={{ __html: c.description }} data-testid="collection-description" />
        )}
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="flex flex-wrap gap-2 mb-7 overflow-x-auto no-scrollbar" data-testid="collection-tabs">
          <Link to={lp("/collections/2all-the-peptides-1")}
            className={`px-4 py-2 rounded-full text-sm font-medium border whitespace-nowrap transition-colors ${
              handle === "2all-the-peptides-1" ? "bg-coral-600 text-white border-coral-600" : "bg-white text-slate-700 border-slate-200 hover:border-coral-400"
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

        <div className="flex justify-between items-center mb-6 text-sm">
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
