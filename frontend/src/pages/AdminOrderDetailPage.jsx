import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams, Link } from "react-router-dom";
import { toast } from "sonner";
import { ArrowLeft, Copy, Check, Truck, Clock, PackageCheck } from "lucide-react";
import AdminLayout from "../components/AdminLayout";
import { ShipmentCard } from "../components/admin/ShipmentCard";
import { api, fmtEUR, fmtMoney, formatErr, img } from "../lib/api";
import { Badge, PAY_BADGE, FUL_BADGE } from "./AdminOrdersPage";

const CopyField = ({ label, value, testId, multiline = false }) => {
  const [copied, setCopied] = useState(false);
  if (!value) return (
    <div><p className="text-slate-500 text-sm mb-1">{label}</p><p className="text-slate-400 text-sm">—</p></div>
  );
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(value);
    } catch {
      const el = document.createElement("textarea");
      el.value = value;
      document.body.appendChild(el);
      el.select();
      document.execCommand("copy");
      el.remove();
    }
    setCopied(true);
    toast.success(`${label} е копиран${label.endsWith("а") ? "а" : ""}`);
    setTimeout(() => setCopied(false), 1500);
  };
  return (
    <div>
      <p className="text-slate-500 text-sm mb-1">{label}</p>
      <button type="button" onClick={copy}
        className="group w-full text-left flex items-start gap-2 rounded-lg -mx-2 px-2 py-1.5 hover:bg-slate-50 transition-colors"
        title="Копирай"
        data-testid={testId}>
        <span className={`text-sm text-slate-900 ${multiline ? "whitespace-pre-line" : "break-all"}`}>{value}</span>
        {copied
          ? <Check className="h-3.5 w-3.5 text-emerald-600 flex-shrink-0 mt-0.5" />
          : <Copy className="h-3.5 w-3.5 text-slate-300 group-hover:text-slate-600 flex-shrink-0 mt-0.5" />}
      </button>
    </div>
  );
};

