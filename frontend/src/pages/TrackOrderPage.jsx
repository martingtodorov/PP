import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { PackageSearch, Truck } from "lucide-react";
import Layout from "../components/Layout";
import { useSeo } from "../lib/seo";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Label } from "../components/ui/label";
import { api, fmtMoney, formatErr } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";
import TrackTimeline from "../components/TrackTimeline";

export default function TrackOrderPage() {
  const { t } = useLocaleCtx();
  useSeo({ title: `${t("trackTitle")} | PurePeptide`, description: t("seoTrackDesc"), path: "/track", robots: "noindex,follow" });

  const [params] = useSearchParams();
  const [form, setForm] = useState({ order_number: params.get("n") || "", phone: "" });
  const [order, setOrder] = useState(null);
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { setForm((f) => ({ ...f, order_number: params.get("n") || f.order_number })); }, [params]);

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true); setErr("");
    try {
      const { data } = await api.post("/orders/track", form);
      setOrder(data.order);
    } catch (ex) {
      setOrder(null);
      setErr(ex?.response?.status === 404 ? t("trackNotFound") : formatErr(ex));
    } finally { setBusy(false); }
  };

  const money = (v) => fmtMoney(v, order?.currency || "EUR");
  const dest = order?.delivery || {};

  return (
    <Layout>
      <div className="max-w-3xl mx-auto px-4 sm:px-6 lg:px-8 py-14">
        <div className="flex items-center gap-3">
          <PackageSearch className="h-7 w-7 text-coral-600" />
          <h1 className="font-display text-3xl sm:text-4xl font-extrabold text-slate-900" data-testid="track-title">{t("trackTitle")}</h1>
        </div>

        {!order && (
          <form onSubmit={submit} className="mt-8 bg-white border border-slate-200 rounded-xl p-6 sm:p-8 space-y-5" data-testid="track-form">
            <p className="text-sm text-slate-600">{t("trackIntro")}</p>
            <div className="grid sm:grid-cols-2 gap-4">
              <div>
                <Label htmlFor="track-number">{t("trackNumberLabel")}</Label>
                <Input id="track-number" required autoComplete="off" placeholder={t("trackNumberPh")}
                  value={form.order_number} onChange={(e) => setForm({ ...form, order_number: e.target.value })}
                  className="mt-1 font-mono uppercase" data-testid="track-number-input" />
              </div>
              <div>
                <Label htmlFor="track-phone">{t("trackPhoneLabel")}</Label>
                <Input id="track-phone" required type="tel" autoComplete="tel" placeholder="+359 8xx xxx xxx"
                  value={form.phone} onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  className="mt-1" data-testid="track-phone-input" />
              </div>
            </div>
            {err && <p className="text-sm text-red-600" data-testid="track-error">{err}</p>}
            <Button type="submit" disabled={busy} className="bg-coral-600 hover:bg-coral-700 rounded-md px-8" data-testid="track-submit">
              {busy ? "…" : t("trackSubmit")}
            </Button>
          </form>
        )}

        {order && (
          <div className="mt-8 space-y-6" data-testid="track-result">
            <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8">
              <div className="flex flex-wrap items-baseline justify-between gap-2">
                <p className="text-slate-600 text-sm">
                  {t("orderWord")} <span className="font-mono font-semibold text-slate-900" data-testid="track-order-number">{order.order_number}</span>
                </p>
                <p className="text-sm text-slate-500">
                  {t("trackDateLabel")}: {new Date(order.created_at).toLocaleDateString()}
                </p>
              </div>
              {order.cancelled
                ? <p className="mt-6 text-sm font-semibold text-slate-700 bg-slate-100 border border-slate-200 rounded-md p-3" data-testid="track-cancelled">{t("trackCancelled")}</p>
                : <TrackTimeline steps={order.steps} t={t} />}
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8" data-testid="track-shipment">
              <h2 className="font-display font-bold text-xl text-slate-900 flex items-center gap-2">
                <Truck className="h-5 w-5 text-coral-600" /> {t("trackingTitle")}
              </h2>
              {order.shipment ? (
                <>
                  <dl className="mt-4 space-y-3 text-sm">
                    {[[t("trackingCourier"), order.shipment.courier || "NextLevel"],
                      [t("trackingNumber"), order.shipment.awb],
                      ...(order.shipment.status ? [[t("trackingStatus"), order.shipment.status]] : [])].map(([k, v]) => (
                      <div key={k} className="flex justify-between items-center gap-4 border-b border-slate-100 pb-2">
                        <dt className="text-slate-500">{k}</dt>
                        <dd className="font-mono text-slate-900 font-medium">{v}</dd>
                      </div>
                    ))}
                  </dl>
                  {order.shipment.tracking_link && (
                    <a href={order.shipment.tracking_link} target="_blank" rel="noreferrer"
                      className="inline-flex items-center gap-2 mt-4 bg-slate-900 hover:bg-slate-800 text-white font-semibold px-5 py-3 rounded-md transition-colors"
                      data-testid="track-courier-link">{t("trackingOpen")}</a>
                  )}
                </>
              ) : (
                <p className="text-sm text-slate-600 mt-2" data-testid="track-pending">{t("trackingPending")}</p>
              )}
            </div>

            <div className="bg-white border border-slate-200 rounded-xl p-6 sm:p-8">
              <h2 className="font-display font-bold text-lg text-slate-900">{t("trackItemsLabel")}</h2>
              <ul className="mt-3 space-y-2 text-sm text-slate-700" data-testid="track-items">
                {order.items.map((it, i) => (
                  <li key={i} className="flex justify-between gap-4 border-b border-slate-100 pb-2">
                    <span>{it.title}{it.variant ? ` · ${it.variant}` : ""} × {it.quantity}</span>
                    <span className="font-semibold whitespace-nowrap">{money(it.price_display * it.quantity)}</span>
                  </li>
                ))}
              </ul>
              <div className="mt-3 flex justify-between text-base">
                <span className="font-display font-bold text-slate-900">{t("totalLabel")}</span>
                <span className="font-display font-extrabold text-slate-900" data-testid="track-total">{money(order.total_display)}</span>
              </div>
              <p className="mt-6 text-sm text-slate-600">
                <span className="text-slate-500">{t("trackDeliveryTo")}: </span>
                {[dest.courier, dest.office_name || dest.line1, dest.office_address,
                  `${dest.postal_code || ""} ${dest.city || ""}`.trim(), dest.country].filter(Boolean).join(" · ")}
              </p>
            </div>

            <button onClick={() => { setOrder(null); setForm({ order_number: "", phone: "" }); }}
              className="text-sm font-semibold text-coral-700 hover:text-coral-800" data-testid="track-reset">
              {t("trackAnother")}
            </button>
          </div>
        )}
      </div>
    </Layout>
  );
}
