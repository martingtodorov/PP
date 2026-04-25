import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import { Button } from "../components/ui/button";
import { useCart } from "../context/CartContext";
import { fmtEUR, fmtBGN } from "../lib/api";

export default function CartPage() {
  const { items, remove, updateQty, subtotal } = useCart();
  const shipping = subtotal === 0 ? 0 : subtotal >= 100 ? 0 : 5.99;
  const total = subtotal + shipping;

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="font-display text-4xl font-extrabold text-slate-900 mb-8" data-testid="cart-title">Количка</h1>
        {items.length === 0 ? (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-12 text-center">
            <p className="text-slate-600">Количката е празна.</p>
            <Link to="/collections/all-peptides">
              <Button className="mt-6 bg-coral-600 hover:bg-coral-700">Към каталога</Button>
            </Link>
          </div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-10">
            <div className="lg:col-span-2 space-y-3">
              {items.map((it) => (
                <div key={it.variant_sku} className="bg-white border border-slate-200 rounded-xl p-4 flex gap-4" data-testid={`cart-line-${it.variant_sku}`}>
                  <img src={it.image} alt={it.title} className="w-24 h-24 object-contain bg-white border border-slate-200 rounded" />
                  <div className="flex-1 min-w-0">
                    <Link to={`/products/${it.product_handle}`} className="font-display font-semibold text-slate-900 hover:text-coral-600">{it.title}</Link>
                    <p className="text-sm text-slate-500">{it.variant_name}</p>
                    <div className="flex items-center gap-3 mt-3">
                      <div className="flex items-center border border-slate-300 rounded">
                        <button onClick={() => updateQty(it.variant_sku, it.quantity - 1)} className="px-2.5 py-1.5">−</button>
                        <span className="w-10 text-center text-sm">{it.quantity}</span>
                        <button onClick={() => updateQty(it.variant_sku, it.quantity + 1)} className="px-2.5 py-1.5">+</button>
                      </div>
                      <button onClick={() => remove(it.variant_sku)} className="text-sm text-slate-500 hover:text-red-600">Премахни</button>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-display font-bold text-slate-900">{fmtEUR(it.price_eur * it.quantity)}</p>
                    <p className="text-xs text-slate-500">({fmtBGN(it.price_eur * it.quantity)})</p>
                  </div>
                </div>
              ))}
            </div>
            <div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 space-y-4 sticky top-24">
                <h2 className="font-display font-bold text-lg text-slate-900">Обобщение</h2>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-slate-600">Междинна сума</span><span className="font-semibold">{fmtEUR(subtotal)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-600">Доставка</span><span className="font-semibold">{shipping === 0 ? "Безплатна" : fmtEUR(shipping)}</span></div>
                  {subtotal < 100 && subtotal > 0 && (
                    <p className="text-xs text-coral-700 bg-coral-50 border border-coral-200 rounded p-2">
                      Добавете още {fmtEUR(100 - subtotal)} за безплатна доставка.
                    </p>
                  )}
                  <div className="border-t border-slate-200 pt-3 flex justify-between text-base">
                    <span className="font-display font-bold text-slate-900">Общо</span>
                    <span className="font-display font-extrabold text-slate-900" data-testid="cart-total">{fmtEUR(total)}</span>
                  </div>
                  <p className="text-right text-xs text-slate-500">≈ {fmtBGN(total)}</p>
                </div>
                <Link to="/checkout">
                  <Button className="w-full bg-coral-600 hover:bg-coral-700" data-testid="cart-checkout-btn">
                    Към плащане
                  </Button>
                </Link>
                <p className="text-xs text-slate-500 text-center">Плащане с банков превод или наложен платеж.</p>
              </div>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
