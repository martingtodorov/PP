import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { Truck, RotateCcw, Star, Minus, Plus } from "lucide-react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import ProductCard from "../components/ProductCard";
import { api, fmtEUR, fmtBGN } from "../lib/api";
import { useCart } from "../context/CartContext";

/**
 * React port of _product-details.liquid preset:
 *   breadcrumb → H1 title → reviews placeholder → price → variant pills
 *   → buy buttons (qty + add-to-cart secondary style)
 *   → trust group (truck + return icons with text)
 *   → accordion (Storage / Application / Shipping)
 *   → complementary products
 */
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

  if (!data.product)
    return <Layout><div className="max-w-7xl mx-auto px-4 py-20 text-slate-500">Зареждане…</div></Layout>;

  const p = data.product;
  const v = p.variants[variantIdx];
  const images = p.images && p.images.length ? p.images : [p.image];
  const out = !v || (v.stock || 0) <= 0;

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div className="grid lg:grid-cols-2 gap-12">
          {/* Gallery */}
          <div>
            <div className="aspect-square bg-white border border-slate-200 rounded-xl overflow-hidden">
              <img src={images[imgIdx]} alt={p.title} className="w-full h-full object-contain p-10" data-testid="product-main-image" />
            </div>
            {images.length > 1 && (
              <div className="flex gap-3 mt-4">
                {images.map((src, i) => (
                  <button
                    key={i}
                    onClick={() => setImgIdx(i)}
                    className={`w-20 h-20 bg-white border rounded-lg overflow-hidden ${i === imgIdx ? "border-slate-900" : "border-slate-200"}`}
                    aria-label={`Изображение ${i + 1}`}
                  >
                    <img src={src} alt="" className="w-full h-full object-contain p-2" />
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Details */}
          <div className="product-details">
            <nav className="breadcrumb flex gap-2" data-testid="breadcrumb">
              <Link to="/" className="hover:text-slate-700">Начало</Link>
              <span>/</span>
              <Link to="/collections/all-peptides" className="hover:text-slate-700">Каталог</Link>
            </nav>

            <h1 className="product-details__title" data-testid="product-title">{p.title}</h1>

            <div className="product-details__reviews">
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
              <span className="ml-1">Janoshik CoA — &gt;99% чистота</span>
            </div>

            <div className="product-details__price">
              <span className="font-bold" data-testid="product-price">{fmtEUR(v?.price_eur || 0)}</span>
              <span className="text-base font-normal text-slate-500">({fmtBGN(v?.price_eur || 0)})</span>
            </div>

            {p.variants.length > 1 && (
              <div>
                <p className="text-xs uppercase tracking-wider text-slate-500 mb-2">Вариант</p>
                <div className="product-details__variant-pills" data-testid="variant-selector">
                  {p.variants.map((va, i) => (
                    <button
                      key={va.sku}
                      type="button"
                      className="product-details__variant-pill"
                      aria-pressed={i === variantIdx}
                      onClick={() => setVariantIdx(i)}
                      data-testid={`variant-${va.sku}`}
                    >
                      {va.name}
                    </button>
                  ))}
                </div>
              </div>
            )}

            <div className="product-details__buy-row">
              <div className="product-details__qty">
                <button onClick={() => setQty(Math.max(1, qty - 1))} aria-label="−"><Minus className="h-4 w-4 mx-auto" /></button>
                <span data-testid="qty-value">{qty}</span>
                <button onClick={() => setQty(qty + 1)} aria-label="+"><Plus className="h-4 w-4 mx-auto" /></button>
              </div>
              <button
                type="button"
                className="button-secondary"
                disabled={out}
                onClick={() => {
                  add(p, v, qty);
                  toast.success("Добавено в количката", { description: `${p.title} × ${qty}` });
                }}
                data-testid="add-to-cart-btn"
              >
                {out ? "Изчерпано" : "Добави в количката"}
              </button>
            </div>

            <div className="product-details__trust">
              <div className="product-details__trust-row">
                <Truck className="h-4 w-4" strokeWidth={1.6} />
                <span>Безплатна доставка с Еконт за поръчки над {fmtEUR(100)}</span>
              </div>
              <div className="product-details__trust-row">
                <RotateCcw className="h-4 w-4" strokeWidth={1.6} />
                <span>14-дневно връщане при неотворен продукт</span>
              </div>
            </div>

            <div className="product-details__accordion">
              <details className="product-details__accordion-row" open>
                <summary>Описание</summary>
                <div className="body">{p.description || "Няма описание."}</div>
              </details>
              <details className="product-details__accordion-row">
                <summary>Съхранение</summary>
                <div className="body">
                  В лиофилизиран вид при 2–8°C, защитени от светлина и влага, пептидите запазват стабилност до 24 месеца. При стайна температура: ~4 месеца. След разтваряне в хладилник: ~4 седмици.
                </div>
              </details>
              <details className="product-details__accordion-row">
                <summary>Приложение</summary>
                <div className="body">
                  Продуктите са предназначени за научни и лабораторни цели. Не са предназначени за диагностика, лечение или предотвратяване на заболявания.
                </div>
              </details>
              <details className="product-details__accordion-row">
                <summary>Доставка</summary>
                <div className="body">
                  Изпращаме с Еконт. Доставка в България за 1–3 работни дни. Предлагаме банков превод и наложен платеж.
                </div>
              </details>
            </div>
          </div>
        </div>

        {/* Complementary / related products */}
        {data.related.length > 0 && (
          <section className="mt-24">
            <h2 className="text-2xl font-bold text-slate-900 mb-6">Подобни продукти</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-5">
              {data.related.map((r) => <ProductCard key={r.id} product={r} />)}
            </div>
          </section>
        )}
      </div>
    </Layout>
  );
}
