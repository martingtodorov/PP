import { useCallback, useEffect, useState } from "react";
import { useParams, Link } from "react-router-dom";
import { CheckCircle2, Copy } from "lucide-react";
import { toast } from "sonner";
import Layout from "../components/Layout";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { api, fmtEUR, fmtAmount, amountOf, fmtBGN, showsBGN } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import CancelOrderButton from "../components/CancelOrderButton";

export default function CheckoutSuccessPage() {
  const { t } = useLocaleCtx();
  useSeo({ title: `${t("seoThanksTitle")} | PurePeptide`, description: t("seoThanksDesc"), path: "/checkout/success", robots: "noindex,nofollow" });

  const { orderId } = useParams();
  const [data, setData] = useState(null);

  const load = useCallback(() => {
    /* the cached copy paints instantly; the API answer carries the live status (cancellable, AWB) */
    const cached = sessionStorage.getItem(`pp_order_${orderId}`);
    if (cached) {
      try { setData(JSON.parse(cached)); } catch {}
    }
    api.get(`/orders/${orderId}`)
      .then(({ data }) => setData((cur) => ({ order: data.order, bank_transfer: cur?.bank_transfer || null })))
      .catch(() => {});
  }, [orderId]);
  useEffect(() => { load(); }, [load]);

  if (!data) return <Layout><div className="max-w-3xl mx-auto py-20 px-4 text-slate-500">{t("loadingText")}</div></Layout>;
  const { order, bank_transfer } = data;

  const copy = (txt) => { navigator.clipboard.writeText(txt); toast.success(t("copiedToast")); };

  return (
    <Layout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center">
            <CheckCircle2 className="h-8 w-8 text-emerald-600" />
          </div>
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900 mt-6" data-testid="success-title">{t("thanksTitle")}</h1>
          <p className="text-slate-600 mt-3">
            {t("orderWord")} <span className="font-mono font-semibold text-slate-900" data-testid="order-number">{order.order_number}</span>
          </p>
        </div>

        <section className="mt-10 bg-white border border-slate-200 rounded-xl p-8" data-testid="order-tracking">
          <h2 className="font-display font-bold text-xl text-slate-900">{t("trackingTitle")}</h2>
          {order.shipment?.awb && order.shipment.status !== "Cancelled" ? (
            <dl className="mt-4 space-y-3 text-sm">
              {[[t("trackingCourier"), order.shipment.courier || "NextLevel"],
                [t("trackingNumber"), order.shipment.awb],
                ...(order.shipment.status ? [[t("trackingStatus"), order.shipment.status]] : [])].map(([k, v]) => (
                <div key={k} className="flex justify-between items-center gap-4 border-b border-slate-100 pb-2">
                  <dt className="text-slate-500">{k}</dt>
                  <dd className="font-mono text-slate-900 font-medium" data-testid={`tracking-${k === t("trackingNumber") ? "awb" : "row"}`}>{v}</dd>
                </div>
              ))}
              {order.shipment.tracking_link && (
                <a href={order.shipment.tracking_link} target="_blank" rel="noreferrer"
                  className="inline-flex items-center gap-2 mt-2 bg-slate-900 hover:bg-slate-800 text-white font-semibold px-5 py-3 rounded-md"
                  data-testid="tracking-open-link">{t("trackingOpen")}</a>
              )}
            </dl>
          ) : (
            <p className="text-sm text-slate-600 mt-2" data-testid="tracking-pending">{t("trackingPending")}</p>
          )}
        </section>

        {bank_transfer && (
          <div className="mt-10 bg-white border border-slate-200 rounded-xl p-8" data-testid="bank-transfer-info">
            <h2 className="font-display font-bold text-xl text-slate-900">{t("bankDetailsTitle")}</h2>
            <p className="text-sm text-slate-600 mt-1">{t("bankDetailsNote")}</p>
            <dl className="mt-6 space-y-3 text-sm">
              {[
                [t("recipientLabel"), bank_transfer.holder],
                [t("bankLabel"), bank_transfer.name],
                ["IBAN", bank_transfer.iban],
                ["BIC", bank_transfer.bic],
                [t("referenceLabel"), bank_transfer.reference],
                [t("amountLabel"), showsBGN() ? `${fmtEUR(bank_transfer.amount_eur)} (${fmtBGN(bank_transfer.amount_eur)})`
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
              {t("afterTransferNote")}
            </p>
          </div>
        )}

        <div className="mt-8 bg-slate-50 border border-slate-200 rounded-xl p-6">
          <h3 className="font-display font-bold text-slate-900 mb-3">{t("itemsTitle")}</h3>
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
            <span>{t("totalLabel")}</span><span>{fmtAmount(order.total_orig != null ? order.total_orig : order.total_eur)}</span>
          </div>
        </div>

        <div className="mt-10 flex flex-wrap justify-center gap-3">
          <Link to="/"><Button variant="outline">{t("toHome")}</Button></Link>
          <Link to="/account"><Button className="bg-coral-600 hover:bg-coral-700">{t("myOrders")}</Button></Link>
          <CancelOrderButton order={order} onDone={load} />
        </div>
      </div>
    </Layout>
  );
}
