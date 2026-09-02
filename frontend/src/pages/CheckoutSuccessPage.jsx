import { useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { CheckCircle2, Copy } from "lucide-react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { api, fmtEUR, fmtAmount, amountOf, fmtBGN, showsBGN } from "../lib/api";

export default function CheckoutSuccessPage() {
  useSeo({ title: "Благодарим за поръчката | PurePeptide", description: "Поръчката е получена.", path: "/checkout/success", robots: "noindex,nofollow" });

  const { orderId } = useParams();
  const [data, setData] = useState(null);

  useEffect(() => {
    const cached = sessionStorage.getItem(`pp_order_${orderId}`);
    if (cached) {
      try { setData(JSON.parse(cached)); return; } catch {}
    }
    api.get(`/orders/${orderId}`).then(({ data }) => setData({ order: data.order, bank_transfer: null }));
  }, [orderId]);

  if (!data) return <Layout><div className="max-w-3xl mx-auto py-20 px-4 text-slate-500">Зареждане…</div></Layout>;
  const { order, bank_transfer } = data;

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success("Копирано"); };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-600" />
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 mt-6" data-testid="success-title">Благодарим за поръчката!</h1>
          <p className="text-slate-600 mt-3">
            Поръчка <span className="font-mono font-semibold text-slate-900" data-testid="order-number">{order.order_number}</span>
          </p>
        </div>

        {bank_transfer && (
          <div className="mt-10 bg-white border border-slate-200 rounded-xl p-8" data-testid="bank-transfer-info">
            <h2 className="font-display font-bold text-xl text-slate-900">Данни за банков превод</h2>
            <p className="text-sm text-slate-600 mt-1">Преведете точната сума и посочете референция в основанието за плащане.</p>
            <dl className="mt-6 space-y-3 text-sm">
              {[
                ["Получател", bank_transfer.holder],
                ["Банка", bank_transfer.name],
                ["IBAN", bank_transfer.iban],
                ["BIC", bank_transfer.bic],
                ["Референция (основание)", bank_transfer.reference],
                ["Сума", showsBGN() ? `${fmtEUR(bank_transfer.amount_eur)} (${fmtBGN(bank_transfer.amount_eur)})`
                          : fmtEUR(bank_transfer.amount_eur)],  /* the IBAN is a euro account */
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between items-center gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-mono text-slate-900 font-medium flex items-center gap-2">
                    {v}
                    <button onClick={() => copy(String(v))} className="text-slate-400 hover:text-slate-700"><Copy className="h-3.5 w-3.5" /></button>
                  </dd>
                </div>
              ))}
            </dl>
            <p className="mt-6 text-xs text-slate-500 leading-relaxed">
              След получаване на превода ще потвърдим поръчката по имейл и ще я изпратим с Еконт. Обработката отнема до 1 работен ден от плащането.
            </p>
          </div>
        )}

        <div className="mt-8 bg-slate-50 border border-slate-200 rounded-xl p-6">
          <h3 className="font-display font-bold text-slate-900 mb-3">Артикули</h3>
          <ul className="space-y-2 text-sm">
            {order.items.map((it) => (
              <li key={it.variant_sku} className="flex justify-between">
                <span className="text-slate-700">{it.title} — {it.variant_name} × {it.quantity}</span>
                <span className="font-semibold">
                  {fmtAmount((it.price_orig != null ? it.price_orig : amountOf(it.price_eur)) * it.quantity)}
                </span>
              </li>
            ))}
          </ul>
          <div className="border-t border-slate-200 mt-4 pt-3 flex justify-between font-display font-bold">
            <span>Общо</span><span>{fmtAmount(order.total_orig != null ? order.total_orig : order.total_eur)}</span>
          </div>
        </div>

        <div className="mt-10 flex justify-center gap-3">
          <Link to="/"><Button variant="outline">Към началото</Button></Link>
          <Link to="/account"><Button className="bg-coral-600 hover:bg-coral-700">Моите поръчки</Button></Link>
        </div>
      </div>
    </Layout>
  );
}
