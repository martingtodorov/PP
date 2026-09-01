import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Layout, { USPRow } from "../components/Layout";
import Breadcrumbs from "../components/Breadcrumbs";
import ProductCard from "../components/ProductCard";
import { api } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { useSeo } from "../lib/seo";
import { graph, articleLd, breadcrumbLd, organizationLd } from "../lib/schema";

export default function ArticlePage() {
  const { handle } = useParams();
  const [articles, setArticles] = useState([]);
  const [product, setProduct] = useState(null);
  const { lp, t, locale } = useLocaleCtx();

  useEffect(() => {
    api.get("/articles").then(({ data }) => setArticles(data.articles));
  }, [locale]);

  const article = articles.find((a) => a.handle === handle);

  useEffect(() => {
    setProduct(null);
    if (!article?.product_handle) return;
    api.get(`/products/${article.product_handle}`).then(({ data }) => setProduct(data.product)).catch(() => {});
  }, [article?.product_handle]);

  useSeo({
    title: article ? (article.seo_title || `${article.title} | PurePeptide`) : "PurePeptide",
    description: article?.seo_description || article?.excerpt || "",
    locale,
    path: `/articles/${handle}`,
    image: article?.image,
    jsonLd: article && graph(
      articleLd({ article, path: `/articles/${handle}` }),
      breadcrumbLd([
        { name: "Начало", path: "/" },
        { name: "Научни статии", path: "/pages/articles" },
        { name: article.title, path: `/articles/${handle}` },
      ]),
      organizationLd(),
    ),
  });

  if (!article) {
    return <Layout><div className="max-w-3xl mx-auto px-4 py-20 text-slate-500">{t("loading")}</div></Layout>;
  }

  return (
    <Layout>
      <article className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 pt-5 pb-14">
        <Breadcrumbs items={[{ label: t("articles"), to: lp("/pages/articles") }, { label: article.title }]} />
        <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 tracking-tight mt-4 leading-tight" data-testid="article-title">
          {article.title}
        </h1>
        <div className="aspect-[16/9] bg-white border border-slate-200 rounded-xl overflow-hidden mt-6">
          <img src={article.image} alt={article.title} className="w-full h-full object-contain" />
        </div>
        <div className="pp-rte mt-8" data-testid="article-body">
          <p className="text-lg text-slate-700">{article.excerpt}</p>
          <p>{t("disclaimer")}</p>
        </div>

        {product && (
          <section className="mt-10">
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-4">{t("relatedProducts")}</p>
            <div className="max-w-[240px]" data-testid="article-related-product">
              <ProductCard product={product} />
            </div>
          </section>
        )}

        <section className="mt-12 border-t border-slate-200 pt-8">
          <p className="text-xs uppercase tracking-[0.18em] text-slate-500 font-bold mb-4">{t("articles")}</p>
          <ul className="space-y-3">
            {articles.filter((a) => a.handle !== handle).map((a) => (
              <li key={a.handle}>
                <Link to={lp(`/articles/${a.handle}`)} className="text-slate-800 hover:text-coral-600 underline-offset-4 hover:underline">
                  {a.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </article>
      <USPRow />
    </Layout>
  );
}
