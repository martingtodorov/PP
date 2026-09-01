import { useEffect, useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import Layout from "../components/Layout";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { Textarea } from "../components/ui/textarea";
import { RadioGroup, RadioGroupItem } from "../components/ui/radio-group";
import { useCart } from "../context/CartContext";
import { useAuth } from "../context/AuthContext";
import { api, fmtEUR, fmtBGN, formatErr, img } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

export default function CheckoutPage() {
  useSeo({ title: "Плащане | PurePeptide", description: "Завършване на поръчка.", path: "/checkout", robots: "noindex,nofollow" });

  const { items, subtotal, clear, note, setNote, discount, discountAmount } = useCart();
  const { user } = useAuth();
  const nav = useNavigate();
  const { lp } = useLocaleCtx();
  const [shippingMethod, setShippingMethod] = useState("speedy");
  const [terms, setTerms] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [placed, setPlaced] = useState(false);
  const [form, setForm] = useState({
    full_name: "", email: "", phone: "",
    line1: "", city: "", postal_code: "", country: "BG", note: "",
  });

  useEffect(() => {
    if (items.length === 0 && !placed) nav(lp("/cart"));
  }, [items.length, nav]);

  useEffect(() => {
    if (user) setForm((f) => ({ ...f, full_name: user.name || f.full_name, email: user.email || f.email, phone: user.phone || f.phone }));
  }, [user]);

  const shipping = shippingMethod === "speedy" ? 7.49 : 5.99;
  const finalShipping = subtotal >= 100 ? 0 : shipping;
  const total = Math.max(subtotal - discountAmount, 0) + finalShipping;

  const submit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      const payload = {
        items: items.map((x) => ({ product_id: x.product_id, variant_sku: x.variant_sku, quantity: x.quantity })),
        shipping: {
          full_name: form.full_name, phone: form.phone, email: form.email,
          line1: form.line1, city: form.city, postal_code: form.postal_code, country: form.country, note: form.note,
        },
        customer_email: form.email,
        customer_name: form.full_name,
        customer_phone: form.phone,
        shipping_method: shippingMethod,
        notes: note || form.note,
        discount_code: discount?.code || "",
        terms_accepted: terms,
      };
      const { data } = await api.post("/checkout", payload);
      clear();
      sessionStorage.setItem(`pp_order_${data.order.id}`, JSON.stringify(data));
      setPlaced(true);
      nav(lp(`/checkout/success/${data.order.id}`));
    } catch (e) {
      toast.error(formatErr(e));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Layout>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        <h1 className="font-display text-4xl font-extrabold text-slate-900 mb-8">Поръчка</h1>
        <form onSubmit={submit} className="grid lg:grid-cols-3 gap-10">
          <div className="lg:col-span-2 space-y-8">
            <section className="bg-white border border-slate-200 rounded-xl p-6">
              <h2 className="font-display font-bold text-lg text-slate-900 mb-5">Контакт</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div><Label>Имена</Label><Input required value={form.full_name} onChange={(e) => setForm({...form, full_name: e.target.value})} data-testid="checkout-name" /></div>
                <div><Label>Имейл</Label><Input type="email" required value={form.email} onChange={(e) => setForm({...form, email: e.target.value})} data-testid="checkout-email" /></div>
                <div className="sm:col-span-2"><Label>Телефон</Label><Input required value={form.phone} onChange={(e) => setForm({...form, phone: e.target.value})} data-testid="checkout-phone" /></div>
              </div>
              {!user && (
                <p className="text-xs text-slate-500 mt-4">
                  Имате профил? <Link to={lp("/account")} className="text-coral-600 font-medium">Влезте</Link>, за да следите поръчките си.
                </p>
              )}
            </section>

            <section className="bg-white border border-slate-200 rounded-xl p-6">
              <h2 className="font-display font-bold text-lg text-slate-900 mb-5">Адрес за доставка</h2>
              <div className="grid sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2"><Label>Адрес</Label><Input required value={form.line1} onChange={(e) => setForm({...form, line1: e.target.value})} data-testid="checkout-address" /></div>
                <div><Label>Град</Label><Input required value={form.city} onChange={(e) => setForm({...form, city: e.target.value})} data-testid="checkout-city" /></div>
                <div><Label>Пощенски код</Label><Input required value={form.postal_code} onChange={(e) => setForm({...form, postal_code: e.target.value})} data-testid="checkout-postal" /></div>
                <div className="sm:col-span-2"><Label>Специални инструкции (по желание)</Label><Textarea value={note} onChange={(e) => setNote(e.target.value)} data-testid="checkout-note" /></div>
              </div>
            </section>

            <section className="bg-white border border-slate-200 rounded-xl p-6">
              <h2 className="font-display font-bold text-lg text-slate-900 mb-5">Метод за доставка</h2>
              <RadioGroup value={shippingMethod} onValueChange={setShippingMethod} className="space-y-3" data-testid="shipping-method">
                {[
                  { v: "speedy", t: "Спиди – до офис", d: "Доставка до избран офис на Спиди", p: "5.99" },
                  { v: "econt_address", t: "Спиди – до адрес", d: "Куриер до посочения адрес", p: "5.99" },
                  { v: "econt_office", t: "Еконт – до офис", d: "Доставка до избран офис на Еконт", p: "5.99" },
                ].map((s) => (
                  <label key={s.v} className={`flex items-center gap-4 border rounded-lg p-4 cursor-pointer ${shippingMethod === s.v ? "border-coral-600 bg-coral-50/40" : "border-slate-200"}`}>
                    <RadioGroupItem value={s.v} id={s.v} />
                    <div className="flex-1">
                      <p className="font-medium text-slate-900">{s.t}</p>
                      <p className="text-xs text-slate-500">{s.d}</p>
                    </div>
                    <span className="font-display font-bold text-slate-900">{subtotal >= 100 ? "Безплатно" : `€${s.p}`}</span>
                  </label>
                ))}
              </RadioGroup>
            </section>

            <section className="bg-white border border-slate-200 rounded-xl p-6">
              <h2 className="font-display font-bold text-lg text-slate-900 mb-3">Метод за плащане</h2>
              <div className="border-2 border-coral-600 bg-coral-50/40 rounded-lg p-4">
                <p className="font-medium text-slate-900">Банков превод</p>
                <p className="text-sm text-slate-600 mt-1">След потвърждение ще получите банкови данни и референция на поръчката. Поръчката се обработва след получаване на превода.</p>
              </div>
            </section>
          </div>

          <div>
            <div className="bg-slate-50 border border-slate-200 rounded-xl p-6 sticky top-24 space-y-4">
              <h2 className="font-display font-bold text-lg text-slate-900">Вашата поръчка</h2>
              <div className="space-y-3 max-h-72 overflow-y-auto">
                {items.map((it) => (
                  <div key={it.variant_sku} className="flex gap-3 text-sm">
                    <img src={img(it.image, 160)} alt={it.title} className="w-14 h-14 object-contain bg-white border border-slate-200 rounded" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-slate-900 truncate">{it.title}</p>
                      <p className="text-xs text-slate-500">{it.variant_name} × {it.quantity}</p>
                    </div>
                    <span className="font-semibold text-slate-900">{fmtEUR(it.price_eur * it.quantity)}</span>
                  </div>
                ))}
              </div>
              <div className="border-t border-slate-200 pt-4 space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-slate-600">Междинна сума</span><span className="font-semibold">{fmtEUR(subtotal)}</span></div>
                {discountAmount > 0 && (
                  <div className="flex justify-between text-coral-700" data-testid="checkout-discount-row">
                    <span>Отстъпка ({discount?.code})</span><span className="font-semibold">− {fmtEUR(discountAmount)}</span>
                  </div>
                )}
                <div className="flex justify-between"><span className="text-slate-600">Доставка</span><span className="font-semibold">{finalShipping === 0 ? "Безплатна" : fmtEUR(finalShipping)}</span></div>
                <div className="border-t border-slate-200 pt-2 flex justify-between">
                  <span className="font-display font-bold">Общо</span>
                  <div className="text-right">
                    <span className="font-display font-extrabold text-lg block" data-testid="checkout-total">{fmtEUR(total)}</span>
                    <span className="text-xs text-slate-500">{fmtBGN(total)}</span>
                  </div>
                </div>
              </div>
              <label className="flex items-start gap-2 text-xs text-slate-600 cursor-pointer">
                <input type="checkbox" checked={terms} onChange={(e) => setTerms(e.target.checked)} className="mt-0.5 accent-coral-600" data-testid="checkout-terms-checkbox" />
                <span>Съгласявам се с <Link to={lp("/pages/terms-conditions")} className="underline hover:text-coral-600">общите условия</Link> и потвърждавам, че поръчвам за научноизследователски цели.</span>
              </label>
              <Button type="submit" disabled={submitting || !terms} className="w-full bg-coral-600 hover:bg-coral-700" data-testid="place-order-btn">
                {submitting ? "Обработка…" : "Завърши поръчката"}
              </Button>
            </div>
          </div>
        </form>
      </div>
    </Layout>
  );
}
