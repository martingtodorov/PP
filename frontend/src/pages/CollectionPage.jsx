import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import Layout from "../components/Layout";
import ProductCard from "../components/ProductCard";
import { api } from "../lib/api";

export default function CollectionPage() {
  const { handle = "all-peptides" } = useParams();
  const [data, setData] = useState({ collection: null, products: [] });
  const [collections, setCollections] = useState([]);
  const [sort, setSort] = useState("featured");

  useEffect(() => {
    api.get(`/collections/${handle}`).then(({ data }) => setData(data));
    api.get("/collections").then(({ data }) => setCollections(data.collections));
  }, [handle]);

  const sorted = [...data.products].sort((a, b) => {
    const ap = Math.min(...(a.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
    const bp = Math.min(...(b.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
    if (sort === "price-asc") return ap - bp;
    if (sort === "price-desc") return bp - ap;
    if (sort === "title") return a.title.localeCompare(b.title, "bg");
    return 0;
  });

  return (
    <Layout>
      <div className="bg-slate-50 border-b border-slate-200">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
          <p className="text-xs uppercase tracking-[0.2em] text-coral-600 font-bold mb-2">Колекция</p>
          <h1 className="font-display text-4xl sm:text-5xl font-extrabold text-slate-900" data-testid="collection-title">
            {data.collection?.title || handle}
          </h1>
          {data.collection?.description && (
            <p className="text-slate-600 mt-3 max-w-2xl">{data.collection.description}</p>
          )}
        </div>
      </div>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        {/* Tabs */}
        <div className="flex flex-wrap gap-2 mb-8 overflow-x-auto no-scrollbar" data-testid="collection-tabs">
          {collections.map((c) => (
            <Link
              key={c.handle}
              to={`/collections/${c.handle}`}
              className={`px-4 py-2 rounded-full text-sm font-medium border whitespace-nowrap transition-colors ${
                c.handle === handle
                  ? "bg-slate-900 text-white border-slate-900"
                  : "bg-white text-slate-700 border-slate-200 hover:border-slate-400"
              }`}
            >
              {c.title}
            </Link>
          ))}
        </div>

        <div className="flex justify-between items-center mb-6 text-sm">
          <span className="text-slate-500" data-testid="collection-count">{sorted.length} продукта</span>
          <select
            value={sort}
            onChange={(e) => setSort(e.target.value)}
            className="border border-slate-300 rounded-md px-3 py-2 bg-white"
            data-testid="sort-select"
          >
            <option value="featured">Препоръчани</option>
            <option value="price-asc">Цена: ниска → висока</option>
            <option value="price-desc">Цена: висока → ниска</option>
            <option value="title">По име</option>
          </select>
        </div>

        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-5">
          {sorted.map((p) => <ProductCard key={p.id} product={p} />)}
        </div>
        {sorted.length === 0 && <p className="text-center text-slate-500 py-20">Няма продукти в тази категория.</p>}
      </div>
    </Layout>
  );
}
