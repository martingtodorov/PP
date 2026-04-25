import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Minus, Plus, ShieldCheck, FlaskConical, FileCheck2, Truck } from "lucide-react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import ProductCard from "../components/ProductCard";
import { Button } from "../components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "../components/ui/tabs";
import { api, fmtEUR, fmtBGN } from "../lib/api";
import { useCart } from "../context/CartContext";

export default function ProductPage() {
  const { handle } = useParams();
  const [data, setData] = useState({ product: null, related: [] });
  const [variantIdx, setVariantIdx] = useState(0);
  const [imgIdx, setImgIdx] = useState(0);
  const [qty, setQty] = useState(1);
  const { add } = useCart();

  useEffect(() => {
    setVariantIdx(0);
    setImgIdx(0);
    setQty(1);
    api.get(`/products/${handle}`).then(({ data }) => setData(data));
  }, [handle]);

  if (!data.product) return <Layout><div className="max-w-7xl mx-auto px-4 py-20 text-slate-500">Зареждане…</div></Layout>;

  const p = data.product;
  const v = p.variants[variantIdx];
  const images = p.images && p.images.length ? p.images : [p.image];
  const out = !v || (v.stock || 0) <= 0;

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <nav className="text-xs text-slate-500 mb-6 flex gap-2" data-testid="breadcrumb">
          <Link to="/" className="hover:text-slate-700">Начало</Link>
          <span>/</span>
          <Link to="/collections/all-peptides" className="hover:text-slate-700">Каталог</Link>
          <span>/</span>
          <span className="text-slate-700">{p.title}</span>
        </nav>

        <div className="grid lg:grid-cols-2 gap-12">
          <div>
            <div className="aspect-square bg-slate-50 border border-slate-200 rounded-xl overflow-hidden">
              <img src={images[imgIdx]} alt={p.title} className="w-full h-full object-contain p-10" data-testid="product-main-image" />
            </div>
            {images.length > 1 && (
              <div className="flex gap-3 mt-4">
                {images.map((src, i) => (
                  <button
                    key={i}
                    onClick={() => setImgIdx(i)}
                    className={`w-20 h-20 bg-slate-50 border rounded-lg overflow-hidden ${i === imgIdx ? "border-blue-600" : "border-slate-200"}`}
                  >
                    <img src={src} alt="" className="w-full h-full object-contain p-2" />
                  </button>
                ))}
              </div>
            )}
          </div>

          <div>
            {p.subtitle && <p className="text-xs uppercase tracking-[0.2em] text-blue-600 font-bold">{p.subtitle}</p>}
            <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 mt-2" data-testid="product-title">{p.title}</h1>
            <div className="mt-5 flex items-baseline gap-3">
              <span className="font-display text-3xl font-extrabold text-slate-900" data-testid="product-price">{fmtEUR(v?.price_eur || 0)}</span>
              <span className="text-slate-500">({fmtBGN(v?.price_eur || 0)})</span>
            </div>

            {p.variants.length > 1 && (
              <div className="mt-6">
                <p className="text-sm font-medium text-slate-700 mb-2">Вариант</p>
                <div className="flex flex-wrap gap-2" data-testid="variant-selector">
                  {p.variants.map((va, i) => (
                    <button
                      key={va.sku}
                      onClick={() => setVariantIdx(i)}
                      className={`px-4 py-2 rounded-md border text-sm font-medium ${
                        i === variantIdx ? "bg-slate-900 text-white border-slate-900" : "border-slate-300 text-slate-700 hover:border-slate-400"
                      }`}
                      data-testid={`variant-${va.sku}`}
                    >
                      {va.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="mt-6 flex items-center gap-4">
              <div className="flex items-center border border-slate-300 rounded-md">
                <button onClick={() => setQty(Math.max(1, qty - 1))} className="px-3 py-2.5"><Minus className="h-4 w-4" /></button>
                <span className="w-10 text-center font-medium" data-testid="qty-value">{qty}</span>
                <button onClick={() => setQty(qty + 1)} className="px-3 py-2.5"><Plus className="h-4 w-4" /></button>
              </div>
              <Button
                size="lg"
                className="flex-1 bg-blue-600 hover:bg-blue-700"
                disabled={out}
                onClick={() => {
                  add(p, v, qty);
                  toast.success("Добавено в количката", { description: `${p.title} × ${qty}` });
                }}
                data-testid="add-to-cart-btn"
              >
                {out ? "Изчерпано" : "Добави в количката"}
              </Button>
            </div>

            <div className="mt-8 grid grid-cols-2 gap-4 text-sm">
              <div className="flex items-start gap-3"><ShieldCheck className="h-5 w-5 text-blue-600 mt-0.5" /><div><p className="font-semibold text-slate-900">&gt;99% чистота</p><p className="text-slate-500 text-xs">HPLC + LC-MS</p></div></div>
              <div className="flex items-start gap-3"><FileCheck2 className="h-5 w-5 text-blue-600 mt-0.5" /><div><p className="font-semibold text-slate-900">Janoshik CoA</p><p className="text-slate-500 text-xs">Сертификат за анализ</p></div></div>
              <div className="flex items-start gap-3"><FlaskConical className="h-5 w-5 text-blue-600 mt-0.5" /><div><p className="font-semibold text-slate-900">Лиофилизиран</p><p className="text-slate-500 text-xs">Стабилен до 24 м.</p></div></div>
              <div className="flex items-start gap-3"><Truck className="h-5 w-5 text-blue-600 mt-0.5" /><div><p className="font-semibold text-slate-900">Доставка с Еконт</p><p className="text-slate-500 text-xs">1–3 работни дни</p></div></div>
            </div>

            <Tabs defaultValue="desc" className="mt-10">
              <TabsList>
                <TabsTrigger value="desc" data-testid="tab-description">Описание</TabsTrigger>
                <TabsTrigger value="storage">Съхранение</TabsTrigger>
                <TabsTrigger value="shipping">Доставка</TabsTrigger>
              </TabsList>
              <TabsContent value="desc" className="text-slate-600 leading-relaxed pt-4">
                {p.description || "Няма описание."}
              </TabsContent>
              <TabsContent value="storage" className="text-slate-600 leading-relaxed pt-4">
                В лиофилизиран вид при 2–8°C, защитени от светлина и влага, пептидите запазват стабилност до 24 месеца. Стайна температура: ~4 месеца. След разтваряне в хладилник: ~4 седмици.
              </TabsContent>
              <TabsContent value="shipping" className="text-slate-600 leading-relaxed pt-4">
                Изпращаме с Еконт. Доставка в България за 1–3 работни дни. Предлагаме наложен платеж и банков превод.
              </TabsContent>
            </Tabs>
          </div>
        </div>

        {data.related.length > 0 && (
          <section className="mt-24">
            <h2 className="font-display text-2xl font-bold text-slate-900 mb-6">Подобни продукти</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              {data.related.map((r) => <ProductCard key={r.id} product={r} />)}
            </div>
          </section>
        )}
      </div>
    </Layout>
  );
}
