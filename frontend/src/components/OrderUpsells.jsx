import { useCallback, useEffect, useState } from "react";
import { Clock, Plus } from "lucide-react";
import { toast } from "sonner";
import { api, fmtPrice, formatErr, img } from "../lib/api";
import { useLocaleCtx } from "../i18n/LocaleContext";

const mmss = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Five-minute window after checkout: anything added here ships in the same parcel. */
export const OrderUpsells = ({ orderId, onAdded }) => {
  const { locale, t } = useLocaleCtx();
  const [products, setProducts] = useState([]);
  const [left, setLeft] = useState(0);
  const [chosen, setChosen] = useState({});
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    api.get(`/orders/${orderId}/upsells`, { params: { locale } })
      .then(({ data }) => {
        setProducts(data.products || []);
        setLeft(Number(data.window?.seconds_left || 0));
      })
      .catch(() => setProducts([]));
  }, [orderId, locale]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const id = setInterval(() => setLeft((v) => (v > 0 ? v - 1 : 0)), 1000);
    return () => clearInterval(id);
  }, []);

  const add = async (p) => {
    const sku = chosen[p.handle] || (p.variants || [])[0]?.sku;
    if (!sku) return;
    setBusy(p.handle);
    try {
      await api.post(`/orders/${orderId}/items`, {
        items: [{ product_id: p.id, variant_sku: sku, quantity: 1 }],
      });
      toast.success(t("upsellAdded"));
      setProducts((list) => list.filter((x) => x.handle !== p.handle));
      if (onAdded) onAdded();
    } catch (e) {
      toast.error(formatErr(e));
      load();
    } finally {
      setBusy("");
    }
  };

  if (left <= 0 || !products.length) return null;

  return (
    <section className="mt-10 bg-white border border-coral-200 rounded-xl p-6 sm:p-8" data-testid="order-upsells">
      <div className="flex flex-wrap items-center gap-3">
        <h2 className="font-display font-bold text-xl text-slate-900">{t("upsellTitle")}</h2>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-coral-50 text-coral-700 px-3 py-1 text-xs font-bold"
          data-testid="upsell-countdown">
          <Clock className="h-3.5 w-3.5" /> {mmss(left)}
        </span>
      </div>
      <p className="text-sm text-slate-600 mt-2">{t("upsellNote")}</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {products.map((p) => {
          const variants = p.variants || [];
          const sku = chosen[p.handle] || variants[0]?.sku;
          const variant = variants.find((v) => v.sku === sku) || variants[0];
          return (
            <div key={p.handle} className="border border-slate-200 rounded-lg p-3 flex flex-col"
              data-testid={`upsell-card-${p.handle}`}>
              <div className="aspect-square bg-white">
                <img src={img(p.image, 240)} alt={p.title} loading="lazy"
                  className="w-full h-full object-contain" />
              </div>
              <p className="mt-2 text-sm font-semibold text-slate-900 line-clamp-2">{p.title}</p>
              {variants.length > 1 && (
                <select
                  value={sku}
                  onChange={(e) => setChosen({ ...chosen, [p.handle]: e.target.value })}
                  className="mt-2 w-full border border-slate-300 rounded-md px-2 py-1.5 text-xs"
                  data-testid={`upsell-variant-${p.handle}`}
                >
                  {variants.map((v) => (
                    <option key={v.sku} value={v.sku}>{v.name} · {fmtPrice(v.price_eur)}</option>
                  ))}
                </select>
              )}
              <p className="mt-2 font-display font-bold text-slate-900">{fmtPrice(variant?.price_eur || 0)}</p>
              <button
                type="button"
                onClick={() => add(p)}
                disabled={busy === p.handle}
                className="mt-3 inline-flex items-center justify-center gap-1.5 rounded-md bg-coral-600 hover:bg-coral-700 text-white text-sm font-semibold py-2.5 transition-colors disabled:opacity-60"
                data-testid={`upsell-add-${p.handle}`}
              >
                <Plus className="h-4 w-4" /> {busy === p.handle ? t("processingText") : t("upsellAdd")}
              </button>
            </div>
          );
        })}
      </div>
    </section>
  );
};

export default OrderUpsells;
