import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import Layout from "../components/Layout";
import Breadcrumbs from "../components/Breadcrumbs";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useSeo } from "../lib/seo";
import { graph, breadcrumbLd, organizationLd } from "../lib/schema";

const SECTIONS = {
  products: { title: "HTML sitemap — продукти", key: "products", to: (h) => `/products/${h}` },
  collections: { title: "HTML sitemap — категории", key: "collections", to: (h) => `/collections/${h}` },
  blogs: { title: "HTML sitemap — научни статии", key: "articles", to: (h) => `/articles/${h}` },
  articles: { title: "HTML sitemap — научни статии", key: "articles", to: (h) => `/articles/${h}` },
  pages: { title: "HTML sitemap — страници", key: "pages", to: (h) => `/pages/${h}` },
};

const HUB = [
  ["/pages/html-sitemap-products", "Продукти"],
  ["/pages/html-sitemap-collections", "Категории"],
  ["/pages/html-sitemap-blogs", "Научни статии"],
  ["/pages/html-sitemap-pages", "Страници"],
];

export default function HtmlSitemapPage() {
  const { pathname } = useLocation();
  const kind = (pathname.match(/html-sitemap-([a-z]+)/) || [])[1];
  const { lp, locale } = useLocaleCtx();
  const [index, setIndex] = useState(null);
  const section = SECTIONS[kind];

  useEffect(() => {
    api.get("/link-index").then(({ data }) => setIndex(data));
  }, [locale]);

  const title = section ? section.title : "HTML sitemap";
  const path = section ? `/pages/html-sitemap-${kind}` : "/pages/html-sitemap";

  useSeo({
    title: `${title} | PurePeptide`,
    description: "Пълен списък с всички страници, продукти, категории и научни статии на PurePeptide.",
    locale,
    path,
    jsonLd: graph(
      { "@type": "WebPage", name: title, url: `${window.location.origin}${path}` },
      breadcrumbLd([{ name: "Начало", path: "/" }, { name: title, path }]),
      organizationLd(),
    ),
  });

  const list = (items, to, keyName = "handle") => (
    <ul className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-x-8 gap-y-2" data-testid="sitemap-list">
      {items.map((it) => (
        <li key={it[keyName]} className="text-sm">
          <Link to={lp(to(it[keyName]))} className="text-slate-700 hover:text-coral-600 hover:underline underline-offset-4">
            {it.title || it[keyName]}
          </Link>
        </li>
      ))}
    </ul>
  );

  return (
    <Layout>
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-16">
        <Breadcrumbs items={[{ label: "HTML sitemap", to: lp("/pages/html-sitemap") }, ...(section ? [{ label: section.title }] : [])]} />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4">{title}</h1>

        <div className="flex flex-wrap gap-2 mt-6" data-testid="sitemap-hub-links">
          {HUB.map(([to, label]) => (
            <Link key={to} to={lp(to)}
              className="px-4 py-2 rounded-full border border-slate-200 text-sm text-slate-700 hover:border-coral-500 hover:text-coral-700 transition-colors">
              {label}
            </Link>
          ))}
        </div>

        {!index && <p className="mt-8 text-sm text-slate-400">Зареждане…</p>}

        {index && section && list(index[section.key] || [], section.to, section.key === "pages" ? "slug" : "handle")}

        {index && !section && (
          <div className="mt-8 space-y-10">
            <section>
              <h2 className="text-lg font-bold text-slate-900">Категории ({index.collections.length})</h2>
              {list(index.collections, (h) => `/collections/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">Продукти ({index.products.length})</h2>
              {list(index.products, (h) => `/products/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">Научни статии ({index.articles.length})</h2>
              {list(index.articles, (h) => `/articles/${h}`)}
            </section>
            <section>
              <h2 className="text-lg font-bold text-slate-900">Страници ({index.pages.length})</h2>
              {list(index.pages, (s) => `/pages/${s}`, "slug")}
            </section>
          </div>
        )}
      </div>
    </Layout>
  );
}
