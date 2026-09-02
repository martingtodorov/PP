import { useState } from "react";
import { link } from "../lib/links";
import { Link } from "react-router-dom";
import Layout from "../components/Layout";
import PreCheckoutModal from "../components/PreCheckoutModal";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { useCart } from "../context/CartContext";
import { fmtPrice, fmtAmount, cartAmounts, fmtBGN, showsBGN, img } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import { formatErr } from "../lib/api";
import { toast } from "sonner";

export default function CartPage() {
  const { lp, t } = useLocaleCtx();
  useSeo({ title: `${t("seoCartTitle")} | PurePeptide`, description: t("seoCartDesc"), path: "/cart", robots: "noindex,follow" });

  const { items, remove, updateQty, subtotal, discount, discountAmount, applyDiscount, removeDiscount } = useCart();
  const [code, setCode] = useState("");
  const [preCheckout, setPreCheckout] = useState(false);
  const [terms, setTerms] = useState(false);
  const [applying, setApplying] = useState(false);
  const shipping = subtotal === 0 ? 0 : subtotal >= 100 ? 0 : 5.99;
  const total = Math.max(subtotal - discountAmount, 0) + shipping;
  /* the amounts actually shown: rounded per line, then summed — same rule as the backend */
  const amt = cartAmounts({ items, shippingEur: shipping, discount });

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="font-display text-4xl font-extrabold text-slate-900 mb-8" data-testid="cart-title">{t("cartTitle")}</h1>
        {items.length === 0 ? (
          <div className="bg-slate-50 border border-slate-200 rounded-xl p-12 text-center">
            <p className="text-slate-600">{t("cartEmpty")}</p>
            <Link to={lp(link("catalog"))}>
              <Button className="mt-6 bg-coral-600 hover:bg-coral-700">{t("toCatalog")}</Button>
            </Link>
          </div>
        ) : (
          <div className="grid lg:grid-cols-3 gap-10">
            <div className="lg:col-span-2 space-y-3">
              {items.map((it, i) => (
                <div key={it.variant_sku} className="bg-white border border-slate-200 rounded-xl p-4 flex gap-4" data-testid={`cart-line-${it.variant_sku}`}>
                  <img src={img(it.image, 300)} alt={it.title} className="w-24 h-24 object-contain bg-white border border-slate-200 rounded" />
                  <div className="flex-1 min-w-0">
                    <Link to={lp(`/products/${it.product_handle}`)} className="font-display font-semibold text-slate-900 hover:text-coral-600">{it.title}</Link>
                    <p className="text-sm text-slate-500">{it.variant_name}</p>
                    <div className="flex items-center gap-3 mt-3">
                      <div className="flex items-center border border-slate-300 rounded">
                        <button onClick={() => updateQty(it.variant_sku, it.quantity - 1)} className="px-2.5 py-1.5">−</button>
                        <span className="w-10 text-center text-sm">{it.quantity}</span>
                        <button onClick={() => updateQty(it.variant_sku, it.quantity + 1)} className="px-2.5 py-1.5">+</button>
                      </div>
                      <button onClick={() => remove(it.variant_sku)} className="text-sm text-slate-500 hover:text-red-600">{t("remove")}</button>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-display font-bold text-slate-900">{fmtAmount(amt.lines[i])}</p>
                    {showsBGN() && <p className="text-xs text-slate-500">({fmtBGN(it.price_eur * it.quantity)})</p>}
                  </div>
                </div>
              ))}
            </div>
            <div>
              <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 space-y-4 sticky top-24">
                <h2 className="font-display font-bold text-lg text-slate-900">{t("summary")}</h2>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-slate-600">{t("subtotal")}</span><span className="font-semibold">{fmtAmount(amt.subtotal)}</span></div>
                  {discountAmount > 0 && (
                    <div className="flex justify-between text-coral-700"><span>{t("discountLabel")} ({discount?.code})</span><span className="font-semibold">− {fmtAmount(amt.discountAmount)}</span></div>
                  )}
                  <div className="flex justify-between"><span className="text-slate-600">{t("shippingLabel")}</span><span className="font-semibold">{amt.shipping === 0 ? t("shippingFree") : fmtAmount(amt.shipping)}</span></div>
                  {subtotal < 100 && subtotal > 0 && (
                    <p className="text-xs text-coral-700 bg-coral-50 border border-coral-200 rounded p-2">
                      {t("freeShippingHint", { amount: fmtPrice(100 - subtotal) })}
                    </p>
                  )}
                  <div className="border-t border-slate-200 pt-3 flex justify-between text-base">
                    <span className="font-display font-bold text-slate-900">{t("totalLabel")}</span>
                    <span className="font-display font-extrabold text-slate-900" data-testid="cart-total">{fmtAmount(amt.total)}</span>
                  </div>
                  {showsBGN() && <p className="text-right text-xs text-slate-500">≈ {fmtBGN(total)}</p>}
                </div>
                <div className="mb-4">
                  {discount ? (
                    <div className="flex items-center justify-between text-sm border border-coral-200 bg-coral-50 rounded-md px-3 py-2" data-testid="cart-page-discount-applied">
                      <span className="font-mono font-semibold text-coral-700">{discount.code}</span>
                      <button onClick={removeDiscount} className="text-xs text-slate-500 hover:text-red-600" data-testid="cart-page-discount-remove">{t("remove")}</button>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <input value={code} onChange={(e) => setCode(e.target.value.toUpperCase())} placeholder={t("discountCodePh")}
                        className="flex-1 border border-slate-300 rounded-md px-3 py-2 text-sm uppercase focus:outline-none focus:border-coral-600"
                        data-testid="cart-page-discount-input" />
                      <button
                        onClick={async () => {
                          if (!code.trim()) return;
                          setApplying(true);
                          try { const d = await applyDiscount(code.trim()); toast.success(t("codeApplied", { code: d.code })); setCode(""); }
                          catch (e) { toast.error(formatErr(e)); } finally { setApplying(false); }
                        }}
                        disabled={applying}
                        className="px-4 py-2 rounded-md bg-slate-900 text-white text-sm font-medium disabled:opacity-50"
                        data-testid="cart-page-discount-apply">
                        {t("applyBtn")}
                      </button>
                    </div>
                  )}
                </div>
                <label className="flex items-start gap-2 text-xs text-slate-600 cursor-pointer mb-3">
                  <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)}
                    className="mt-0.5 accent-coral-600" data-testid="cart-terms-checkbox" />
                  <span>
                    {t("termsConsent18")}{" "}
                    <Link to={lp(link("terms"))} className="underline hover:text-coral-600" target="_blank">
                      {t("termsLinkLabel")}
                    </Link>
                  </span>
                </label>
                <Button className="w-full h-14 text-base sm:text-lg font-semibold bg-coral-600 hover:bg-coral-700"
                  disabled={!terms}
                  onClick={() => setPreCheckout(true)} data-testid="cart-checkout-btn">
                  {t("toPayment")}
                </Button>
                <p className="text-xs text-slate-500 text-center">{t("payHint")}</p>
              </div>
            </div>
          </div>
        )}
      </div>
      <PreCheckoutModal open={preCheckout} onClose={() => setPreCheckout(false)} termsAccepted={terms} />
    </Layout>
  );
}