export default function AdminOrderDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [order, setOrder] = useState(null);
  const [busy, setBusy] = useState("");

  const load = useCallback(() => {
    api.get(`/admin/orders/${id}`).then(({ data }) => setOrder(data.order))
      .catch((e) => toast.error(formatErr(e)));
  }, [id]);
  useEffect(() => { load(); }, [load]);

  const act = async (key, url, message) => {
    setBusy(key);
    try {
      const { data } = await api.post(url);
      toast.success(data.sent_to ? `${message}: ${data.sent_to}` : message);
      load();
    } catch (e) { toast.error(formatErr(e)); } finally { setBusy(""); }
  };

  if (!order) return <AdminLayout title="Поръчка"><p className="text-sm text-slate-400">Зареждане…</p></AdminLayout>;

  const paid = order.payment_status === "paid";
  const fulfilled = ["fulfilled", "shipped"].includes(order.fulfillment_status);
  const cur = order.currency || "EUR";
  const m = (n) => fmtMoney(n, cur);
  const totalDisp = order.total_display ?? order.total_eur;
  const balance = paid ? 0 : totalDisp;
  const addr = order.customer.address;

  return (
    <AdminLayout title={order.order_number}>
      <button onClick={() => nav("/admin/orders")} className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-slate-900 mb-4"
        data-testid="order-back-btn">
        <ArrowLeft className="h-4 w-4" /> Всички поръчки
      </button>

      <div className="flex flex-wrap items-center gap-3 mb-1">
        <h2 className="text-2xl font-bold text-slate-900">{order.order_number}</h2>
        <Badge map={FUL_BADGE} value={order.fulfillment_status} />
        <Badge map={PAY_BADGE} value={order.payment_status} />
      </div>
      <p className="text-sm text-slate-500 mb-6" data-testid="order-meta">
        {new Date(order.created_at).toLocaleString("bg-BG")} · {order.source === "shopify_import" ? "Shopify (импорт)" : "Онлайн магазин"}
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-[1fr_340px] gap-6 items-start">
        <div className="space-y-6 min-w-0">
          {/* fulfillment */}
          <section className="bg-white border border-slate-200 rounded-xl p-5" data-testid="order-fulfillment-card">
            <div className="flex items-center gap-2 mb-4">
              {fulfilled
                ? <span className="inline-flex items-center gap-2 bg-emerald-100 text-emerald-800 text-sm font-bold px-3 py-1.5 rounded-lg"><PackageCheck className="h-4 w-4" /> Изпратена ({order.items_count})</span>
                : <span className="inline-flex items-center gap-2 bg-amber-100 text-amber-900 text-sm font-bold px-3 py-1.5 rounded-lg"><Truck className="h-4 w-4" /> Неизпратена ({order.items_count})</span>}
              {order.shipping_method && <span className="text-sm text-slate-500">{order.shipping_method}</span>}
            </div>

            <ul className="space-y-4">
              {order.items.map((it, i) => (
                <li key={i} className="flex gap-3" data-testid={`order-item-${i}`}>
                  {it.image ? (
                    <img src={img(it.image, 160)} alt="" className="w-16 h-16 object-contain bg-slate-50 border border-slate-200 rounded-lg flex-shrink-0" />
                  ) : <div className="w-16 h-16 bg-slate-100 rounded-lg flex-shrink-0" />}
                  <div className="min-w-0 flex-1">
                    <p className="font-semibold text-slate-900 leading-snug">
                      {it.handle ? <Link to={`/admin/products`} className="hover:text-coral-700">{it.title}</Link> : it.title}
                    </p>
                    {it.variant && <p className="text-sm text-slate-600">{it.variant}</p>}
                    {it.sku && <p className="text-xs text-slate-500 font-mono">SKU: {it.sku}</p>}
                    <p className="text-sm text-slate-500 mt-0.5">
                      {m((it.price_display ?? it.price_eur) * it.quantity)} ({it.quantity} × {m(it.price_display ?? it.price_eur)})
                    </p>
                  </div>
                  <span className="font-bold text-slate-900 whitespace-nowrap">× {it.quantity}</span>
                </li>
              ))}
            </ul>

            {!fulfilled && (
              <button onClick={() => act("fulfill", `/admin/orders/${order.id}/fulfill`, "Маркирана като изпратена")}
                disabled={busy === "fulfill"}
                className="w-full mt-5 bg-slate-900 hover:bg-slate-800 text-white font-semibold py-3 rounded-lg text-sm disabled:opacity-60"
                data-testid="order-fulfill-btn">
                {busy === "fulfill" ? "Записване…" : "Маркирай като изпратена"}
              </button>
            )}
            {order.tracking?.tracking_number && (
              <p className="mt-4 text-sm text-slate-600">
                Товарителница: <span className="font-mono font-semibold">{order.tracking.tracking_number}</span>
                {order.tracking.mocked && <span className="ml-2 text-[10px] text-amber-700 uppercase">MOCKED</span>}
              </p>
            )}
          </section>

          <ShipmentCard order={order} onChanged={load} />

          {/* payment */}
          <section className="bg-white border border-slate-200 rounded-xl p-5" data-testid="order-payment-card">
            <div className="mb-4">
              {paid
                ? <span className="inline-flex items-center gap-2 bg-emerald-100 text-emerald-800 text-sm font-bold px-3 py-1.5 rounded-lg">Платена</span>
                : <span className="inline-flex items-center gap-2 bg-orange-100 text-orange-900 text-sm font-bold px-3 py-1.5 rounded-lg"><Clock className="h-4 w-4" /> Очаква плащане</span>}
            </div>

            <dl className="text-sm space-y-2">
              <div className="flex justify-between"><dt className="text-slate-500">{order.items_count} артикула · Междинна сума</dt><dd className="font-medium">{m(order.subtotal_display ?? order.subtotal_eur)}</dd></div>
              {(order.discount_display ?? order.discount_eur) > 0 && (
                <div className="flex justify-between"><dt className="text-slate-500">Отстъпка</dt><dd className="font-medium text-emerald-700">− {m(order.discount_display ?? order.discount_eur)}</dd></div>
              )}
              <div className="flex justify-between"><dt className="text-slate-500">Доставка</dt><dd className="font-medium">{m(order.shipping_display ?? order.shipping_eur)}</dd></div>
              <div className="flex justify-between border-t border-slate-100 pt-2 text-base"><dt className="font-bold">Общо</dt><dd className="font-bold" data-testid="order-total">{m(totalDisp)}</dd></div>
              {cur !== "EUR" && (
                <div className="flex justify-between"><dt className="text-slate-500">Равностойност в евро (курс {order.currency_rate} {cur}/EUR)</dt><dd className="font-medium" data-testid="order-total-eur">{fmtEUR(order.total_eur)}</dd></div>
              )}
              <div className="flex justify-between"><dt className="text-slate-500">Платено</dt><dd className="font-medium">{m(paid ? totalDisp : 0)}</dd></div>
              <div className="flex justify-between"><dt className="text-slate-500">Остатък</dt><dd className="font-semibold">{m(balance)}</dd></div>
            </dl>

            <div className="mt-5 space-y-2">
              <button onClick={() => act("invoice", `/admin/orders/${order.id}/send-invoice`, "Фактурата е изпратена")}
                disabled={busy === "invoice"}
                className="w-full bg-slate-900 hover:bg-slate-800 text-white font-semibold py-3 rounded-lg text-sm disabled:opacity-60"
                data-testid="order-send-invoice-btn">
                {busy === "invoice" ? "Изпращане…" : "Изпрати фактура по имейл"}
              </button>
              {!paid && (
                <button onClick={() => act("paid", `/admin/orders/${order.id}/mark-paid`, "Маркирана като платена")}
                  disabled={busy === "paid"}
                  className="w-full border border-slate-300 hover:border-slate-900 font-semibold py-3 rounded-lg text-sm disabled:opacity-60"
                  data-testid="order-mark-paid-btn">
                  {busy === "paid" ? "Записване…" : "Маркирай като платена"}
                </button>
              )}
            </div>
          </section>
        </div>

        {/* customer */}
        <aside className="bg-white border border-slate-200 rounded-xl p-5 space-y-4" data-testid="order-customer-card">
          <h3 className="font-bold text-slate-900">Клиент</h3>
          <CopyField label="Име" value={order.customer.name} testId="order-copy-name" />
          {order.customer.orders_count != null && (
            <p className="text-sm text-slate-500 -mt-2">
              {order.customer.orders_count} поръчки · {fmtEUR(order.customer.total_spent || 0)}
            </p>
          )}
          <CopyField label="Имейл" value={order.customer.email} testId="order-copy-email" />
          <CopyField label="Телефон" value={order.customer.phone} testId="order-copy-phone" />
          <CopyField
            label="Адрес за доставка"
            multiline
            value={[order.customer.name, addr.line1, `${addr.zip} ${addr.city}`.trim(), addr.country]
              .filter(Boolean).join("\n")}
            testId="order-copy-address"
          />
          <p className="text-[11px] text-slate-400">Клик върху поле го копира в клипборда.</p>
          {order.note && (
            <div className="text-sm">
              <p className="text-slate-500 mb-1">Бележка</p>
              <p className="text-slate-900">{order.note}</p>
            </div>
          )}
        </aside>
      </div>
    </AdminLayout>
  );
}
