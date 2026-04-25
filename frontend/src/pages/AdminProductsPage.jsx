import { useEffect, useState } from "react";
import AdminLayout from "../components/AdminLayout";
import { api, fmtEUR } from "../lib/api";

export default function AdminProductsPage() {
  const [products, setProducts] = useState([]);
  const [search, setSearch] = useState("");

  useEffect(() => {
    api.get("/admin/products").then(({ data }) => setProducts(data.products));
  }, []);

  const filtered = products.filter((p) => p.title.toLowerCase().includes(search.toLowerCase()));

  return (
    <AdminLayout title="Продукти">
      <div className="flex gap-3 mb-6">
        <input
          placeholder="Търсене…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="border border-slate-300 rounded-md px-4 py-2 text-sm flex-1 max-w-md"
          data-testid="products-search"
        />
      </div>
      <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
        <table className="w-full text-sm">
          <thead className="bg-slate-50 text-xs uppercase text-slate-500">
            <tr>
              <th className="text-left px-4 py-3">Продукт</th>
              <th className="text-left px-4 py-3">Handle</th>
              <th className="text-left px-4 py-3">Варианти</th>
              <th className="text-left px-4 py-3">Цена от</th>
              <th className="text-left px-4 py-3">Налични</th>
              <th className="text-left px-4 py-3">Колекции</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((p) => {
              const minPrice = Math.min(...(p.variants || [{ price_eur: 0 }]).map((v) => v.price_eur));
              const stock = (p.variants || []).reduce((s, v) => s + (v.stock || 0), 0);
              return (
                <tr key={p.id} className="border-t border-slate-100 hover:bg-slate-50" data-testid={`admin-product-${p.handle}`}>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
                      <img src={p.image} alt="" className="w-10 h-10 object-contain bg-white border border-slate-200 rounded" />
                      <span className="font-medium">{p.title}</span>
                    </div>
                  </td>
                  <td className="px-4 py-3 font-mono text-xs text-slate-500">{p.handle}</td>
                  <td className="px-4 py-3">{p.variants?.length || 0}</td>
                  <td className="px-4 py-3 font-semibold">{fmtEUR(minPrice)}</td>
                  <td className="px-4 py-3">{stock <= 0 ? <span className="text-red-600 font-medium">Изчерпан</span> : stock}</td>
                  <td className="px-4 py-3 text-xs text-slate-500">{(p.collections || []).join(", ")}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </AdminLayout>
  );
}
